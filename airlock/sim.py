"""The simulated incident: synthetic data, KudiMart's webhook endpoint, the
fix and Paylane's replay. Everything here is fictional and deterministic.

Story (Nov 3 2026, UTC). Neither change is wrong on its own:

- 09:12 KudiMart deploys verifier v2.14.0 to a 10% canary, pod-canary-1.
  v2.14.0 reads only X-Sig-Primary. The other pods run v2.13.2, which
  accepts either signature header.
- 09:40 Paylane rotates its signing secret with a 72h overlap. X-Sig-Primary
  is signed with the new secret, X-Sig-Secondary with the old one.
- KudiMart still holds only the old secret. Webhooks are routed to pods by a
  hash of the payment reference, so a payment routed to the canary after
  09:40 gets a 401 on every retry. Paylane gives up after 3 attempts.
- 37 customers were debited and their orders are still pending.

Layout of a data folder:

    provider/  payments.csv  webhook_attempts.log  changes.log  signing.json
    merchant/  orders.csv    app.log  deploys.log  verifier.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import json
import random
import shutil
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx

from . import psi

DAY = datetime(2026, 11, 3, tzinfo=UTC)
WINDOW_START = DAY.replace(hour=8)
WINDOW_END = DAY.replace(hour=14)
CANARY_DEPLOY = DAY.replace(hour=9, minute=12)
ROTATION = DAY.replace(hour=9, minute=40)
N_PAYMENTS = 480
N_STUCK = 37
N_ABANDONED = 60
RETRY_DELAYS = (0, 30, 120)  # seconds after payment, three attempts

PODS = [f"pod-{i}" for i in range(1, 10)] + ["pod-canary-1"]
CANARY = "pod-canary-1"
OLD_KEY_ID = "whsec-2026-08"
NEW_KEY_ID = "whsec-2026-11"
# Synthetic secrets, derived so the data is reproducible. Not real keys.
OLD_SECRET = hashlib.sha256(b"airlock-synthetic-old-secret").hexdigest()
NEW_SECRET = hashlib.sha256(b"airlock-synthetic-new-secret").hexdigest()

ACCEPTED_HEADERS = {
    "v2.13.2": ("X-Sig-Primary", "X-Sig-Secondary"),
    "v2.14.0": ("X-Sig-Primary",),
    "v2.14.1": ("X-Sig-Primary", "X-Sig-Secondary"),
}
FIX_VERSION = "v2.14.1"
ENDPOINT_PATH = "/webhooks/paylane"


def ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def route(reference: str) -> str:
    """Sticky routing: the same reference always lands on the same pod."""
    h = int.from_bytes(hashlib.sha256(reference.encode()).digest()[:4], "big")
    return PODS[h % len(PODS)]


def sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def webhook_body(reference: str, amount_kobo: int, paid_at: str) -> bytes:
    return json.dumps(
        {"event": "charge.success", "reference": reference, "amount_kobo": amount_kobo, "paid_at": paid_at},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def is_stuck(reference: str, paid_at: datetime) -> bool:
    return paid_at >= ROTATION and route(reference) == CANARY


# ── data generation ──────────────────────────────────────────────────────────


@dataclass
class Payment:
    reference: str
    order_id: str
    amount_kobo: int
    phone: str
    card_last4: str
    paid_at: datetime


def _payments(seed: int) -> list[Payment]:
    rng = random.Random(seed)
    span = int((WINDOW_END - WINDOW_START).total_seconds())
    times = sorted(WINDOW_START + timedelta(seconds=rng.randrange(span)) for _ in range(N_PAYMENTS))
    out = []
    for n, t in enumerate(times, 1):
        out.append(
            Payment(
                reference=f"KDM-{rng.randrange(16**6):06X}-{n:04d}",
                order_id=f"KM-{100000 + n}",
                amount_kobo=rng.randrange(150_000, 2_500_000, 50),
                phone="+234800" + f"{rng.randrange(10**7):07d}",
                card_last4=f"{rng.randrange(10**4):04d}",
                paid_at=t,
            )
        )
    return out


def find_seed() -> int:
    """The first seed giving exactly N_STUCK stuck payments. Deterministic."""
    seed = 0
    while sum(is_stuck(p.reference, p.paid_at) for p in _payments(seed)) != N_STUCK:
        seed += 1
    return seed


def generate(out: Path) -> dict[str, int]:
    seed = find_seed()
    rng = random.Random(seed + 10_000)
    payments = _payments(seed)
    prov, merch = out / "provider", out / "merchant"
    prov.mkdir(parents=True, exist_ok=True)
    merch.mkdir(parents=True, exist_ok=True)

    attempts: list[tuple[datetime, str]] = []
    app: list[tuple[datetime, str]] = []
    pay_rows, order_rows = [], []
    stuck = 0
    for p in payments:
        pod = route(p.reference)
        version = "v2.14.0" if pod == CANARY and p.paid_at >= CANARY_DEPLOY else "v2.13.2"
        bad = is_stuck(p.reference, p.paid_at)
        stuck += bad
        tries = RETRY_DELAYS if bad else RETRY_DELAYS[:1]
        for n, delay in enumerate(tries, 1):
            at = p.paid_at + timedelta(seconds=delay + rng.randrange(1, 4))
            status = 401 if bad else 200
            attempts.append(
                (at, f"{ts(at)} attempt={n} ref={p.reference} merchant=kudimart "
                     f"endpoint=https://api.kudimart.example{ENDPOINT_PATH} status={status} "
                     f"latency_ms={rng.randrange(18, 90)} key_primary={NEW_KEY_ID if p.paid_at >= ROTATION else OLD_KEY_ID}")
            )
            if bad:
                app.append((at, f"{ts(at)} level=warn pod={pod} verifier={version} webhook ref={p.reference} "
                                f"header=X-Sig-Primary result=signature_mismatch status=401"))
            else:
                app.append((at, f"{ts(at)} level=info pod={pod} verifier={version} webhook ref={p.reference} "
                                f"result=ok order={p.order_id} status=200 credited"))
        if bad:
            at = p.paid_at + timedelta(seconds=RETRY_DELAYS[-1] + 5)
            attempts.append((at, f"{ts(at)} gave_up ref={p.reference} merchant=kudimart attempts=3 last_status=401"))
        pay_rows.append([p.reference, p.amount_kobo, "success", p.phone, p.card_last4, ts(p.paid_at),
                         "gave_up" if bad else "delivered"])
        order_rows.append([p.order_id, p.reference, p.amount_kobo, p.phone, ts(p.paid_at - timedelta(seconds=40)),
                           "pending" if bad else "credited", "" if bad else ts(p.paid_at + timedelta(seconds=3))])

    span = int((WINDOW_END - WINDOW_START).total_seconds())
    for n in range(1, N_ABANDONED + 1):
        created = WINDOW_START + timedelta(seconds=rng.randrange(span))
        order_rows.append([f"KM-{200000 + n}", f"KDM-{rng.randrange(16**6):06X}-A{n:03d}",
                           rng.randrange(150_000, 2_500_000, 50), "+234800" + f"{rng.randrange(10**7):07d}",
                           ts(created), "pending", ""])
    order_rows.sort(key=lambda r: r[4])

    with open(prov / "payments.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["reference", "amount_kobo", "status", "customer_phone", "card_last4", "paid_at", "webhook_status"])
        w.writerows(pay_rows)
    with open(merch / "orders.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["order_id", "reference", "amount_kobo", "customer_phone", "created_at", "status", "credited_at"])
        w.writerows(order_rows)
    (prov / "webhook_attempts.log").write_text("\n".join(line for _, line in sorted(attempts)) + "\n")
    (merch / "app.log").write_text("\n".join(line for _, line in sorted(app)) + "\n")
    (prov / "changes.log").write_text(
        "2026-11-02T16:20:00Z change=fraud_rules_updated scope=all_merchants detail=velocity_threshold_raised\n"
        f"{ts(ROTATION)} change=signing_secret_rotated service=webhook-signer version=v4.1.0 merchant=kudimart new_key={NEW_KEY_ID} old_key={OLD_KEY_ID}\n"
        f"{ts(ROTATION)} change=secret_overlap_window_opened service=webhook-signer version=v4.1.0 merchant=kudimart "
        f"overlap_until={ts(ROTATION + timedelta(hours=72))} X-Sig-Primary={NEW_KEY_ID} X-Sig-Secondary={OLD_KEY_ID}\n"
        "2026-11-03T11:30:00Z change=dashboard_deployed version=v8.3.0 scope=internal\n"
    )
    (merch / "deploys.log").write_text(
        "2026-11-02T14:05:00Z service=checkout-web version=v5.2.0 target=all strategy=rolling\n"
        f"{ts(CANARY_DEPLOY)} service=webhook-verifier version=v2.14.0 target={CANARY} strategy=canary weight=10% "
        "note=verify_X-Sig-Primary_only_legacy_header_fallback_removed\n"
    )
    (prov / "signing.json").write_text(json.dumps({
        "merchant": "kudimart",
        "rotated_at": ts(ROTATION),
        "overlap_until": ts(ROTATION + timedelta(hours=72)),
        "headers": {
            "X-Sig-Primary": {"key_id": NEW_KEY_ID, "secret": NEW_SECRET},
            "X-Sig-Secondary": {"key_id": OLD_KEY_ID, "secret": OLD_SECRET},
        },
        "max_attempts": 3,
        "note": "synthetic secrets for a fictional demo",
    }, indent=2) + "\n")
    (merch / "verifier.json").write_text(json.dumps({
        "secret": {"key_id": OLD_KEY_ID, "value": OLD_SECRET, "installed_at": "2026-08-14T10:00:00Z"},
        "pods": {pod: ("v2.14.0" if pod == CANARY else "v2.13.2") for pod in PODS},
        "versions": {v: {"accepted_headers": list(h)} for v, h in ACCEPTED_HEADERS.items() if v != FIX_VERSION},
        "routing": "sha256(reference) mod 10 picks the pod; retries go to the same pod",
        "note": "synthetic secret for a fictional demo",
    }, indent=2) + "\n")
    return {"payments": len(pay_rows), "orders": len(order_rows), "stuck": stuck, "seed": seed}


def reset(src: Path, dst: Path) -> None:
    """Copy pristine data into a live state folder the server may change."""
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


# ── reading each side's records (each side reads only its own folder) ───────


def read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def provider_items(provider_dir: Path, start: str, end: str) -> list[str]:
    """Paylane's successful payments in a window, as PSI items."""
    return [
        psi.item(r["reference"], int(r["amount_kobo"]))
        for r in read_csv(provider_dir / "payments.csv")
        if r["status"] == "success" and start <= r["paid_at"] < end
    ]


