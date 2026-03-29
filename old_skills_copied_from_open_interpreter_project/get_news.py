"""Fetch and summarize UK news from RSS feeds and Brave Search, saved as a markdown digest."""

import os
import sys
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup

_skills_dir = str(Path(__file__).parent)
if _skills_dir not in sys.path:
    sys.path.insert(0, _skills_dir)


def _clean(html):
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)


def get_news(topic="UK news", output_file=None):
    """
    Fetch and summarize news from RSS feeds and Brave Search.

    Args:
        topic:       Search topic (default: 'UK news').
        output_file: If set, also save the digest to this file path.

    Returns:
        Formatted markdown string of the news digest.
    """
    from get_rss_feeds import get_rss_feeds
    import requests

    articles = []

    # ── RSS feeds ─────────────────────────────────────────────────────────────
    try:
        rss_entries = get_rss_feeds(entries_per_feed=4)
        for e in rss_entries:
            articles.append({
                "title":   e["title"],
                "summary": _clean(e["summary"]),
                "link":    e["link"],
                "source":  e["source"],
            })
    except Exception as e:
        print(f"[get_news] RSS error: {e}")

    # ── Brave Search ──────────────────────────────────────────────────────────
    api_key = os.environ.get("WEB_SEARCH_API_KEY")
    if api_key:
        try:
            from web_search import web_search
            for item in web_search(topic, raw=True).get("web", {}).get("results", []):
                articles.append({
                    "title":   item.get("title", "").strip(),
                    "summary": _clean(item.get("description", "")),
                    "link":    item.get("url", ""),
                    "source":  "Brave Search",
                })
        except Exception as e:
            print(f"[get_news] Brave Search error: {e}")
    else:
        print("[get_news] WEB_SEARCH_API_KEY not set — skipping Brave Search.")

    # ── Build digest string ───────────────────────────────────────────────────
    lines = [f"# News Digest: {topic}", f"*Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}*", ""]

    if not articles:
        lines.append("No articles found.")
    else:
        current_source = None
        for a in articles:
            if a["source"] != current_source:
                current_source = a["source"]
                lines += ["", f"## {current_source}", ""]
            lines.append(f"### {a['title']}")
            if a["summary"]:
                summary = a["summary"][:300] + ("..." if len(a["summary"]) > 300 else "")
                lines.append(summary)
            lines += [f"[Read more]({a['link']})", ""]

    digest = "\n".join(lines)

    if output_file:
        with open(output_file, "w") as f:
            f.write(digest)
        print(f"[get_news] Saved {len(articles)} articles to {output_file}")

    return digest


if __name__ == "__main__":
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "UK news"
    get_news(topic=topic)
