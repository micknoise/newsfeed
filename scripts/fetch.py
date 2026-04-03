"""
Fetch all RSS feeds, store new items in DB, then fetch article text
and generate LLM summaries for each new item.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import yaml
from src import db, llm, rss, web


def _load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def _summarize_item(item_row, max_chars: int) -> tuple[str, str]:
    """Fetch article text and ask the LLM for a 2-3 sentence summary.
    Returns (content, summary)."""
    content = web.fetch_article_text(item_row["url"], max_chars=max_chars)
    source_text = content or item_row["content"] or item_row["title"]

    if not source_text.strip():
        return "", item_row["title"]

    prompt = (
        f"Summarise the following article in 2-3 concise sentences. "
        f"Focus on the key facts. Do not start with 'This article'.\n\n"
        f"Title: {item_row['title']}\n\n"
        f"{source_text[:4000]}"
    )
    try:
        summary = llm.complete(prompt, max_tokens=200)
    except Exception as e:
        print(f"[fetch] LLM summary failed for '{item_row['title']}': {e}")
        summary = source_text[:300]

    return content, summary


def run() -> int:
    config = _load_config()
    db.init_db()

    # 1. Fetch all RSS feeds
    items = rss.fetch_all(config)
    new_count = 0
    for item in items:
        added = db.add_item(
            guid=item["guid"],
            feed_label=item["feed_label"],
            title=item["title"],
            url=item["url"],
            published_at=item["published_at"],
            raw_description=item["description"],
        )
        if added:
            new_count += 1

    print(f"[fetch] {len(items)} total items, {new_count} new")

    # 2. Remove items older than retention window
    removed = db.cleanup_old_items(days=config["settings"]["retention_days"])
    if removed:
        print(f"[fetch] Removed {removed} expired items")

    # 3. Summarize new (unsummarized) items
    max_chars = config.get("settings", {}).get("max_article_chars", 6000)
    to_summarize = db.get_unsummarized(limit=60)
    print(f"[fetch] Summarizing {len(to_summarize)} items...")

    for row in to_summarize:
        content, summary = _summarize_item(row, max_chars)
        db.update_summary(row["id"], content, summary)
        print(f"[fetch]   ✓ {row['title'][:60]}")

    return new_count


if __name__ == "__main__":
    run()
