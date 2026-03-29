"""
Render Jinja2 templates into docs/ to produce the static GitHub Pages site.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import yaml
from jinja2 import Environment, FileSystemLoader
from src import db

TEMPLATES_DIR = ROOT / "templates"
DOCS_DIR = ROOT / "docs"


def _load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def _row_to_dict(row) -> dict:
    d = dict(row)
    tags_raw = d.get("tags") or "[]"
    try:
        d["tags"] = json.loads(tags_raw) if isinstance(tags_raw, str) else tags_raw
    except Exception:
        d["tags"] = []
    # Normalise published_at to a readable string
    pub = d.get("published_at")
    if isinstance(pub, str) and pub:
        try:
            pub = datetime.fromisoformat(pub.replace("Z", "+00:00"))
        except Exception:
            pub = None
    d["published_at"] = pub
    return d


def run() -> None:
    config = _load_config()
    db.init_db()

    retention = config["settings"]["retention_days"]
    site_title = config["settings"].get("site_title", "Newsfeed")

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    env.filters["datefmt"] = lambda dt, fmt="%d %b %Y %H:%M": (
        dt.strftime(fmt) if isinstance(dt, datetime) else (dt or "")
    )

    now = datetime.now(timezone.utc)
    digest_row = db.get_latest_digest()
    digest = dict(digest_row) if digest_row else {"summary": "", "created_at": None}

    # --- feed.html — chronological raw feed ---
    all_items = [_row_to_dict(r) for r in db.get_all_recent_items(days=retention)]
    feed_tmpl = env.get_template("feed.html")
    (DOCS_DIR / "feed.html").write_text(
        feed_tmpl.render(
            site_title=site_title,
            items=all_items,
            now=now,
            digest=digest,
        ),
        encoding="utf-8",
    )

    # --- index.html — themes + digest ---
    themes = db.get_themes(days=retention)
    themed = {
        theme: [_row_to_dict(r) for r in db.get_items_by_theme(theme, days=retention)]
        for theme in themes
    }
    # Items not yet classified go in a catch-all
    unclassified = [
        _row_to_dict(r) for r in db.get_all_recent_items(days=retention)
        if not r["theme"]
    ]

    index_tmpl = env.get_template("index.html")
    (DOCS_DIR / "index.html").write_text(
        index_tmpl.render(
            site_title=site_title,
            digest=digest,
            themed=themed,
            unclassified=unclassified,
            now=now,
            audio_exists=(DOCS_DIR / "audio" / "summary.ogg").exists(),
        ),
        encoding="utf-8",
    )

    print(f"[build] Site written to {DOCS_DIR} ({len(all_items)} items, {len(themes)} themes)")


if __name__ == "__main__":
    run()
