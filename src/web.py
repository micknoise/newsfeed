"""Fetch a URL and return clean readable text (adapted from read_url.py)."""

import requests
from html.parser import HTMLParser


def fetch_article_text(url: str, max_chars: int = 6000) -> str:
    """Extract plain text from a URL. Returns empty string on failure."""
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
                return text.strip()[:max_chars]
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
        return " ".join(stripper._parts)[:max_chars]
    except Exception:
        return ""
