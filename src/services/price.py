"""
Price service — fetches live market prices via yfinance.

Public API
----------
fetch_price(symbol)              -> dict | None
fetch_prices_batch(symbols)      -> dict[str, dict]
_fetch_from_yfinance(symbols)    -> dict[str, dict]
_sync_fetch(symbols)             -> dict[str, dict]
"""
from __future__ import annotations

import asyncio
from typing import Sequence

import yfinance as yf
from loguru import logger

from src.utils.cache import price_cache

MAX_RETRIES = 3
RETRY_DELAY = 2.0
CACHE_TTL = 60  # seconds


# ─── Public helpers ───────────────────────────────────────────────────────────


async def fetch_price(symbol: str) -> dict | None:
    """Return price data for a single symbol (cache-first)."""
    cached = price_cache.get(symbol.upper())
    if cached is not None:
        return cached

    result = await _fetch_from_yfinance([symbol.upper()])
    return result.get(symbol.upper())


async def fetch_prices_batch(symbols: Sequence[str]) -> dict[str, dict]:
    """Return price data for multiple symbols (cache-first, batch fetch for misses)."""
    if not symbols:
        return {}

    symbols = [s.upper() for s in symbols]
    result: dict[str, dict] = {}
    misses: list[str] = []

    for sym in symbols:
        cached = price_cache.get(sym)
        if cached is not None:
            result[sym] = cached
        else:
            misses.append(sym)

    if misses:
        fetched = await _fetch_from_yfinance(misses)
        result.update(fetched)

    return result


# ─── Internal ─────────────────────────────────────────────────────────────────


async def _fetch_from_yfinance(symbols: list[str]) -> dict[str, dict]:
    """Async wrapper around _sync_fetch with retry logic."""
    for attempt in range(MAX_RETRIES):
        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, _sync_fetch, symbols)
            # populate cache
            for sym, info in data.items():
                price_cache.set(sym, info, ttl=CACHE_TTL)
            return data
        except Exception as exc:
            logger.warning(f"yfinance fetch attempt {attempt + 1} failed: {exc}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAY)

    return {}


def _sync_fetch(symbols: list[str]) -> dict[str, dict]:
    """Synchronous yfinance fetch — runs in executor."""
    tickers = yf.Tickers(" ".join(symbols))
    result: dict[str, dict] = {}

    for sym, ticker in tickers.tickers.items():
        try:
            last_price = ticker.fast_info.last_price
            prev_close = ticker.fast_info.previous_close

            if last_price is None:
                continue

            change = last_price - (prev_close or last_price)
            change_pct = (change / prev_close * 100) if prev_close else 0.0

            result[sym] = {
                "symbol": sym,
                "price": last_price,
                "change": change,
                "change_pct": change_pct,
            }
        except Exception as exc:
            logger.warning(f"Could not parse data for {sym}: {exc}")

    return result