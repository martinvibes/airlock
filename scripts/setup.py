"""Set up Airlock on a Switch server: two owners, four agents, three rooms.

Everything goes through Switch's own API, so each company's agents really are
owned by that company's Switch user:

    KudiMart engineer  owns  kudimart-customs, kudimart-investigator
    Paylane engineer   owns  paylane-customs,  paylane-investigator
    host admin         owns  airlock (the shared room)

Writes state/airlock.json (credentials and ids; gitignored) and resets the
live data folders state/kudimart and state/paylane from data/.

    SWITCH_URL=http://localhost:8000 SWITCH_ADMIN_EMAIL=... SWITCH_ADMIN_PASSWORD=... \
        uv run python scripts/setup.py [--mattermost] [--suffix=-2]

With --mattermost the three rooms are also Mattermost channels, and each
engineer gets a Mattermost account linked to their Switch user (confirmed
with that account's own session, as Switch requires). Needs
MATTERMOST_ADMIN_USER and MATTERMOST_ADMIN_PASSWORD (Switch's .env has them).
The bundled Mattermost user that Switch adds to every channel it creates is
taken out of the two private channels.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from airlock import sim  # noqa: E402
from airlock.mattermost import Mattermost  # noqa: E402
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

# The Airlock door, on Customs (the gatekeepers). Switch only takes public https
# links, so this shows once the repo is public; until then Switch draws its own.
CUSTOMS_ICON = "https://raw.githubusercontent.com/martinvibes/airlock/main/assets/logo/airlock-avatar.png"

AIRLOCK_INSTRUCTIONS = (
    "Shared room between KudiMart and Paylane. Only the two Customs agents carry information "
    "across, as typed AIRLOCK/1 claims released by an engineer. Customs refuses free text. "
    "Investigators are not members of this room."
)


def private_instructions(company: str) -> str:
    return (ROOT / "agents" / f"{company}-investigator.md").read_text()


def set_icons(state: dict) -> None:
    for co, c in state["companies"].items():
        gw = c.get("_gw")
        if gw is None:
            gw = Gateway(state["switch_url"])
            gw.login(c["user"]["email"], c["user"]["password"])
        try:
            gw.set_agent_icon(c["agents"]["customs"]["id"], CUSTOMS_ICON)
        except SwitchError as e:
            print(f"warning: could not set {c['agents']['customs']['name']}'s icon: {e}")


def mm_avatars(state: dict, mm_admin: Mattermost) -> None:
    """Give the Customs bots the logo in Mattermost directly. Switch does the same
    from CUSTOMS_ICON once that URL is public; this covers a private checkout."""
    png = (ROOT / "assets" / "logo" / "airlock-avatar.png").read_bytes()
    for c in state["companies"].values():
        name = c["agents"]["customs"]["name"]
        try:
            mm_admin.set_avatar(mm_admin.user_by_username(name)["id"], png)
        except RuntimeError as e:
            print(f"warning: could not set {name}'s Mattermost avatar: {e}")


def mm_admin_from_env(url: str) -> Mattermost | None:
    if not os.environ.get("MATTERMOST_ADMIN_USER"):
        return None
    mm = Mattermost(url)
    mm.login(os.environ["MATTERMOST_ADMIN_USER"], os.environ["MATTERMOST_ADMIN_PASSWORD"])
    return mm


def mm_password() -> str:
    return secrets.token_urlsafe(14) + "Aa1!"


def link_mattermost(gw: Gateway, mm_url: str, bridge: str, username: str, password: str, ext_id: str) -> None:
    """Claim the Mattermost account for this Switch user, then confirm the claim
    with the account's own session. Until confirmed, the link counts for nothing."""
    for _ in range(60):
        found = gw.directory(bridge, username).get("users", [])
        if any(u["external_user_id"] == ext_id for u in found):
            break
        time.sleep(1)
    else:
        sys.exit(f"Mattermost bridge never listed {username}")
    ident = gw.claim_identity(bridge, ext_id, username)
    if ident.get("link_request") is None:
        return
    mm = Mattermost(mm_url)
    mm.login(username, password)
    try:
        gw.verify_identity(bridge, ident["id"], mm.token or "")
    finally:
        mm.logout()


