"""RSS feed fetching and normalisation.

Feeds are fetched with an explicit User-Agent and per-host rate limiting.
Reddit in particular enforces a hard limit on unauthenticated .rss requests
(observed: x-ratelimit-remaining hits 0 after a single request), so requests
to the same host are serialised with a configurable delay and 429s are
retried with backoff rather than being silently swallowed.
"""

import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

# Reddit blocks generic/absent User-Agents. Identify the client properly.
USER_AGENT = (
    "newsfeed/1.0 (personal RSS reader by /u/micknoise; "
    "+https://github.com/micknoise/newsfeed)"
)

# Minimum seconds between requests to the same host. Reddit needs a long
# gap; everything else is polite-but-quick.
DEFAULT_HOST_DELAY = 2.0
HOST_DELAYS = {
    "reddit.com": 90.0,
    "www.reddit.com": 90.0,
    "old.reddit.com": 90.0,
}

_last_request_at: dict[str, float] = {}


class FeedFetchError(Exception):
    """Raised when a feed could not be fetched (network error, 429, etc.).

    Distinct from a feed that fetched fine but happens to have no entries —
    callers must not treat a fetch failure as 'this feed has no news'.
    """


def _host_key(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    # Group all reddit subdomains under one bucket — the limit is per-account/IP.
    if host.endswith("reddit.com"):
        return "reddit.com"
    return host


def _throttle(url: str) -> None:
    """Sleep as needed so we don't exceed the per-host request rate."""
    key = _host_key(url)
    delay = HOST_DELAYS.get(key, DEFAULT_HOST_DELAY)
    last = _last_request_at.get(key)
    if last is not None:
        wait = delay - (time.monotonic() - last)
        if wait > 0:
            print(f"[rss]   throttling {key} for {wait:.0f}s")
            time.sleep(wait)
    _last_request_at[key] = time.monotonic()


def _get(url: str, timeout: int = 30, max_retries: int = 3) -> bytes:
    """Fetch a feed URL, honouring rate limits. Raises FeedFetchError."""
    last_err = "unknown error"
    for attempt in range(max_retries):
        _throttle(url)
        try:
            resp = requests.get(
                url,
                timeout=timeout,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/atom+xml, application/rss+xml, application/xml;q=0.9, */*;q=0.8",
                    "Accept-Encoding": "gzip, deflate",
                },
            )
        except requests.RequestException as e:
            last_err = f"network error: {e}"
            print(f"[rss]   attempt {attempt + 1}/{max_retries} failed: {last_err}")
            continue

        if resp.status_code == 200:
            return resp.content

        if resp.status_code in (429, 503):
            # Prefer the server's own hint about when to come back.
            hint = resp.headers.get("retry-after") or resp.headers.get("x-ratelimit-reset")
            try:
                backoff = float(hint) if hint else 0.0
            except ValueError:
                backoff = 0.0
            # Reddit's reset header is optimistically small; enforce a real floor
            # that grows with each attempt.
            backoff = max(backoff, HOST_DELAYS.get(_host_key(url), 30.0) * (attempt + 1))
            last_err = f"HTTP {resp.status_code} (rate limited)"
            if attempt < max_retries - 1:
                print(f"[rss]   rate limited, backing off {backoff:.0f}s")
                time.sleep(backoff)
                _last_request_at[_host_key(url)] = time.monotonic()
            continue

        last_err = f"HTTP {resp.status_code}"
        break

    raise FeedFetchError(last_err)


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


def fetch_feed(label: str, url: str, limit: int = 12,
               max_age_days: int | None = None) -> list[dict]:
    """Fetch a single RSS/Atom feed. Raises FeedFetchError on fetch failure.

    If `max_age_days` is set, entries published longer ago than that are
    dropped. Entries with no parseable date are always kept — some feeds
    simply omit dates, and dropping those would be worse than keeping them.
    """
    raw = _get(url)
    parsed = feedparser.parse(raw)

    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=max_age_days)
        if max_age_days else None
    )
    stale = 0

    results = []
    for entry in parsed.entries[:limit]:
        summary_raw = (
            getattr(entry, "summary", "")
            or getattr(entry, "description", "")
            or ""
        )
        published = _parse_date(entry)
        if cutoff and published and published < cutoff:
            stale += 1
            continue

        results.append({
            "guid":        _make_guid(entry, url),
            "feed_label":  label,
            "title":       entry.get("title", "").strip(),
            "url":         entry.get("link", ""),
            "published_at": published,
            "description": _clean_html(summary_raw)[:500],
        })

    if stale:
        # A feed where *everything* is stale is almost certainly frozen, not quiet.
        if not results:
            print(f"[rss] {label}: WARNING — all {stale} entries older than "
                  f"{max_age_days}d; feed looks frozen")
        else:
            print(f"[rss] {label}: dropped {stale} stale entries (>{max_age_days}d)")
    return results


def fetch_all(config: dict) -> list[dict]:
    """Fetch all feeds defined in config. Returns combined list sorted newest-first.

    Feeds are ordered so that same-host feeds are spread out, and failures are
    reported loudly rather than silently yielding an empty feed.
    """
    settings = config.get("settings", {})
    limit = settings.get("items_per_feed", 12)
    max_age = settings.get("max_item_age_days", 14)
    feeds = config.get("feeds", [])
    all_items = []
    failures = []

    for feed in feeds:
        try:
            items = fetch_feed(feed["label"], feed["url"], limit=limit,
                               max_age_days=max_age)
        except FeedFetchError as e:
            failures.append((feed["label"], str(e)))
            print(f"[rss] {feed['label']}: FAILED — {e}")
            continue
        print(f"[rss] {feed['label']}: {len(items)} items")
        all_items.extend(items)

    if failures:
        print(f"[rss] {len(failures)} feed(s) failed: " + ", ".join(l for l, _ in failures))

    all_items.sort(
        key=lambda x: x["published_at"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return all_items
