"""
All database access for the Finance Discord Bot goes through this module.
No cog or service should import aiosqlite directly.
"""
from __future__ import annotations

import os
from datetime import date
from typing import Optional

import aiosqlite
from loguru import logger

DB_PATH = os.getenv("DB_PATH", "data/finance_bot.db")


def _conn() -> aiosqlite.Connection:
    return aiosqlite.connect(DB_PATH)


# ─── Users ────────────────────────────────────────────────────────────────────


async def upsert_user(discord_id: str, username: str) -> int:
    """Insert or update a user; return their internal integer id."""
    async with _conn() as db:
        await db.execute("PRAGMA foreign_keys=ON;")
        await db.execute(
            "INSERT OR IGNORE INTO users (discord_id, username) VALUES (?, ?)",
            (discord_id, username),
        )
        await db.execute(
            "UPDATE users SET username = ? WHERE discord_id = ?",
            (username, discord_id),
        )
        await db.commit()
        async with db.execute(
            "SELECT id FROM users WHERE discord_id = ?", (discord_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0]


# ─── Alerts ───────────────────────────────────────────────────────────────────


async def create_price_alert(
    user_id: int, symbol: str, target_price: float, direction: str
) -> int:
    """Create a fixed-price alert. Returns the new alert id."""
    async with _conn() as db:
        cur = await db.execute(
            """
            INSERT INTO alerts (user_id, symbol, alert_type, target_price, direction)
            VALUES (?, ?, 'price', ?, ?)
            """,
            (user_id, symbol.upper(), target_price, direction),
        )
        await db.commit()
        return cur.lastrowid


async def create_percent_alert(
    user_id: int, symbol: str, pct_change: float, base_price: float
) -> int:
    """Create a percentage-move alert. Returns the new alert id."""
    async with _conn() as db:
        cur = await db.execute(
            """
            INSERT INTO alerts (user_id, symbol, alert_type, pct_change, base_price)
            VALUES (?, ?, 'percent', ?, ?)
            """,
            (user_id, symbol.upper(), pct_change, base_price),
        )
        await db.commit()
        return cur.lastrowid


async def get_user_alerts(user_id: int) -> list[dict]:
    """Return all active alerts for a single user."""
    async with _conn() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM alerts WHERE user_id = ? AND active = 1 ORDER BY created_at DESC",
            (user_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_all_active_alerts() -> list[dict]:
    """Return all active alerts joined with the user's discord_id — used by the poller."""
    async with _conn() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT a.*, u.discord_id
            FROM alerts a
            JOIN users u ON a.user_id = u.id
            WHERE a.active = 1
            ORDER BY a.symbol
            """
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def deactivate_alert(alert_id: int, user_id: int) -> bool:
    """Soft-delete an alert. Returns True if a row was affected."""
    async with _conn() as db:
        cur = await db.execute(
            "UPDATE alerts SET active = 0 WHERE id = ? AND user_id = ?",
            (alert_id, user_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def deactivate_alert_by_id(alert_id: int) -> None:
    """Soft-delete an alert by id only (used internally by the scheduler)."""
    async with _conn() as db:
        await db.execute("UPDATE alerts SET active = 0 WHERE id = ?", (alert_id,))
        await db.commit()


# ─── Holdings ─────────────────────────────────────────────────────────────────


async def upsert_holding(
    user_id: int, symbol: str, quantity: float, avg_cost: float
) -> None:
    """Add shares to a holding, computing a weighted-average cost if it exists."""
    symbol = symbol.upper()
    async with _conn() as db:
        async with db.execute(
            "SELECT quantity, avg_cost FROM holdings WHERE user_id = ? AND symbol = ?",
            (user_id, symbol),
        ) as cur:
            existing = await cur.fetchone()

        if existing:
            old_qty, old_cost = existing
            new_qty = old_qty + quantity
            new_cost = ((old_qty * old_cost) + (quantity * avg_cost)) / new_qty
            await db.execute(
                "UPDATE holdings SET quantity = ?, avg_cost = ? WHERE user_id = ? AND symbol = ?",
                (new_qty, new_cost, user_id, symbol),
            )
        else:
            await db.execute(
                "INSERT INTO holdings (user_id, symbol, quantity, avg_cost) VALUES (?, ?, ?, ?)",
                (user_id, symbol, quantity, avg_cost),
            )
        await db.commit()


async def remove_holding(user_id: int, symbol: str) -> bool:
    """Delete a holding. Returns True if a row was affected."""
    async with _conn() as db:
        cur = await db.execute(
            "DELETE FROM holdings WHERE user_id = ? AND symbol = ?",
            (user_id, symbol.upper()),
        )
        await db.commit()
        return cur.rowcount > 0


async def get_holdings(user_id: int) -> list[dict]:
    """Return all holdings for a user, ordered alphabetically."""
    async with _conn() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM holdings WHERE user_id = ? ORDER BY symbol",
            (user_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_all_holding_symbols() -> list[str]:
    """Return distinct symbols held by any user (for the morning report)."""
    async with _conn() as db:
        async with db.execute("SELECT DISTINCT symbol FROM holdings ORDER BY symbol") as cur:
            return [r[0] for r in await cur.fetchall()]


# ─── OpenAI Usage ─────────────────────────────────────────────────────────────


async def get_openai_usage(user_id: int) -> int:
    """Return today's OpenAI call count for a user."""
    today = date.today().isoformat()
    async with _conn() as db:
        async with db.execute(
            "SELECT call_count FROM openai_usage WHERE user_id = ? AND date = ?",
            (user_id, today),
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def increment_openai_usage(user_id: int) -> None:
    """Atomically increment today's OpenAI call count."""
    today = date.today().isoformat()
    async with _conn() as db:
        await db.execute(
            """
            INSERT INTO openai_usage (user_id, date, call_count) VALUES (?, ?, 1)
            ON CONFLICT (user_id, date) DO UPDATE SET call_count = call_count + 1
            """,
            (user_id, today),
        )
        await db.commit()