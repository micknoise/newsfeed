"""
Orchestrator — called by cron every hour.
Runs the full pipeline: fetch → classify → summarise → build site.
"""

import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


def _step(name: str, fn):
    start = time.time()
    print(f"\n{'='*50}")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {name}")
    print("="*50)
    try:
        result = fn()
        elapsed = time.time() - start
        print(f"[{name}] done in {elapsed:.1f}s → {result}")
        return result
    except Exception as e:
        elapsed = time.time() - start
        print(f"[{name}] ERROR after {elapsed:.1f}s: {e}")
        return None


def main():
    print(f"\n{'#'*50}")
    print(f"# Newsfeed update — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*50}")

    from scripts.fetch import run as fetch_run
    from scripts.classify import run as classify_run
    from scripts.summarise import run as summarise_run
    from scripts.make_audio import run as audio_run
    from scripts.build_site import run as build_run

    _step("Fetch RSS feeds", fetch_run)
    _step("Classify items", classify_run)
    _step("Generate digest + audio", summarise_run)
    _step("Generate per-article audio", audio_run)
    _step("Build static site", build_run)

    print(f"\n[run_all] Update complete — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


if __name__ == "__main__":
    main()
