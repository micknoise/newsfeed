"""Summarize RSS feed entries and Brave search results into a readable digest."""

import os
import sys
from pathlib import Path

# Ensure skills dir is on path so sibling skills can be imported
_skills_dir = str(Path(__file__).parent)
if _skills_dir not in sys.path:
    sys.path.insert(0, _skills_dir)


def summarize_feed(topic=None, entries_per_feed=5, include_search=True):
    """
    Produce a readable news digest combining RSS feeds and Brave search.

    Args:
        topic:           Optional topic string to filter/search for (e.g. "AI").
                         If None, returns general top news.
        entries_per_feed: Entries to pull from each RSS feed.
        include_search:  If True and WEB_SEARCH_API_KEY is set, enriches with
                         Brave search results for the topic.

    Returns:
        A formatted string digest suitable for reading.
    """
    from get_rss_feeds import get_rss_feeds
    from web_search import web_search

    sections = []

    # ── RSS section ───────────────────────────────────────────────────────────
    all_entries = get_rss_feeds(entries_per_feed=entries_per_feed)

    if topic:
        keywords = topic.lower().split()
        filtered = [
            e for e in all_entries
            if any(k in e["title"].lower() or k in e["summary"].lower() for k in keywords)
        ]
        rss_entries = filtered or all_entries  # fall back to all if no matches
        rss_header = f"## RSS headlines mentioning '{topic}'"
        if not filtered:
            rss_header += " (no exact matches — showing all headlines)"
    else:
        rss_entries = all_entries
        rss_header = "## Top headlines from RSS feeds"

    lines = [rss_header, ""]
    seen_titles = set()
    for e in rss_entries:
        if e["title"] in seen_titles:
            continue
        seen_titles.add(e["title"])
        lines.append(f"**{e['source']}** — {e['title']}")
        if e["summary"]:
            lines.append(f"{e['summary'][:200]}{'...' if len(e['summary']) > 200 else ''}")
        lines.append(f"<{e['link']}>")
        lines.append("")

    sections.append("\n".join(lines))

    # ── Brave search section ──────────────────────────────────────────────────
    if include_search and os.getenv("WEB_SEARCH_API_KEY"):
        query = topic if topic else "top news today"
        try:
            results = web_search(query, raw=True)
            web_items = results.get("web", {}).get("results", [])[:5]
            if web_items:
                search_lines = [f"## Brave search: '{query}'", ""]
                for item in web_items:
                    title = item.get("title", "").strip()
                    desc  = item.get("description", "").strip()
                    url   = item.get("url", "")
                    search_lines.append(f"**{title}**")
                    if desc:
                        search_lines.append(desc)
                    search_lines.append(f"<{url}>")
                    search_lines.append("")
                sections.append("\n".join(search_lines))
        except Exception as e:
            sections.append(f"## Brave search\n\n(Unavailable: {e})\n")

    return "\n---\n\n".join(sections)


if __name__ == "__main__":
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else None
    print(summarize_feed(topic=topic, entries_per_feed=3))
