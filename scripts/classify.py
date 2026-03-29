"""
Ask the LLM to assign a theme and tags to each unclassified item.
Themes are discovered dynamically from the content — the LLM can invent
new themes as needed. Existing themes are passed as context so related
stories are grouped consistently.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import yaml
from src import db, llm


def _load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


_SYSTEM = """You are a news classification assistant.
Given a news article title and summary, return a JSON object with exactly two keys:
- "theme": a short theme label (2-4 words, title case, e.g. "AI & Machine Learning", "UK Politics", "Cybersecurity", "Space Exploration")
- "tags": a list of 2-5 lowercase keyword tags

Respond with valid JSON only. No prose, no markdown fences."""


def _classify_item(title: str, summary: str, existing_themes: list[str]) -> tuple[str, list[str]]:
    themes_hint = ""
    if existing_themes:
        themes_hint = f"\nExisting themes (prefer these if appropriate): {', '.join(existing_themes)}"

    prompt = f"Title: {title}\nSummary: {summary[:400]}{themes_hint}"
    try:
        raw = llm.complete(prompt, system=_SYSTEM, max_tokens=120, temperature=0.1)
        # Strip any accidental markdown fences
        raw = raw.strip().strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        data = json.loads(raw)
        theme = str(data.get("theme", "General")).strip()
        tags = [str(t).lower().strip() for t in data.get("tags", [])][:5]
        return theme, tags
    except Exception as e:
        print(f"[classify] Parse error ({e}) for: {title[:50]}")
        return "General", []


def run() -> int:
    config = _load_config()
    db.init_db()
    retention = config["settings"]["retention_days"]

    items = db.get_unclassified(limit=80)
    if not items:
        print("[classify] Nothing to classify")
        return 0

    existing_themes = db.get_themes(days=retention)
    print(f"[classify] Classifying {len(items)} items (known themes: {len(existing_themes)})")

    for row in items:
        theme, tags = _classify_item(
            row["title"],
            row["summary"] or row["content"] or "",
            existing_themes,
        )
        db.update_theme(row["id"], theme, tags)
        # Add to existing themes so later items in this batch can reuse it
        if theme not in existing_themes:
            existing_themes.append(theme)
        print(f"[classify]   [{theme}] {row['title'][:55]}")

    return len(items)


if __name__ == "__main__":
    run()
