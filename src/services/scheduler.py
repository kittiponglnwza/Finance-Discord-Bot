"""
Scheduler service — sets up all recurring background jobs.

Jobs:
  • alert_poller    — runs every 60 s, checks price alerts
  • morning_report  — runs on cron, posts to configured channel
"""
from __future__ import annotations

import os

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from src.db import queries
from src.services.news import fetch_headlines_multi
from src.services.price import fetch_prices_batch
from src.services.sentiment import summarize_morning_report
from src.utils.formatter import build_report_embed

# ─── Config ───────────────────────────────────────────────────────────────────

REPORT_CHANNEL_ID: int = int(os.getenv("MORNING_REPORT_CHANNEL_ID", "0"))
REPORT_HOUR: int = int(os.getenv("MORNING_REPORT_HOUR", "7"))
REPORT_MINUTE: int = int(os.getenv("MORNING_REPORT_MINUTE", "0"))
REPORT_TZ: str = os.getenv("MORNING_REPORT_TIMEZONE", "America/New_York")
POLL_INTERVAL: int = int(os.getenv("ALERT_POLL_INTERVAL", "60"))


# ─── Setup ────────────────────────────────────────────────────────────────────


def setup_scheduler(bot: discord.Client) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=REPORT_TZ)

    scheduler.add_job(
        _poll_alerts,
        "interval",
        seconds=POLL_INTERVAL,
        args=[bot],
        id="alert_poller",
        replace_existing=True,
        max_instances=1,  # never overlap runs
    )

    scheduler.add_job(
        _send_morning_report,
        CronTrigger(hour=REPORT_HOUR, minute=REPORT_MINUTE, timezone=REPORT_TZ),
        args=[bot],
        id="morning_report",
        replace_existing=True,
        max_instances=1,
    )

    logger.info(
        f"Scheduler configured | alert poll: {POLL_INTERVAL}s | "
        f"report: {REPORT_HOUR:02d}:{REPORT_MINUTE:02d} {REPORT_TZ}"
    )
    return scheduler


# ─── Jobs ─────────────────────────────────────────────────────────────────────


async def _poll_alerts(bot: discord.Client) -> None:
    """Check every active alert against the latest cached prices."""
    try:
        alerts = await queries.get_all_active_alerts()
        if not alerts:
            return

        symbols = list({a["symbol"] for a in alerts})
        prices = await fetch_prices_batch(symbols)

        triggered_ids: list[int] = []

        for alert in alerts:
            price_data = prices.get(alert["symbol"])
            if not price_data:
                continue

            current_price: float = price_data["price"]

            if alert["alert_type"] == "price":
                hit = (
                    alert["direction"] == "upper"
                    and current_price >= alert["target_price"]
                ) or (
                    alert["direction"] == "lower"
                    and current_price <= alert["target_price"]
                )
            else:  # percent
                base = alert.get("base_price") or 0
                if base == 0:
                    continue
                actual_pct = (current_price - base) / base * 100
                hit = abs(actual_pct) >= abs(alert["pct_change"])

            if hit:
                await _dm_user(bot, alert, price_data)
                triggered_ids.append(alert["id"])

        # Deactivate all triggered alerts in one pass
        for aid in triggered_ids:
            await queries.deactivate_alert_by_id(aid)

        if triggered_ids:
            logger.info(f"Alert poller fired {len(triggered_ids)} alert(s)")

    except Exception as exc:
        logger.error(f"Alert poller error: {exc}")


async def _dm_user(
    bot: discord.Client, alert: dict, price_data: dict
) -> None:
    """Send a DM to the user whose alert was triggered."""
    try:
        user = await bot.fetch_user(int(alert["discord_id"]))
    except Exception as exc:
        logger.warning(f"Could not fetch user {alert['discord_id']}: {exc}")
        return

    symbol = alert["symbol"]
    current_price = price_data["price"]

    if alert["alert_type"] == "price":
        direction_str = "above ⬆️" if alert["direction"] == "upper" else "below ⬇️"
        body = (
            f"🔔 **Price Alert Triggered!**\n"
            f"`{symbol}` is now **${current_price:,.2f}** — "
            f"{direction_str} your target of **${alert['target_price']:,.2f}**"
        )
    else:
        base = alert["base_price"]
        actual_pct = (current_price - base) / base * 100
        body = (
            f"🔔 **% Move Alert Triggered!**\n"
            f"`{symbol}` has moved **{actual_pct:+.2f}%** "
            f"from your base of **${base:,.2f}**\n"
            f"Current price: **${current_price:,.2f}**"
        )

    try:
        await user.send(body)
        logger.info(f"Alert #{alert['id']} DM sent → {alert['discord_id']}")
    except discord.Forbidden:
        logger.warning(f"Cannot DM user {alert['discord_id']} (DMs disabled)")
    except Exception as exc:
        logger.error(f"DM failed for alert #{alert['id']}: {exc}")


async def _send_morning_report(bot: discord.Client) -> None:
    """Fetch market data + news, generate AI summary, post to report channel."""
    if not REPORT_CHANNEL_ID:
        logger.warning("MORNING_REPORT_CHANNEL_ID not configured — skipping report")
        return

    channel = bot.get_channel(REPORT_CHANNEL_ID)
    if channel is None:
        logger.error(f"Report channel {REPORT_CHANNEL_ID} not found")
        return

    try:
        symbols = await queries.get_all_holding_symbols()
        if not symbols:
            logger.info("No holdings in DB — skipping morning report")
            return

        prices = await fetch_prices_batch(symbols)
        headlines = await fetch_headlines_multi(symbols[:5])
        holdings = [{"symbol": s} for s in symbols]
        summary = await summarize_morning_report(holdings, headlines)
        embed = build_report_embed(holdings, prices, summary or "")
        await channel.send(embed=embed)
        logger.info(f"Morning report posted to channel {REPORT_CHANNEL_ID}")
    except Exception as exc:
        logger.error(f"Morning report failed: {exc}")