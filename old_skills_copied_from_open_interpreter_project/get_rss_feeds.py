"""Fetch recent entries from a curated list of RSS news feeds."""

import feedparser
from bs4 import BeautifulSoup


_DEFAULT_FEEDS = [
    ("BBC News",        "https://feeds.bbci.co.uk/news/rss.xml"),
    ("The Guardian",    "https://www.theguardian.com/world/rss"),
    ("Reuters",         "https://feeds.reuters.com/reuters/topNews"),
    ("Al Jazeera",      "https://www.aljazeera.com/xml/rss/all.xml"),
    ("UK Politics",     "https://www.reddit.com/r/ukpolitics/.rss"),
    ("World News",      "https://www.reddit.com/r/worldnews/.rss"),
]


def _clean_html(raw):
    """Strip HTML tags from a string, return plain text."""
    if not raw:
        return ""
    return BeautifulSoup(raw, "html.parser").get_text(separator=" ", strip=True)


def get_rss_feeds(feeds=None, entries_per_feed=5):
    """
    Fetch recent entries from RSS news feeds.

    Args:
        feeds:           List of (label, url) tuples. Defaults to a curated news set.
        entries_per_feed: How many entries to pull from each feed.

    Returns:
        List of dicts with keys: title, summary, link, source.
    """
    if feeds is None:
        feeds = _DEFAULT_FEEDS

    results = []
    for label, url in feeds:
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries[:entries_per_feed]:
                summary_raw = getattr(entry, "summary", "") or getattr(entry, "description", "")
                results.append({
                    "source": label,
                    "title":   entry.get("title", "").strip(),
                    "summary": _clean_html(summary_raw)[:400],
                    "link":    entry.get("link", ""),
                })
        except Exception as e:
            print(f"[get_rss_feeds] Skipping {label}: {e}")

    return results


if __name__ == "__main__":
    entries = get_rss_feeds(entries_per_feed=2)
    for e in entries:
        print(f"[{e['source']}] {e['title']}")
        print(f"  {e['summary'][:120]}...")
        print()