def channel_name(room: dict) -> str:
    url = room.get("external_channel_url") or ""
    name = urlparse(url).path.rsplit("/", 1)[-1]
    if not name:
        sys.exit(f"room {room.get('name')} has no Mattermost channel")
    return name


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mattermost", action="store_true", help="mirror the rooms into Mattermost")
    ap.add_argument("--mattermost-bridge", help="bridge id (default: Switch's default Mattermost bridge)")
    ap.add_argument("--suffix", default="", help="append to every name (for repeated runs on one server)")
    ap.add_argument("--icons-only", action="store_true",
                    help="only (re)set the Customs icons for the agents in state/airlock.json")
    args = ap.parse_args()
    if args.icons_only:
        state = json.loads(STATE_FILE.read_text())
        set_icons(state)
        mm = mm_admin_from_env(state["mattermost"]["url"]) if "mattermost" in state else None
        if mm is not None:
            mm_avatars(state, mm)
        print("icons set")
        return

    base = os.environ.get("SWITCH_URL", "http://localhost:8000")
    sfx = args.suffix
    admin = Gateway(base)
    admin.login(os.environ["SWITCH_ADMIN_EMAIL"], os.environ["SWITCH_ADMIN_PASSWORD"])

    STATE.mkdir(exist_ok=True)
    state: dict = {"switch_url": base, "suffix": sfx, "companies": {}}

    bridge = args.mattermost_bridge
    mm_admin = None
    if args.mattermost or bridge:
        if not bridge:
            bridge = next((b["bridge_id"] for b in admin.bridges()
                           if b.get("bridge_type") == "mattermost" and b.get("is_default")), None)
            if not bridge:
                sys.exit("no default Mattermost bridge on this Switch server")
        mm_url = os.environ.get("MATTERMOST_URL", "http://localhost:8065")
        mm_admin = Mattermost(mm_url)
        mm_admin.login(os.environ["MATTERMOST_ADMIN_USER"], os.environ["MATTERMOST_ADMIN_PASSWORD"])
        team = mm_admin.team(os.environ.get("MATTERMOST_TEAM_NAME", "switch"))
        state["mattermost"] = {"url": mm_url, "team": team["name"], "bridge_id": bridge}

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

        if mm_admin is not None:
            username, mpw = f"{co}-eng{sfx}", mm_password()
            mu = mm_admin.create_user(username, f"{co}-eng{sfx}@airlock.example.com", mpw,
                                      meta["title"], "Engineer")
            mm_admin.add_to_team(team["id"], mu["id"])
            link_mattermost(gw, state["mattermost"]["url"], bridge, username, mpw, mu["id"])
            state["companies"][co]["mattermost"] = {"username": username, "password": mpw, "user_id": mu["id"]}
            print(f"{meta['title']}: Mattermost account {username}, linked to {email}")

    # 4. Rooms. Each company creates its own private room; the host creates airlock.
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

    if mm_admin is not None:
        # Each engineer into their own channels; the bundled default member out
        # of the private ones. Then check: who is in each channel.
        default = mm_admin.user_by_username(os.environ.get("MATTERMOST_USER", "user"))
        chans = {}
        for co in COMPANIES:
            c = state["companies"][co]
            ch = mm_admin.channel(team["id"], channel_name(c["_gw"].room(c["private_room"])))
            mm_admin.add_to_channel(ch["id"], c["mattermost"]["user_id"])
            if any(m["user_id"] == default["id"] for m in mm_admin.members(ch["id"])):
                mm_admin.remove_from_channel(ch["id"], default["id"])
            chans[co] = ch
        ch = mm_admin.channel(team["id"], channel_name(admin.room(air["id"])))
        for co in COMPANIES:
            mm_admin.add_to_channel(ch["id"], state["companies"][co]["mattermost"]["user_id"])
        chans["airlock"] = ch
        state["mattermost"]["channels"] = {k: {"id": v["id"], "name": v["name"]} for k, v in chans.items()}
        for k, v in chans.items():
            print(f"Mattermost channel {v['name']}: {len(mm_admin.members(v['id']))} members")

    set_icons(state)
    if mm_admin is not None:
        mm_avatars(state, mm_admin)

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
        if mm_admin is not None:
            mm = Mattermost(state["mattermost"]["url"])
            mm.login(c["mattermost"]["username"], c["mattermost"]["password"])
            for key in (co, "airlock"):
                n = secrets.token_hex(6)
                mm.post(state["mattermost"]["channels"][key]["id"], f"airlock pairing {n}")
                nonces[n] = (co, "engineer")
            mm.logout()
    time.sleep(3 if mm_admin is not None else 0)  # let the bridge deliver
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
                        # The same rule Customs applies: a platform message speaks
                        # for the person it names, everything else for its sender.
                        sid = ev.get("on_behalf_of") if ev.get("sender_kind") == "platform" else None
                        sid = sid or ev["sender"]
                        if sid not in ids:
                            ids.append(sid)
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
    if mm_admin is not None:
        print(f"\nMattermost ({state['mattermost']['url']}), synthetic accounts for this demo:")
        for co in COMPANIES:
            m = state["companies"][co]["mattermost"]
            print(f"  {m['username']:<20} {m['password']}")


if __name__ == "__main__":
    main()