def merchant_credited_items(merchant_dir: Path) -> list[str]:
    """KudiMart's credited orders, as PSI items. Pending orders are left out:
    pending alone can't tell paid from abandoned, which is the point."""
    return [
        psi.item(r["reference"], int(r["amount_kobo"]))
        for r in read_csv(merchant_dir / "orders.csv")
        if r["status"] == "credited"
    ]


# ── KudiMart's webhook endpoint ──────────────────────────────────────────────


class Merchant:
    """KudiMart's order store and verifier, backed by a live state folder."""

    def __init__(self, merchant_dir: Path):
        self.dir = merchant_dir
        self.lock = threading.Lock()

    def _config(self) -> dict[str, Any]:
        return json.loads((self.dir / "verifier.json").read_text())

    def handle(self, body: bytes, headers: dict[str, str]) -> tuple[int, str]:
        cfg = self._config()
        try:
            event = json.loads(body)
            reference, amount = event["reference"], int(event["amount_kobo"])
        except (ValueError, KeyError, TypeError):
            return 400, "bad body"
        pod = route(reference)
        version = cfg["pods"][pod]
        secret = cfg["secret"]["value"]
        accepted = ACCEPTED_HEADERS[version]
        ok = any(
            hmac.compare_digest(headers.get(h.lower(), ""), sign(body, secret)) for h in accepted
        )
        now = ts(datetime.now(UTC))
        if not ok:
            self._log(f"{now} level=warn pod={pod} verifier={version} webhook ref={reference} "
                      f"header={'+'.join(accepted)} result=signature_mismatch status=401")
            return 401, "signature mismatch"
        with self.lock:
            rows = read_csv(self.dir / "orders.csv")
            for r in rows:
                if r["reference"] == reference:
                    if int(r["amount_kobo"]) != amount:
                        return 409, "amount mismatch"
                    if r["status"] != "credited":
                        r["status"], r["credited_at"] = "credited", now
                        self._write_orders(rows)
                    self._log(f"{now} level=info pod={pod} verifier={version} webhook ref={reference} "
                              f"result=ok order={r['order_id']} status=200 credited")
                    return 200, "credited"
        return 404, "unknown reference"

    def _write_orders(self, rows: list[dict[str, str]]) -> None:
        tmp = self.dir / "orders.csv.tmp"
        with open(tmp, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        tmp.replace(self.dir / "orders.csv")

    def _log(self, line: str) -> None:
        with open(self.dir / "app.log", "a") as f:
            f.write(line + "\n")


def deploy_fix(merchant_dir: Path) -> str:
    """Ship v2.14.1 to the canary: accept either signature header again."""
    path = merchant_dir / "verifier.json"
    cfg = json.loads(path.read_text())
    cfg["pods"][CANARY] = FIX_VERSION
    cfg["versions"][FIX_VERSION] = {"accepted_headers": list(ACCEPTED_HEADERS[FIX_VERSION])}
    path.write_text(json.dumps(cfg, indent=2) + "\n")
    now = ts(datetime.now(UTC))
    with open(merchant_dir / "deploys.log", "a") as f:
        f.write(f"{now} service=webhook-verifier version={FIX_VERSION} target={CANARY} strategy=canary "
                "weight=10% note=accept_either_signature_header\n")
    return now


def serve(merchant_dir: Path, port: int = 8787, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    merchant = Merchant(merchant_dir)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            if self.path != ENDPOINT_PATH:
                self.send_error(404)
                return
            length = int(self.headers.get("content-length", 0))
            status, text = merchant.handle(
                self.rfile.read(length), {k.lower(): v for k, v in self.headers.items()}
            )
            self.send_response(status)
            self.send_header("content-type", "text/plain")
            self.end_headers()
            self.wfile.write(text.encode())

        def log_message(self, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


# ── Paylane's replay ─────────────────────────────────────────────────────────


def replay(provider_dir: Path, stuck_items: list[str], url: str) -> dict[str, int]:
    """Re-send webhooks for the given items, signed exactly as Paylane signs
    today (primary = new secret, secondary = old)."""
    signing = json.loads((provider_dir / "signing.json").read_text())["headers"]
    paid = {
        psi.item(r["reference"], int(r["amount_kobo"])): r
        for r in read_csv(provider_dir / "payments.csv")
    }
    delivered = rejected = 0
    with httpx.Client(timeout=10) as http:
        for it in stuck_items:
            row = paid[it]
            body = webhook_body(row["reference"], int(row["amount_kobo"]), row["paid_at"])
            resp = http.post(url, content=body, headers={
                "content-type": "application/json",
                "X-Sig-Primary": sign(body, signing["X-Sig-Primary"]["secret"]),
                "X-Sig-Secondary": sign(body, signing["X-Sig-Secondary"]["secret"]),
            })
            if resp.status_code == 200:
                delivered += 1
            else:
                rejected += 1
    return {"attempted": len(stuck_items), "delivered": delivered, "rejected": rejected}


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m airlock.sim")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("generate").add_argument("out", type=Path)
    r = sub.add_parser("reset")
    r.add_argument("src", type=Path)
    r.add_argument("dst", type=Path)
    s = sub.add_parser("serve")
    s.add_argument("merchant_dir", type=Path)
    s.add_argument("--port", type=int, default=8787)
    sub.add_parser("fix").add_argument("merchant_dir", type=Path)
    args = ap.parse_args()
    if args.cmd == "generate":
        print(json.dumps(generate(args.out)))
    elif args.cmd == "reset":
        reset(args.src, args.dst)
    elif args.cmd == "serve":
        serve(args.merchant_dir, args.port)
        print(f"KudiMart webhook endpoint on http://127.0.0.1:{args.port}{ENDPOINT_PATH}")
        threading.Event().wait()
    elif args.cmd == "fix":
        print(f"deployed {FIX_VERSION} to {CANARY} at {deploy_fix(args.merchant_dir)}")


if __name__ == "__main__":
    main()
