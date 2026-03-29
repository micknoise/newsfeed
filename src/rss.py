"""RSS feed fetching and normalisation."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
from bs4 import BeautifulSoup


def _clean_html(raw: str) -> str:
    if not raw:
        return ""
    return BeautifulSoup(raw, "html.parser").get_text(separator=" ", strip=True)


def _parse_date(entry) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                return parsedate_to_datetime(raw).astimezone(timezone.utc)
            except Exception:
                pass
    return None


def _make_guid(entry, feed_url: str) -> str:
    return getattr(entry, "id", None) or entry.get("link", "") or f"{feed_url}#{entry.get('title','')}"


def fetch_feed(label: str, url: str, limit: int = 12) -> list[dict]:
    """Fetch a single RSS/Atom feed. Returns list of normalised item dicts."""
    try:
        parsed = feedparser.parse(url, agent="newsfeed/1.0")
    except Exception as e:
        print(f"[rss] Error fetching {label}: {e}")
        return []

    results = []
    for entry in parsed.entries[:limit]:
        summary_raw = (
            getattr(entry, "summary", "")
            or getattr(entry, "description", "")
            or ""
        )
        results.append({
            "guid":        _make_guid(entry, url),
            "feed_label":  label,
            "title":       entry.get("title", "").strip(),
            "url":         entry.get("link", ""),
            "published_at": _parse_date(entry),
            "description": _clean_html(summary_raw)[:500],
        })
    return results


def fetch_all(config: dict) -> list[dict]:
    """Fetch all feeds defined in config. Returns combined list sorted newest-first."""
    limit = config.get("settings", {}).get("items_per_feed", 12)
    all_items = []
    for feed in config.get("feeds", []):
        items = fetch_feed(feed["label"], feed["url"], limit=limit)
        print(f"[rss] {feed['label']}: {len(items)} items")
        all_items.extend(items)

    # Sort by published_at descending (None dates go last)
    all_items.sort(
        key=lambda x: x["published_at"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return all_items
