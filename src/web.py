"""Fetch a URL and return clean readable text (adapted from read_url.py)."""

import requests
from html.parser import HTMLParser


# Interstitials that return plenty of text but no article. Without this they
# sail past settings.min_source_chars and get summarised as if they were news.
_INTERSTITIAL_HOSTS = ("news.google.com", "consent.google.com", "consent.yahoo.com")
_INTERSTITIAL_MARKERS = (
    "Before you continue to Google",
    "We use cookies and data",
    "Enable JavaScript and cookies to continue",
)


def _is_interstitial(url: str, text: str) -> bool:
    """True if `text` is a consent/redirect page rather than article content."""
    from urllib.parse import urlparse
    if urlparse(url).netloc.lower().lstrip("www.") in _INTERSTITIAL_HOSTS:
        return True
    head = text[:1500]
    return any(m in head for m in _INTERSTITIAL_MARKERS)


def fetch_article_text(url: str, max_chars: int = 6000) -> str:
    """Extract plain text from a URL. Returns empty string on failure.

    Consent/redirect interstitials are treated as failures, not as content.
    """
    try:
        import trafilatura
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                no_fallback=False,
            )
            if text and len(text.strip()) > 100:
                text = text.strip()
                if not _is_interstitial(url, text):
                    return text[:max_chars]
                return ""
    except Exception:
        pass

    # Fallback: requests + basic HTML stripping
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()

        class _Stripper(HTMLParser):
            def __init__(self):
                super().__init__()
                self._parts = []
                self._skip = False

            def handle_starttag(self, tag, attrs):
                if tag in ("script", "style", "nav", "header", "footer"):
                    self._skip = True

            def handle_endtag(self, tag):
                if tag in ("script", "style", "nav", "header", "footer"):
                    self._skip = False

            def handle_data(self, data):
                if not self._skip and data.strip():
                    self._parts.append(data.strip())

        stripper = _Stripper()
        stripper.feed(resp.text)
        text = " ".join(stripper._parts)
        if _is_interstitial(url, text):
            return ""
        return text[:max_chars]
    except Exception:
        return ""
