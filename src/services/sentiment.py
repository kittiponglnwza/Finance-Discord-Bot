"""
AI Sentiment service — thin async wrapper around GPT-4o-mini.

Rules:
- Always use gpt-4o-mini (cost control)
- Hard cap on headlines sent per call
- Exponential backoff on failure
- Never raises — returns None on total failure
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional

from loguru import logger
from openai import AsyncOpenAI

# ─── Config ───────────────────────────────────────────────────────────────────

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """Lazy-init the OpenAI client so missing keys only fail at call time."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

MODEL = "gpt-4o-mini"
MAX_TOKENS = 350
TEMPERATURE = 0.3
MAX_HEADLINES = 20
MAX_RETRIES = 2

_SYSTEM_PROMPT = """\
You are a concise financial analyst. Given a list of news headlines:
1. State overall sentiment in ONE word: Bullish | Bearish | Neutral | Mixed
2. Summarise the 2-3 most important themes (1 sentence each)
3. Flag any notable risks in 1 sentence

Keep the entire response under 220 words. Be direct — no fluff.\
"""


# ─── Public API ───────────────────────────────────────────────────────────────


async def analyze_sentiment(
    headlines: list[str], context: str = ""
) -> Optional[str]:
    """
    Run GPT-4o-mini sentiment analysis on a list of news headlines.

    Args:
        headlines: Raw headline strings (will be capped at MAX_HEADLINES).
        context:   Optional prefix giving portfolio context to the model.

    Returns:
        Model response string, or None if all retries fail.
    """
    if not headlines:
        return None

    capped = headlines[:MAX_HEADLINES]
    headlines_block = "\n".join(f"• {h}" for h in capped)
    user_msg = (
        (f"Context: {context}\n\n" if context else "")
        + f"Headlines:\n{headlines_block}"
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await _get_client().chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
            )
            text = response.choices[0].message.content or ""
            logger.debug(f"OpenAI sentiment ok (attempt {attempt})")
            return text.strip()
        except Exception as exc:
            logger.warning(f"OpenAI attempt {attempt}/{MAX_RETRIES} failed: {exc}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2**attempt)

    logger.error("All OpenAI retries exhausted — returning None")
    return None


async def summarize_morning_report(
    holdings: list[dict], headlines: list[str]
) -> Optional[str]:
    """
    Convenience wrapper that builds portfolio context automatically.

    Args:
        holdings: List of holding dicts (must include 'symbol' key).
        headlines: Headlines gathered for those symbols.
    """
    symbols = [h["symbol"] for h in holdings]
    context = f"Portfolio: {', '.join(symbols)}"
    return await analyze_sentiment(headlines, context=context)