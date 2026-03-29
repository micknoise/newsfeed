"""Search Wikipedia for a topic and return a plain-text summary."""

import re
import requests
from urllib.parse import quote

_HEADERS = {"User-Agent": "open-interpreter-skills/1.0 (local research tool)"}


def wikipedia_search(topic: str) -> str:
    """
    Search Wikipedia for a topic and return a plain-text summary.

    Args:
        topic: The topic to look up (e.g. 'Python programming language').

    Returns:
        A formatted string with the article title and summary extract.
    """
    # Step 1: use the search API to find the canonical page title
    search_resp = requests.get(
        "https://en.wikipedia.org/w/api.php",
        headers=_HEADERS,
        params={
            "action": "query",
            "list": "search",
            "srsearch": topic,
            "format": "json",
            "srlimit": 1,
        },
        timeout=10,
    )
    search_resp.raise_for_status()
    results = search_resp.json().get("query", {}).get("search", [])
    if not results:
        return f"No Wikipedia article found for '{topic}'."

    page_title = results[0]["title"]

    # Step 2: fetch the summary for that title
    summary_resp = requests.get(
        f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(page_title)}",
        headers=_HEADERS,
        timeout=10,
    )
    summary_resp.raise_for_status()
    data = summary_resp.json()

    title   = data.get("title", page_title)
    extract = data.get("extract", "No summary available.")
    extract = re.sub(r"\s+", " ", extract).strip()
    url     = data.get("content_urls", {}).get("desktop", {}).get("page", "")

    result = f"**{title}**\n\n{extract}"
    if url:
        result += f"\n\n{url}"
    return result


if __name__ == "__main__":
    import sys
    topic = " ".join(sys.argv[1:]) or "Python programming language"
    print(wikipedia_search(topic))
