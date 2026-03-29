"""Fetch a URL and return clean readable text, suitable for speaking aloud."""

import sys
from pathlib import Path

_skills_dir = str(Path(__file__).parent)
if _skills_dir not in sys.path:
    sys.path.insert(0, _skills_dir)


def read_url(url: str, max_chars: int = 8000) -> str:
    """
    Fetch a URL and extract clean readable text from it.

    Strips HTML, navigation, ads and boilerplate — returns just the content.
    Suitable for passing directly to speak() to read an article aloud.

    Args:
        url:       The URL to fetch and read.
        max_chars: Maximum characters to return (default 8000, ~10 min of speech).

    Returns:
        Clean plain text of the page content.

    Examples:
        read_url("https://www.bbc.co.uk/news/articles/abc123")
        read_url("https://en.wikipedia.org/wiki/Polar_bear")
    """
    import trafilatura

    downloaded = trafilatura.fetch_url(url)
    if downloaded:
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        if text and len(text.strip()) > 100:
            return text.strip()[:max_chars]

    # Fallback: requests + basic HTML stripping
    import requests
    from html.parser import HTMLParser

    class _Extractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self._parts = []
            self._skip  = False

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "nav", "header", "footer"):
                self._skip = True

        def handle_endtag(self, tag):
            if tag in ("script", "style", "nav", "header", "footer"):
                self._skip = False

        def handle_data(self, data):
            if not self._skip and data.strip():
                self._parts.append(data.strip())

    r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    parser = _Extractor()
    parser.feed(r.text)
    return " ".join(parser._parts)[:max_chars]


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://en.wikipedia.org/wiki/Polar_bear"
    print(read_url(url))
