"""
AI Sentiment service — thin async wrapper around Google Gemini.

Rules:
- Always use gemini-1.5-flash (cost control & high free tier limits)
- Hard cap on headlines sent per call
- Exponential backoff on failure
- Never raises — returns None on total failure
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional

from loguru import logger
import google.generativeai as genai

# ─── Config ───────────────────────────────────────────────────────────────────

_model: genai.GenerativeModel | None = None

MODEL_NAME = "gemini-1.5-flash"
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

def _get_model() -> genai.GenerativeModel:
    """Lazy-init the model so missing keys only fail at call time."""
    global _model
    if _model is None:
        # ใช้ API Key ของ Gemini แทน OpenAI
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        
        # ตั้งค่าโมเดล พร้อมใส่ System Prompt และ Temperature
        _model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            system_instruction=_SYSTEM_PROMPT,
            generation_config=genai.types.GenerationConfig(
                temperature=TEMPERATURE,
                max_output_tokens=MAX_TOKENS,
            )
        )
    return _model


# ─── Public API ───────────────────────────────────────────────────────────────


async def analyze_sentiment(
    headlines: list[str], context: str = ""
) -> Optional[str]:
    """
    Run Gemini sentiment analysis on a list of news headlines.

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
            model = _get_model()
            # ใช้ฟังก์ชันแบบ async ของ Gemini
            response = await model.generate_content_async(user_msg)
            
            # ดึงข้อความออกมา
            text = response.text or ""
            logger.debug(f"Gemini sentiment ok (attempt {attempt})")
            return text.strip()
            
        except Exception as exc:
            logger.warning(f"Gemini attempt {attempt}/{MAX_RETRIES} failed: {exc}")
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2**attempt)

    logger.error("All Gemini retries exhausted — returning None")
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