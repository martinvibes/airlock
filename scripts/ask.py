"""Post as a company's engineer and print what comes back. For trying things by hand.

    uv run python scripts/ask.py kudimart "@investigator what's failing?"
    uv run python scripts/ask.py kudimart "release 1"
    uv run python scripts/ask.py paylane --room airlock "hello"
    uv run python scripts/ask.py kudimart --watch 120        # just print the room

`@investigator` and `@customs` are expanded to the company's real agent names.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from airlock.switch_client import AgentClient, Gateway  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("company", choices=["kudimart", "paylane"])
    ap.add_argument("text", nargs="?")
    ap.add_argument("--room", choices=["private", "airlock"], default="private")
    ap.add_argument("--watch", type=float, default=90, help="seconds to keep printing replies")
    ap.add_argument("--until", help="stop once a message contains this text")
    args = ap.parse_args()

    state = json.loads((ROOT / "state" / "airlock.json").read_text())
    c = state["companies"][args.company]
    room = c["private_room"] if args.room == "private" else state["airlock_room"]
    names = {n: c["agents"][n] for n in ("investigator", "customs")}
    reader = AgentClient(state["switch_url"], c["agents"]["customs"]["id"], c["agents"]["customs"]["api_key"])
    since = (datetime.now(UTC) - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    if args.text:
        text, mention = args.text, []
        for short, a in names.items():
            if f"@{short}" in text:
                text = text.replace(f"@{short}", f"@{a['name']}")
                mention.append(a["id"])
        gw = Gateway(state["switch_url"])
        gw.login(c["user"]["email"], c["user"]["password"])
        gw.post(room, text, mention_agent_ids=mention)

    seen: set[str] = set()
    end = time.time() + args.watch
    while time.time() < end:
        for ev in reader.history(room, limit=200, since=since)["events"]:
            key = f"{ev.get('timestamp')}{ev.get('body')}"
            if key in seen:
                continue
            seen.add(key)
            print(f"\n[{ev.get('sender_name') or ev.get('sender')}] {ev.get('body')}", flush=True)
            if args.until and args.until in (ev.get("body") or ""):
                return
        time.sleep(1)


if __name__ == "__main__":
    main()
