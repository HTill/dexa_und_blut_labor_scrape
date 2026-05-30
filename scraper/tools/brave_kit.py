"""Brave Search API wrapper with query-level caching and rate limiting.

Saves rich search results to data/unchecked/search_cache.json
to avoid burning API quota on repeated queries.

TTL: 30 days per cached query result.
Rate limit: 1 query/second (Brave Free Tier).
"""

import json
import os
import time
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
CACHE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "unchecked" / "search_cache.json"
CACHE_TTL = 30 * 86400  # 30 days in seconds
_last_request = 0.0


def _load_cache() -> dict:
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
    except (json.JSONDecodeError, IOError):
        pass
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(CACHE_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    os.replace(tmp, str(CACHE_FILE))


def _extract_result(r: dict) -> dict:
    extra = r.get("extra_snippets") or []
    return {
        "url": r.get("url", ""),
        "title": r.get("title", ""),
        "description": r.get("description", ""),
        "age": r.get("age", ""),
        "extra_snippets": extra,
    }


def search(query: str, max_results: int = 8) -> list[dict]:
    global _last_request

    api_key = os.getenv("BRAVE_SEARCH_API_KEY", "")
    if not api_key:
        print("  WARN: BRAVE_SEARCH_API_KEY not set, skipping search")
        return []

    cache = _load_cache()
    now = time.time()
    cache_key = query
    cache_hit = cache.get(cache_key, {})

    if cache_hit and (now - cache_hit.get("ts", 0) < CACHE_TTL):
        results = cache_hit.get("results", [])
        if results:
            print(f"    cache: {len(results)} results")
            return results

    elapsed = now - _last_request
    if elapsed < 0.02:
        time.sleep(0.02)

    try:
        resp = requests.get(
            BRAVE_API_URL,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
            params={"q": query, "count": max_results, "search_lang": "de",
                    "extra_snippets": "true"},
            timeout=15,
        )
        _last_request = time.time()
        resp.raise_for_status()
        data = resp.json()
        web_results = data.get("web", {}).get("results", [])
        results = [_extract_result(r) for r in web_results if r.get("url")]
        cache[cache_key] = {"results": results, "ts": _last_request}
        _save_cache(cache)
        return results
    except Exception as e:
        _last_request = time.time()
        print(f"    Brave API error: {e}")
        return cache_hit.get("results", []) if cache_hit else []
