"""
Analyze service — Technical indicators, Institutional holdings, Sentiment score.

fetch_technical(symbol)      -> dict
fetch_institutional(symbol)  -> list[dict]
fetch_sentiment_score(symbol, headlines) -> dict
build_analysis(symbol, headlines) -> dict
"""
from __future__ import annotations

import asyncio
from typing import Any

import yfinance as yf
from loguru import logger


# ─── Technical Analysis ───────────────────────────────────────────────────────

def _sync_technical(symbol: str) -> dict:
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="6mo")

    if hist.empty:
        return {}

    close = hist["Close"]

    # Moving Averages
    ma20 = close.rolling(20).mean().iloc[-1]
    ma50 = close.rolling(50).mean().iloc[-1]
    ma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None

    # RSI (14)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    rsi = (100 - (100 / (1 + rs))).iloc[-1]

    # MACD
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd_line = (ema12 - ema26).iloc[-1]
    signal_line = (ema12 - ema26).ewm(span=9).mean().iloc[-1]
    macd_hist = macd_line - signal_line

    price_now = close.iloc[-1]

    return {
        "price": round(price_now, 2),
        "ma20": round(ma20, 2),
        "ma50": round(ma50, 2),
        "ma200": round(ma200, 2) if ma200 else None,
        "rsi": round(rsi, 2),
        "macd_line": round(macd_line, 4),
        "signal_line": round(signal_line, 4),
        "macd_hist": round(macd_hist, 4),
        "above_ma20": price_now > ma20,
        "above_ma50": price_now > ma50,
        "above_ma200": (price_now > ma200) if ma200 else None,
    }


async def fetch_technical(symbol: str) -> dict:
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _sync_technical, symbol.upper())
    except Exception as e:
        logger.warning(f"Technical fetch failed for {symbol}: {e}")
        return {}


# ─── Institutional Holdings ───────────────────────────────────────────────────

def _sync_institutional(symbol: str) -> list[dict]:
    ticker = yf.Ticker(symbol)
    holders = ticker.institutional_holders
    if holders is None or holders.empty:
        return []

    results = []
    for _, row in holders.head(10).iterrows():
        results.append({
            "holder": row.get("Holder", "Unknown"),
            "shares": int(row.get("Shares", 0)),
            "pct_out": round(float(row.get("% Out", 0)) * 100, 2),
            "value": int(row.get("Value", 0)),
        })
    return results


async def fetch_institutional(symbol: str) -> list[dict]:
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _sync_institutional, symbol.upper())
    except Exception as e:
        logger.warning(f"Institutional fetch failed for {symbol}: {e}")
        return []


# ─── Sentiment Score ──────────────────────────────────────────────────────────

def _score_sentiment(headlines: list[str]) -> dict:
    """Simple keyword-based sentiment scoring (no API needed)."""
    positive_words = [
        "surge", "rally", "gain", "jump", "beat", "record", "high",
        "growth", "profit", "buy", "bullish", "upgrade", "strong",
        "outperform", "rise", "soar", "boom", "positive"
    ]
    negative_words = [
        "fall", "drop", "decline", "loss", "miss", "cut", "bearish",
        "downgrade", "weak", "sell", "crash", "risk", "concern",
        "warning", "slide", "plunge", "negative", "layoff"
    ]

    pos = neg = 0
    for h in headlines:
        h_lower = h.lower()
        pos += sum(1 for w in positive_words if w in h_lower)
        neg += sum(1 for w in negative_words if w in h_lower)

    total = pos + neg
    if total == 0:
        score = 50
        label = "Neutral"
    else:
        score = int((pos / total) * 100)
        if score >= 65:
            label = "Bullish 🟢"
        elif score >= 45:
            label = "Neutral 🟡"
        else:
            label = "Bearish 🔴"

    return {"score": score, "label": label, "pos": pos, "neg": neg}


# ─── Signal Summary ───────────────────────────────────────────────────────────

def _build_signal(tech: dict, sentiment: dict) -> str:
    score = 0

    # RSI
    rsi = tech.get("rsi", 50)
    if rsi < 30:
        score += 2  # oversold → buy signal
    elif rsi < 50:
        score += 1
    elif rsi > 70:
        score -= 2  # overbought → sell signal
    elif rsi > 55:
        score -= 1

    # MA
    if tech.get("above_ma20"):
        score += 1
    if tech.get("above_ma50"):
        score += 1
    if tech.get("above_ma200"):
        score += 1

    # MACD
    if tech.get("macd_hist", 0) > 0:
        score += 1
    else:
        score -= 1

    # Sentiment
    s = sentiment.get("score", 50)
    if s >= 65:
        score += 1
    elif s < 35:
        score -= 1

    if score >= 4:
        return "🟢 **BUY** — แนวโน้มดี สัญญาณบวกหลายด้าน"
    elif score >= 1:
        return "🟡 **HOLD** — แนวโน้มกลาง รอจังหวะที่ชัดขึ้น"
    else:
        return "🔴 **CAUTION** — สัญญาณอ่อนแอ ควรระวัง"


# ─── Main Builder ─────────────────────────────────────────────────────────────

async def build_analysis(symbol: str, headlines: list[str]) -> dict:
    tech, inst = await asyncio.gather(
        fetch_technical(symbol),
        fetch_institutional(symbol),
    )
    sentiment = _score_sentiment(headlines)
    signal = _build_signal(tech, sentiment)

    return {
        "symbol": symbol.upper(),
        "technical": tech,
        "institutional": inst,
        "sentiment": sentiment,
        "signal": signal,
    }
