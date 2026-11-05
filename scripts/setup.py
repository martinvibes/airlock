"""Set up Airlock on a Switch server: two owners, four agents, three rooms.

Everything goes through Switch's own API, so each company's agents really are
owned by that company's Switch user:

    KudiMart engineer  owns  kudimart-customs, kudimart-investigator
    Paylane engineer   owns  paylane-customs,  paylane-investigator
    host admin         owns  airlock (the shared room)

Writes state/airlock.json (credentials and ids; gitignored) and resets the
live data folders state/kudimart and state/paylane from data/.

    SWITCH_URL=http://localhost:8000 SWITCH_ADMIN_EMAIL=... SWITCH_ADMIN_PASSWORD=... \
        uv run python scripts/setup.py [--mattermost-bridge <bridge_id>]
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from airlock import sim  # noqa: E402
from airlock.switch_client import (  # noqa: E402
    AgentClient,
    Gateway,
    SwitchError,
    register_agent,
    register_known,
)

STATE = ROOT / "state"
STATE_FILE = STATE / "airlock.json"

COMPANIES = {
    "kudimart": {"title": "KudiMart", "party": "merchant", "data": "merchant", "peer": "paylane"},
    "paylane": {"title": "Paylane", "party": "provider", "data": "provider", "peer": "kudimart"},
}

AIRLOCK_INSTRUCTIONS = (
    "Shared room between KudiMart and Paylane. Only the two Customs agents carry information "
    "across, as typed AIRLOCK/1 claims released by an engineer. Customs refuses free text. "
    "Investigators are not members of this room."
)


def private_instructions(company: str) -> str:
    return (ROOT / "agents" / f"{company}-investigator.md").read_text()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mattermost-bridge", help="bridge id to mirror rooms into Mattermost")
    ap.add_argument("--suffix", default="", help="append to every name (for repeated runs on one server)")
    args = ap.parse_args()

    base = os.environ.get("SWITCH_URL", "http://localhost:8000")
    sfx = args.suffix
    admin = Gateway(base)
    admin.login(os.environ["SWITCH_ADMIN_EMAIL"], os.environ["SWITCH_ADMIN_PASSWORD"])

    STATE.mkdir(exist_ok=True)
    state: dict = {"switch_url": base, "suffix": sfx, "companies": {}}

    # 1. Live data folders = investigator workspaces. Each holds only its own company's files.
    for co, meta in COMPANIES.items():
        ws = STATE / co
        sim.reset(ROOT / "data" / meta["data"], ws)
        shutil.copy(ROOT / "agents" / f"{co}-investigator.md", ws / "CLAUDE.md")

    # 2. One Switch user per company, each minting its own registration key.
    for co, meta in COMPANIES.items():
        email = f"{co}-engineer{sfx}@airlock.example.com"
        password = secrets.token_urlsafe(16)
        try:
            user = admin.create_user(f"{meta['title']} Engineer", email, password)
        except SwitchError as e:
            if e.status != 409:
                raise
            sys.exit(f"{email} already exists on this server. Use --suffix, or reset Switch's database.")
        gw = Gateway(base)
        gw.login(email, password)
        key = gw.create_registration_key(f"airlock-{co}{sfx}")
        state["companies"][co] = {
            "party": meta["party"],
            "user": {"id": user["id"], "name": user["name"], "email": email, "password": password},
            "workspace": str(STATE / co),
        }
        # 3. Agents, registered with that user's key, so that user owns them.
        agents = {}
        cname = f"{co}-customs{sfx}"
        aid, akey = register_agent(base, key, cname, f"{meta['title']} Customs: typed claims only, no model",
                                   display_name=f"{meta['title']} Customs")
        agents["customs"] = {"id": aid, "name": cname, "api_key": akey}
        iname = f"{co}-investigator{sfx}"
        iid, ikey = register_known(base, key, "claude-code", iname,
                                   f"{meta['title']} investigator: reads only {meta['title']}'s data",
                                   display_name=f"{meta['title']} Investigator",
                                   options={"repo_dir": str(STATE / co)})
        agents["investigator"] = {"id": iid, "name": iname, "api_key": ikey}
        state["companies"][co]["agents"] = agents
        state["companies"][co]["_gw"] = gw
        print(f"{meta['title']}: user {email}, agents {cname}, {iname}")

    # 4. Rooms. Each company creates its own private room; the host creates airlock.
    bridge = args.mattermost_bridge
    for co, meta in COMPANIES.items():
        c = state["companies"][co]
        gw = c["_gw"]
        room = gw.create_room(
            f"{co}-war-room{sfx}", f"{meta['title']} private investigation",
            instructions=private_instructions(co),
            agent_ids=[c["agents"]["customs"]["id"], c["agents"]["investigator"]["id"]],
            internal_only=bridge is None, bridge_id=bridge,
        )
        gw.add_member(room["id"], c["user"]["id"])
        c["private_room"] = room["id"]
    air = admin.create_room(
        f"airlock{sfx}", "Shared room: typed claims only", instructions=AIRLOCK_INSTRUCTIONS,
        agent_ids=[state["companies"][co]["agents"]["customs"]["id"] for co in COMPANIES],
        internal_only=bridge is None, bridge_id=bridge,
    )
    for co in COMPANIES:
        admin.add_member(air["id"], state["companies"][co]["user"]["id"])
    state["airlock_room"] = air["id"]

    # 5. Addressing policies, set by each owner. Customs answers its own people in
    # its room, anyone in airlock (so it can refuse visibly), and the peer Customs.
    for co, meta in COMPANIES.items():
        c, peer = state["companies"][co], state["companies"][meta["peer"]]
        gw = c["_gw"]
        gw.set_addressing_policy(c["agents"]["customs"]["id"], [
            {"rooms": [c["private_room"]], "users": [c["user"]["id"]],
             "agents": [c["agents"]["investigator"]["id"]], "owner": True},
            {"rooms": [air["id"]], "users": "*", "agents": [peer["agents"]["customs"]["id"]], "owner": True},
        ])
        gw.set_addressing_policy(c["agents"]["investigator"]["id"], [
            {"rooms": [c["private_room"]], "users": [c["user"]["id"]],
             "agents": [c["agents"]["customs"]["id"]], "owner": True},
        ])

    # 6. Pair identities. Every participant posts a one-time nonce; the sender id
    # Switch attaches to that message is recorded. Customs later trusts these
    # ids, which come from Switch, never names or message text.
    nonces = {}
    for co in COMPANIES:
        c = state["companies"][co]
        for room in (c["private_room"], air["id"]):
            n = secrets.token_hex(6)
            c["_gw"].post(room, f"airlock pairing {n}")
            nonces[n] = (co, "engineer")
            n = secrets.token_hex(6)
            AgentClient(base, c["agents"]["customs"]["id"], c["agents"]["customs"]["api_key"]).post(
                room, f"airlock pairing {n}")
            nonces[n] = (co, "customs")
        n = secrets.token_hex(6)
        AgentClient(base, c["agents"]["investigator"]["id"], c["agents"]["investigator"]["api_key"]).post(
            c["private_room"], f"airlock pairing {n}")
        nonces[n] = (co, "investigator")
    for co in COMPANIES:
        state["companies"][co]["participants"] = {"engineer": [], "customs": [], "investigator": []}
    for co in COMPANIES:
        c = state["companies"][co]
        reader = AgentClient(base, c["agents"]["customs"]["id"], c["agents"]["customs"]["api_key"])
        for room in (c["private_room"], air["id"]):
            for ev in reader.history(room)["events"]:
                body = ev.get("body", "")
                if body.startswith("airlock pairing "):
                    who = nonces.get(body.split()[-1])
                    if who:
                        ids = state["companies"][who[0]]["participants"][who[1]]
                        if ev["sender"] not in ids:
                            ids.append(ev["sender"])
    for co in COMPANIES:
        for role, ids in state["companies"][co]["participants"].items():
            if not ids:
                sys.exit(f"pairing failed: no participant id for {co} {role}")
        print(f"{co} participants: {state['companies'][co]['participants']}")

    for c in state["companies"].values():
        c.pop("_gw")
    STATE_FILE.write_text(json.dumps(state, indent=2))
    print(f"rooms: kudimart-war-room{sfx}, paylane-war-room{sfx}, airlock{sfx}")
    print(f"wrote {STATE_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
