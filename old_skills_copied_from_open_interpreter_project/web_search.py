"""Perform a web search using the Brave Search API."""

import os
import requests


def web_search(query, raw=False):
    """
    Perform a web search using the Brave Search API.

    Args:
        query: Search query string.
        raw:   If True, return the raw JSON response dict (for use by other skills).
               If False (default), return a formatted readable string.

    Returns:
        Formatted string of results, or raw JSON dict if raw=True.
    """
    api_key = os.getenv("WEB_SEARCH_API_KEY")
    if not api_key:
        raise ValueError("WEB_SEARCH_API_KEY environment variable is not set.")

    response = requests.get(
        "https://api.search.brave.com/res/v1/web/search",
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
        },
        params={"q": query},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()

    if raw:
        return data

    results = data.get("web", {}).get("results", [])
    if not results:
        return f"No results found for '{query}'."

    lines = [f"**Web search: {query}**", ""]
    for item in results[:5]:
        title = item.get("title", "").strip()
        desc  = item.get("description", "").strip()
        link  = item.get("url", "")
        lines.append(f"**{title}**")
        if desc:
            lines.append(desc)
        lines.append(link)
        lines.append("")

    return "\n".join(lines)
