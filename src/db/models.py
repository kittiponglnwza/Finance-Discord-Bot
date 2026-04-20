import os

import aiosqlite
from loguru import logger

DB_PATH = os.getenv("DB_PATH", "data/finance_bot.db")

# ─── DDL ──────────────────────────────────────────────────────────────────────

_CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT    UNIQUE NOT NULL,
    username   TEXT    NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_ALERTS = """
CREATE TABLE IF NOT EXISTS alerts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    symbol       TEXT    NOT NULL,
    alert_type   TEXT    NOT NULL CHECK (alert_type IN ('price', 'percent')),
    -- price alert fields
    target_price REAL,
    direction    TEXT CHECK (direction IN ('upper', 'lower')),
    -- percent alert fields
    pct_change   REAL,
    base_price   REAL,
    -- status
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
"""

_CREATE_HOLDINGS = """
CREATE TABLE IF NOT EXISTS holdings (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER NOT NULL,
    symbol    TEXT    NOT NULL,
    quantity  REAL    NOT NULL CHECK (quantity > 0),
    avg_cost  REAL    NOT NULL CHECK (avg_cost >= 0),
    added_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, symbol),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
"""

_CREATE_OPENAI_USAGE = """
CREATE TABLE IF NOT EXISTS openai_usage (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    date       TEXT    NOT NULL,
    call_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE (user_id, date),
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
"""

_PRAGMAS = [
    "PRAGMA journal_mode=WAL;",
    "PRAGMA foreign_keys=ON;",
    "PRAGMA synchronous=NORMAL;",
]


# ─── Init ─────────────────────────────────────────────────────────────────────


async def init_db() -> None:
    """Create all tables and apply performance pragmas."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        for pragma in _PRAGMAS:
            await db.execute(pragma)
        await db.execute(_CREATE_USERS)
        await db.execute(_CREATE_ALERTS)
        await db.execute(_CREATE_HOLDINGS)
        await db.execute(_CREATE_OPENAI_USAGE)
        await db.commit()
    logger.info(f"Database initialised at '{DB_PATH}'")