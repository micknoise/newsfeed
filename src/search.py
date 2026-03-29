"""Brave Search API wrapper (adapted from web_search.py)."""

import os
import requests


def web_search(query: str, n: int = 5) -> list[dict]:
    """
    Search the web via Brave Search API.
    Returns list of {title, url, description} dicts.
    Requires WEB_SEARCH_API_KEY environment variable.
    """
    api_key = os.getenv("WEB_SEARCH_API_KEY")
    if not api_key:
        return []

    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
            },
            params={"q": query, "count": n},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("web", {}).get("results", [])
        return [
            {
                "title":       r.get("title", "").strip(),
                "url":         r.get("url", ""),
                "description": r.get("description", "").strip(),
            }
            for r in results[:n]
        ]
    except Exception as e:
        print(f"[search] Brave Search error: {e}")
        return []
