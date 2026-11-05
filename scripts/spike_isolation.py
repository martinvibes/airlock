"""Isolation spike: prove Switch keeps an investigator out of the airlock.

Creates two owners, four custom agents and three rooms on a real Switch
server, then checks who receives what. Run against a fresh local server:

    SWITCH_URL=http://localhost:8000 SWITCH_ADMIN_EMAIL=... SWITCH_ADMIN_PASSWORD=... \
        uv run python scripts/spike_isolation.py
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from airlock.switch_client import (  # noqa: E402
    AgentClient,
    Gateway,
    SwitchError,
    register_agent,
    run_in_thread,
)

BASE = os.environ.get("SWITCH_URL", "http://localhost:8000")
SFX = secrets.token_hex(2)
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  ({detail})" if detail else ""))


def expect_error(name: str, fn, status: tuple[int, ...] = (403, 404)) -> None:
    try:
        fn()
    except SwitchError as e:
        check(name, e.status in status, f"{e.status} {e.detail[:120]}")
        return
    check(name, False, "call succeeded")


def main() -> None:
    admin = Gateway(BASE)
    admin.login(os.environ["SWITCH_ADMIN_EMAIL"], os.environ["SWITCH_ADMIN_PASSWORD"])

    people = {}
    for co in ("kudimart", "paylane"):
        email = f"{co}-eng-{SFX}@example.com"
        pw = secrets.token_urlsafe(12)
        user = admin.create_user(f"{co.title()} Engineer {SFX}", email, pw)
        gw = Gateway(BASE)
        gw.login(email, pw)
        people[co] = {"user": user, "gw": gw, "key": gw.create_registration_key(f"{co}-{SFX}")}
    check("two separate owners", people["kudimart"]["user"]["id"] != people["paylane"]["user"]["id"])

    agents = {}
    for co in ("kudimart", "paylane"):
        for role in ("customs", "investigator"):
            name = f"{co}-{role}-{SFX}"
            aid, key = register_agent(BASE, people[co]["key"], name, f"spike {role}")
            agents[f"{co}-{role}"] = AgentClient(BASE, aid, key)
    check("registered 4 custom agents", len(agents) == 4)

    kgw, pgw = people["kudimart"]["gw"], people["paylane"]["gw"]
    kroom = kgw.create_room(
        f"kudimart-war-room-{SFX}", "KudiMart private",
        agent_ids=[agents["kudimart-customs"].agent_id, agents["kudimart-investigator"].agent_id],
    )
    proom = pgw.create_room(
        f"paylane-war-room-{SFX}", "Paylane private",
        agent_ids=[agents["paylane-customs"].agent_id, agents["paylane-investigator"].agent_id],
    )
    kgw.add_member(kroom["id"], people["kudimart"]["user"]["id"])
    pgw.add_member(proom["id"], people["paylane"]["user"]["id"])
    check("each owner created a private room with its own agents", True)
    expect_error("paylane engineer cannot post in kudimart's private room",
                 lambda: pgw.post(kroom["id"], "peek"))

    # Who can put the peer's Customs into a shared room?
    try:
        air = kgw.create_room(
            f"airlock-{SFX}", "Shared",
            agent_ids=[agents["kudimart-customs"].agent_id, agents["paylane-customs"].agent_id],
        )
        check("owner can add the peer's agent to a room (noting)", True, "allowed")
    except SwitchError as e:
        print(f"note: owner could not add peer agent: {e.status} {e.detail[:150]}")
        air = admin.create_room(
            f"airlock-{SFX}", "Shared",
            agent_ids=[agents["kudimart-customs"].agent_id, agents["paylane-customs"].agent_id],
        )
        check("host admin created airlock with both Customs", True)
    kid, pid, aid = kroom["id"], proom["id"], air["id"]
    for co in ("kudimart", "paylane"):
        try:
            admin.add_member(aid, people[co]["user"]["id"])
        except SwitchError as e:
            print(f"note: add_member {co}: {e.status} {e.detail[:150]}")
    print("airlock members:", json.dumps(kgw.members(aid))[:700])

    # Streams
    seen: dict[str, list] = {k: [] for k in agents}
    lock = threading.Lock()

    def recorder(key):
        def h(ev):
            with lock:
                seen[key].append(ev)
        return h

    run_in_thread(agents["kudimart-customs"], [kid, aid], recorder("kudimart-customs"))
    run_in_thread(agents["paylane-customs"], [pid, aid], recorder("paylane-customs"))
    run_in_thread(agents["kudimart-investigator"], [kid], recorder("kudimart-investigator"), scope="single")
    run_in_thread(agents["paylane-investigator"], [pid], recorder("paylane-investigator"), scope="single")
    time.sleep(3)

    inv = agents["kudimart-investigator"]
    expect_error("investigator cannot open a stream on airlock",
                 lambda: AgentClient(BASE, inv.agent_id, inv.http.headers["Authorization"][7:])._open([aid], "single", "all"),
                 (403, 409))
    expect_error("investigator cannot post into airlock", lambda: inv.post(aid, "leak"))
    expect_error("investigator cannot read airlock history", lambda: inv.history(aid))
    expect_error("investigator cannot post into the other company's room", lambda: inv.post(pid, "hi"))

    marker = f"AIRLOCK/1 spike-{SFX}"
    agents["paylane-customs"].post(aid, marker)
    kgw.post(kid, f"hello from kudimart engineer {SFX}")
    agents["kudimart-investigator"].post(kid, f"investigator note {SFX}")
    time.sleep(4)

    def bodies(key):
        return [e.payload.get("body", "") for e in seen[key] if e.type == "message"]

    check("kudimart-customs received the airlock post", any(marker in b for b in bodies("kudimart-customs")))
    check("kudimart-investigator did NOT receive the airlock post", not any(marker in b for b in bodies("kudimart-investigator")))
    check("paylane-investigator did NOT receive the airlock post", not any(marker in b for b in bodies("paylane-investigator")))
    check("paylane-customs did NOT receive kudimart private messages",
          not any(SFX in b and "kudimart engineer" in b for b in bodies("paylane-customs")))
    human = [e for e in seen["kudimart-customs"] if e.type == "message" and "kudimart engineer" in e.payload.get("body", "")]
    check("kudimart-customs received the engineer's private message", bool(human))
    if human:
        print("human message payload:", json.dumps(human[0].raw)[:900])
    invmsg = [e for e in seen["kudimart-customs"] if e.type == "message" and "investigator note" in e.payload.get("body", "")]
    if invmsg:
        print("investigator message payload:", json.dumps(invmsg[0].raw)[:700])

    ops = agents["kudimart-customs"].ops()
    for name in ("create_room_document", "load_internal_documents", "connect_to_room", "post_message", "read_context", "list_participants"):
        if name in ops:
            print(f"op {name}: {json.dumps(ops[name]['input_schema'].get('properties', {}))[:400]}")

    state = {
        "suffix": SFX,
        "rooms": {"kudimart": kid, "paylane": pid, "airlock": aid},
        "agents": {k: v.agent_id for k, v in agents.items()},
        "users": {co: people[co]["user"]["id"] for co in people},
    }
    print("state:", json.dumps(state))
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    for a in agents.values():
        a.stop()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
