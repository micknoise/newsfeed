"""
Fetch all RSS feeds, store new items in DB, then fetch article text
and generate grounded LLM summaries for each new item.

Summaries are only ever produced from real source text. If an article body
can't be retrieved and the feed gives us nothing but a headline, we do NOT
ask the LLM to "summarise" it — that is exactly the situation that produces
invented news. Instead we fall back to the feed's own text, or to nothing.
When enabled, every LLM summary is additionally checked back against the
source text and discarded if it asserts anything the source doesn't support.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import yaml
from src import db, llm, rss, web

# Sentinel the model is told to emit when the source text is too thin.
NO_SUMMARY = "NO_SUMMARY"

_SUMMARY_SYSTEM = (
    "You summarise news articles. You may only use information that appears "
    "verbatim in the source text provided by the user. You must not add "
    "background, context, consequences, figures, names, dates or quotes that "
    "are not in that text. You must not use anything you remember about this "
    "topic from training. If the source text is too short or too vague to "
    f"summarise, reply with exactly {NO_SUMMARY} and nothing else."
)

_VERIFY_SYSTEM = (
    "You are a strict fact-checker. You compare a candidate summary against a "
    "source text and decide whether every claim in the summary is directly "
    "supported by that source. Unsupported specifics — numbers, names, dates, "
    "causes, outcomes — make it unsupported. Answer with exactly one word: "
    "SUPPORTED or UNSUPPORTED."
)


def _load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def _verify_summary(summary: str, source_text: str) -> bool:
    """Ask the LLM whether `summary` is fully supported by `source_text`."""
    prompt = (
        f"SOURCE TEXT:\n{source_text[:4000]}\n\n"
        f"CANDIDATE SUMMARY:\n{summary}\n\n"
        "Is every claim in the candidate summary directly supported by the "
        "source text? Answer SUPPORTED or UNSUPPORTED."
    )
    try:
        verdict = llm.complete(
            prompt, system=_VERIFY_SYSTEM, max_tokens=10, temperature=0.0
        )
    except Exception as e:
        print(f"[fetch]     verification call failed ({e}) — rejecting summary")
        return False
    return verdict.strip().upper().startswith("SUPPORTED")


def _extractive(source_text: str, limit: int = 300) -> str:
    """Truncate source text at a sentence boundary. Adds no new claims."""
    text = " ".join(source_text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    stop = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return (cut[: stop + 1] if stop > 80 else cut).strip() + "…"


def _summarize_item(item_row, cfg: dict) -> tuple[str, str, str]:
    """Return (article_content, summary, summary_source)."""
    settings = cfg.get("settings", {})
    max_chars = settings.get("max_article_chars", 6000)
    min_source = settings.get("min_source_chars", 400)
    verify = cfg.get("llm", {}).get("verify_summaries", True)

    content = web.fetch_article_text(item_row["url"], max_chars=max_chars)
    feed_text = (item_row["content"] or "").strip()
    source_text = (content or feed_text).strip()

    # Not enough real text to summarise anything. Never invent.
    if len(source_text) < min_source:
        if source_text:
            return content, _extractive(source_text), "extractive"
        return content, "", "none"

    prompt = (
        "Summarise the source text below in 2-3 concise sentences, using only "
        "facts stated in it. Do not begin with 'This article'.\n\n"
        f"TITLE: {item_row['title']}\n\n"
        f"SOURCE TEXT:\n{source_text[:4000]}"
    )
    try:
        summary = llm.complete(prompt, system=_SUMMARY_SYSTEM, max_tokens=200)
    except Exception as e:
        print(f"[fetch]     LLM summary failed: {e}")
        return content, _extractive(source_text), "extractive"

    summary = summary.strip()

    # Model told us the source was too thin — believe it.
    if not summary or NO_SUMMARY in summary.upper():
        return content, _extractive(source_text), "extractive"

    if verify and not _verify_summary(summary, source_text):
        print(f"[fetch]     ✗ ungrounded summary discarded: {item_row['title'][:50]}")
        return content, _extractive(source_text), "extractive"

    return content, summary, "verified" if verify else "llm"


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
    # Keep the eligibility window tied to retention so nothing fetched but not
    # yet summarised falls off the end before a later run can pick it up.
    to_summarize = db.get_unsummarized(
        limit=60, hours=config["settings"]["retention_days"] * 24
    )
    print(f"[fetch] Summarizing {len(to_summarize)} items...")

    tally: dict[str, int] = {}
    for row in to_summarize:
        content, summary, source = _summarize_item(row, config)
        db.update_summary(row["id"], content, summary, source)
        tally[source] = tally.get(source, 0) + 1
        print(f"[fetch]   ✓ [{source}] {row['title'][:55]}")

    if tally:
        print("[fetch] Summary provenance: " +
              ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))

    return new_count


if __name__ == "__main__":
    run()
