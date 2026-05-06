import re
from html import unescape
from urllib.parse import urlparse

import httpx

from app.models import SearchResult

SEARCH_TRIGGER_WORDS = {
    "latest",
    "current",
    "today",
    "news",
    "recent",
    "update",
    "up-to-date",
    "live",
}


def should_search(use_search: str, messages_text: str) -> bool:
    if use_search == "on":
        return True
    if use_search == "off":
        return False
    lowered = messages_text.lower()
    return any(word in lowered for word in SEARCH_TRIGGER_WORDS)


def _is_allowed(url: str, mode: str, allowed_domains: set[str]) -> bool:
    if mode == "open":
        return True
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    return host in allowed_domains


async def simple_web_search(
    query: str,
    mode: str,
    allowed_domains: set[str],
    limit: int = 5,
) -> list[SearchResult]:
    # Use the html subdomain directly to avoid 302 redirect failures.
    endpoint = "https://html.duckduckgo.com/html/"
    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        resp = await client.post(endpoint, data={"q": query})
        resp.raise_for_status()
        html = resp.text

    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    snippet_pattern = re.compile(r'<a[^>]+class="result__snippet"[^>]*>(?P<snippet>.*?)</a>', re.IGNORECASE | re.DOTALL)
    snippets = [re.sub(r"<[^>]+>", "", unescape(s)) for s in snippet_pattern.findall(html)]
    matches = list(pattern.finditer(html))

    results: list[SearchResult] = []
    for idx, match in enumerate(matches):
        url = unescape(match.group("url"))
        if not _is_allowed(url, mode, allowed_domains):
            continue
        title = re.sub(r"<[^>]+>", "", unescape(match.group("title"))).strip()
        snippet = snippets[idx].strip() if idx < len(snippets) else ""
        if title and url:
            results.append(SearchResult(title=title, url=url, snippet=snippet))
        if len(results) >= limit:
            break
    return results
