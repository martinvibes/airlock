"""Run all of Airlock against a Switch server set up by scripts/setup.py.

    uv run python scripts/up.py --reset            # fresh incident, everything running
    uv run python scripts/up.py --no-investigators  # Customs only (drive investigators yourself)

Starts, in one process:
- KudiMart's webhook endpoint (where Paylane's replay lands),
- kudimart-customs and paylane-customs (code, no model),
- kudimart-investigator and paylane-investigator (headless Claude Code, read-only,
  each in its own company's folder).

Ctrl-C stops everything.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from airlock import agent, sim  # noqa: E402
from airlock.investigator import Investigator  # noqa: E402

COMPANIES = {"kudimart": "merchant", "paylane": "provider"}


def reset(state: dict) -> None:
    for co, data in COMPANIES.items():
        ws = Path(state["companies"][co]["workspace"])
        sim.reset(ROOT / "data" / data, ws)
        shutil.copy(ROOT / "agents" / f"{co}-investigator.md", ws / "CLAUDE.md")
        (ROOT / "state" / f"{co}-investigator-session.txt").unlink(missing_ok=True)
    print("reset: both companies' data restored, investigator sessions cleared")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="restore the synthetic incident data first")
    ap.add_argument("--no-investigators", action="store_true")
    ap.add_argument("--model", default=os.environ.get("AIRLOCK_INVESTIGATOR_MODEL"))
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    state = json.loads((ROOT / "state" / "airlock.json").read_text())
    if args.reset:
        reset(state)
    server = sim.serve(Path(state["companies"]["kudimart"]["workspace"]), args.port)
    url = f"http://127.0.0.1:{args.port}{sim.ENDPOINT_PATH}"
    stop = threading.Event()
    threads = [threading.Thread(target=agent.run, args=(co, state, url, stop), daemon=True)
               for co in COMPANIES]
    if not args.no_investigators:
        threads += [threading.Thread(target=Investigator(co, state, model=args.model).run, args=(stop,),
                                     daemon=True) for co in COMPANIES]
    for t in threads:
        t.start()
    sfx = state.get("suffix", "")
    print(f"\nAirlock is up on {state['switch_url']}. Webhook endpoint {url}")
    print(f"Rooms: kudimart-war-room{sfx}, paylane-war-room{sfx}, airlock{sfx}. Ctrl-C to stop.\n")
    try:
        stop.wait()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        stop.set()
        server.shutdown()


if __name__ == "__main__":
    main()
