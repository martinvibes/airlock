import socket
from pathlib import Path

import pytest

from airlock import psi, sim

START, END = "2026-11-03T08:00:00Z", "2026-11-03T14:00:00Z"


@pytest.fixture(scope="module")
def pristine(tmp_path_factory):
    out = tmp_path_factory.mktemp("data")
    summary = sim.generate(out)
    return out, summary


@pytest.fixture
def live(pristine, tmp_path):
    src, _ = pristine
    dst = tmp_path / "live"
    sim.reset(src, dst)
    return dst


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_generation_matches_the_story(pristine):
    out, summary = pristine
    assert summary["payments"] == 480 and summary["stuck"] == 37
    assert summary["rejected"] == 42 and summary["support_credited"] == 5
    orders = sim.read_csv(out / "merchant" / "orders.csv")
    assert len(orders) == 540
    assert sum(o["status"] == "pending" for o in orders) == 97  # 37 paid + 60 abandoned
    assert sum(o["status"] == "credited" for o in orders) == 443


def test_generation_is_deterministic(pristine, tmp_path):
    out, _ = pristine
    sim.generate(tmp_path)
    for f in ("provider/payments.csv", "merchant/orders.csv", "merchant/app.log"):
        assert (tmp_path / f).read_text() == (out / f).read_text()


def test_committed_data_is_current(pristine):
    out, _ = pristine
    repo = Path(__file__).resolve().parents[1] / "data"
    for f in ("provider/payments.csv", "merchant/orders.csv", "provider/webhook_attempts.log"):
        assert (repo / f).read_text() == (out / f).read_text(), f"regenerate data/: {f}"


def test_all_401s_come_from_the_canary(pristine):
    out, _ = pristine
    lines = (out / "merchant" / "app.log").read_text().splitlines()
    rejected = [line for line in lines if "status=401" in line]
    assert len(rejected) == 126  # 42 payments x 3 attempts
    assert all("pod=pod-canary-1" in line and "verifier=v2.14.0" in line for line in rejected)


def test_neither_side_alone_knows_the_37(pristine):
    out, _ = pristine
    # KudiMart's verifier rejects before parsing: its 401 lines name no payment.
    app = (out / "merchant" / "app.log").read_text().splitlines()
    assert not any("ref=" in line or "order=" in line for line in app if "status=401" in line)
    # Paylane's own log says 42 gave up, but support already credited 5 by hand.
    gave_up = [r for r in sim.read_csv(out / "provider" / "payments.csv") if r["webhook_status"] == "gave_up"]
    assert len(gave_up) == 42
    orders = {o["reference"]: o for o in sim.read_csv(out / "merchant" / "orders.csv")}
    assert sum(orders[r["reference"]]["credited_via"] == "support" for r in gave_up) == 5
    assert sum("action=manual_credit" in line for line in app) == 5


def test_pending_alone_cannot_identify_the_paid(pristine):
    out, _ = pristine
    paid = {r["reference"] for r in sim.read_csv(out / "provider" / "payments.csv")}
    pending = [o for o in sim.read_csv(out / "merchant" / "orders.csv") if o["status"] == "pending"]
    assert sum(o["reference"] in paid for o in pending) == 37
    assert sum(o["reference"] not in paid for o in pending) == 60


def run_psi(provider_dir, merchant_dir):
    prov = psi.Provider(sim.provider_items(provider_dir, START, END))
    a_prime, b = psi.merchant_round2(prov.round1(), sim.merchant_credited_items(merchant_dir))
    return prov.finish(a_prime, b)


def test_full_incident_replay_fails_before_fix_then_closes(live):
    port = free_port()
    server = sim.serve(live / "merchant", port)
    url = f"http://127.0.0.1:{port}{sim.ENDPOINT_PATH}"
    try:
        stuck = run_psi(live / "provider", live / "merchant")
        assert len(stuck) == 37

        before = sim.replay(live / "provider", stuck, url)
        assert before == {"attempted": 37, "delivered": 0, "rejected": 37}

        sim.deploy_fix(live / "merchant")
        after = sim.replay(live / "provider", stuck, url)
        assert after == {"attempted": 37, "delivered": 37, "rejected": 0}

        assert run_psi(live / "provider", live / "merchant") == []

        # Had Paylane replayed its whole gave-up list, 5 would have been duplicates.
        provider = sim.read_csv(live / "provider" / "payments.csv")
        everything = [psi.item(r["reference"], int(r["amount_kobo"])) for r in provider
                      if r["webhook_status"] == "gave_up"]
        again = sim.replay(live / "provider", everything, url)
        assert again["attempted"] == 42
        log = (live / "merchant" / "app.log").read_text()
        assert log.count("result=duplicate") == 42  # the 37 just replayed, plus 5 credited by support
    finally:
        server.shutdown()


def test_bad_signature_is_rejected_even_after_fix(live):
    sim.deploy_fix(live / "merchant")
    m = sim.Merchant(live / "merchant")
    row = sim.read_csv(live / "provider" / "payments.csv")[0]
    body = sim.webhook_body(row["reference"], int(row["amount_kobo"]), row["paid_at"])
    assert m.handle(body, {"x-sig-primary": "00" * 32, "x-sig-secondary": "11" * 32})[0] == 401
    good = sim.sign(body, sim.OLD_SECRET)
    assert m.handle(body, {"x-sig-secondary": good})[0] == 200
