"""Restricted Indian Government Web Search Fallback (myscheme.gov.in / gov.in / nic.in)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from backend.config import get_settings
from backend.db.repositories import now_ist_iso
from backend.guardrails.injection import sanitize_untrusted_evidence

logger = logging.getLogger(__name__)

ALLOWED_DOMAIN_SUFFIXES = (".gov.in", ".nic.in", "myscheme.gov.in", "india.gov.in", "pgportal.gov.in")


def is_allowed_gov_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    if not host:
        return False
    return any(host == dom or host.endswith(dom) for dom in ALLOWED_DOMAIN_SUFFIXES)


def _search_ddgs_sync(query: str, max_results: int) -> list[dict[str, Any]]:
    from ddgs import DDGS

    scoped_query = f"{query} (site:myscheme.gov.in OR site:gov.in OR site:nic.in)"
    results: list[dict[str, Any]] = []
    ts = now_ist_iso()
    with DDGS(timeout=8) as ddgs:
        raw = list(ddgs.text(scoped_query, max_results=max_results * 2))
    for item in raw:
        url = item.get("href") or item.get("link") or ""
        if not is_allowed_gov_url(url):
            continue
        snippet_raw = item.get("body") or item.get("snippet") or ""
        snippet_clean, flags = sanitize_untrusted_evidence(snippet_raw)
        results.append(
            {
                "title": item.get("title") or "Official Government Portal",
                "url": url,
                "snippet": snippet_clean,
                "retrieved_at": ts,
                "security_flags": flags,
            }
        )
        if len(results) >= max_results:
            break
    return results


async def _search_tavily(query: str, max_results: int, api_key: str) -> list[dict[str, Any]]:
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_domains": ["myscheme.gov.in", "gov.in", "nic.in"],
    }
    ts = now_ist_iso()
    async with httpx.AsyncClient(timeout=8.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    results: list[dict[str, Any]] = []
    for item in data.get("results", []):
        u = item.get("url") or ""
        if not is_allowed_gov_url(u):
            continue
        snippet_clean, flags = sanitize_untrusted_evidence(item.get("content") or "")
        results.append(
            {
                "title": item.get("title") or "Official Government Portal",
                "url": u,
                "snippet": snippet_clean,
                "retrieved_at": ts,
                "security_flags": flags,
            }
        )
    return results


async def search_gov_web(query: str, max_results: int = 4) -> dict[str, Any]:
    """Search official Indian government portals with strict domain filtering & 8s timeout."""
    settings = get_settings()
    max_results = max(1, min(int(max_results), 5))
    tavily_key = settings.tavily_api_key.get_secret_value().strip()

    if tavily_key:
        try:
            items = await asyncio.wait_for(_search_tavily(query, max_results, tavily_key), timeout=8.5)
            return {"provider": "tavily", "results": items, "error": None}
        except Exception as exc:
            logger.warning("Tavily search failed (%s); falling back to DuckDuckGo.", exc)

    try:
        items = await asyncio.wait_for(asyncio.to_thread(_search_ddgs_sync, query, max_results), timeout=8.5)
        return {"provider": "duckduckgo", "results": items, "error": None}
    except Exception as exc:
        logger.warning("Restricted .gov.in web search unavailable: %s", exc)
        return {
            "provider": "duckduckgo",
            "results": [],
            "error": f"Live .gov.in web search temporarily unavailable ({type(exc).__name__}).",
        }
