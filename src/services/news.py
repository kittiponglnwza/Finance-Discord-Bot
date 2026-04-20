"""
News service — fetches financial headlines for a given symbol.

Priority:
  1. NewsAPI  (if NEWSAPI_KEY is set)
  2. Yahoo Finance RSS feed  (free fallback)

Public API
----------
fetch_headlines(symbol)        -> list[str]
fetch_headlines_multi(symbols) -> list[str]
"""
from __future__ import annotations

import asyncio
import os
from typing import Sequence

import aiohttp
import feedparser
from loguru import logger

from src.utils.cache import news_cache

# ─── Config ───────────────────────────────────────────────────────────────────

NEWSAPI_KEY: str = os.getenv("NEWSAPI_KEY", "")
NEWSAPI_URL = "https://newsapi.org/v2/everything"
MAX_HEADLINES = 10
CACHE_TTL = 900  # 15 minutes


# ─── Public helpers ───────────────────────────────────────────────────────────


async def fetch_headlines(symbol: str) -> list[str]:
    """Return up to MAX_HEADLINES headlines for *symbol* (cached)."""
    cache_key = f"news:{symbol.upper()}"
    cached = news_cache.get(cache_key)
    if cached is not None:
        return cached

    headlines = (
        await _fetch_from_newsapi(symbol)
        if NEWSAPI_KEY
        else await _fetch_from_rss(symbol)
    )
    headlines = headlines[:MAX_HEADLINES]
    news_cache.set(cache_key, headlines, ttl=CACHE_TTL)
    return headlines


async def fetch_headlines_multi(symbols: Sequence[str]) -> list[str]:
    """Fetch headlines for multiple symbols concurrently, deduped."""
    if not symbols:
        return []

    results = await asyncio.gather(
        *[fetch_headlines(sym) for sym in symbols],
        return_exceptions=True,
    )

    seen: set[str] = set()
    combined: list[str] = []
    for item in results:
        if isinstance(item, Exception):
            continue
        for headline in item:
            if headline not in seen:
                seen.add(headline)
                combined.append(headline)
    return combined


# ─── Backends ─────────────────────────────────────────────────────────────────


async def _fetch_from_newsapi(symbol: str) -> list[str]:
    params = {
        "q": symbol,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": MAX_HEADLINES,
        "apiKey": NEWSAPI_KEY,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(NEWSAPI_URL, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.warning(f"NewsAPI returned {resp.status} for {symbol}")
                    return await _fetch_from_rss(symbol)
                data = await resp.json()
                articles = data.get("articles", [])
                return [a["title"] for a in articles if a.get("title")]
    except Exception as exc:
        logger.warning(f"NewsAPI error for {symbol}: {exc} — falling back to RSS")
        return await _fetch_from_rss(symbol)


async def _fetch_from_rss(symbol: str) -> list[str]:
    """Yahoo Finance RSS — no API key required."""
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
    try:
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(None, feedparser.parse, url)
        return [entry.title for entry in feed.entries if hasattr(entry, "title")]
    except Exception as exc:
        logger.warning(f"RSS fetch error for {symbol}: {exc}")
        return []