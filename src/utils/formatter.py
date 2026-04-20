"""
All Discord Embed construction lives here so cogs stay thin.
"""
from __future__ import annotations

from datetime import datetime, timezone

import discord


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _price_color(change_pct: float) -> discord.Color:
    if change_pct > 0:
        return discord.Color.green()
    if change_pct < 0:
        return discord.Color.red()
    return discord.Color.light_grey()


def _trend_emoji(change_pct: float) -> str:
    if change_pct > 0:
        return "🟢"
    if change_pct < 0:
        return "🔴"
    return "⚪"


def fmt_usd(value: float) -> str:
    return f"${value:,.2f}"


def fmt_pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


# ─── Embeds ───────────────────────────────────────────────────────────────────


def build_price_embed(
    symbol: str, price: float, change: float, change_pct: float
) -> discord.Embed:
    emoji = _trend_emoji(change_pct)
    embed = discord.Embed(
        title=f"{emoji} {symbol}",
        color=_price_color(change_pct),
        timestamp=_now(),
    )
    embed.add_field(name="Price", value=fmt_usd(price), inline=True)
    embed.add_field(
        name="Change",
        value=f"{fmt_usd(change)} ({fmt_pct(change_pct)})",
        inline=True,
    )
    return embed


def build_portfolio_embed(
    holdings: list[dict], prices: dict[str, dict]
) -> discord.Embed:
    embed = discord.Embed(
        title="📊 Portfolio Summary",
        color=discord.Color.blurple(),
        timestamp=_now(),
    )

    total_value = 0.0
    total_cost = 0.0

    for h in holdings:
        symbol = h["symbol"]
        qty = h["quantity"]
        avg_cost = h["avg_cost"]
        price_data = prices.get(symbol, {})
        current_price = price_data.get("price", 0.0)

        cost_basis = qty * avg_cost
        current_value = qty * current_price
        pl = current_value - cost_basis
        pl_pct = (pl / cost_basis * 100) if cost_basis else 0.0

        total_value += current_value
        total_cost += cost_basis

        emoji = _trend_emoji(pl_pct)
        no_price = current_price == 0.0

        embed.add_field(
            name=f"{emoji} {symbol}",
            value=(
                f"Qty: `{qty:g}` @ `{fmt_usd(avg_cost)}`\n"
                f"Price: `{'N/A' if no_price else fmt_usd(current_price)}`\n"
                f"P/L: `{fmt_usd(pl)}` (`{fmt_pct(pl_pct)}`)"
            ),
            inline=True,
        )

    total_pl = total_value - total_cost
    total_pl_pct = (total_pl / total_cost * 100) if total_cost else 0.0
    emoji = _trend_emoji(total_pl_pct)

    # Spacer + summary row
    embed.add_field(name="\u200b", value="\u200b", inline=False)
    embed.add_field(name="💰 Total Value", value=fmt_usd(total_value), inline=True)
    embed.add_field(name="💳 Total Cost", value=fmt_usd(total_cost), inline=True)
    embed.add_field(
        name=f"{emoji} Total P/L",
        value=f"`{fmt_usd(total_pl)}` (`{fmt_pct(total_pl_pct)}`)",
        inline=True,
    )
    return embed


def build_alert_list_embed(alerts: list[dict]) -> discord.Embed:
    embed = discord.Embed(
        title="🔔 Your Active Alerts",
        color=discord.Color.gold(),
        timestamp=_now(),
    )
    if not alerts:
        embed.description = (
            "No active alerts.\n"
            "Use `!alert SYMBOL PRICE [upper|lower]` or `!alert SYMBOL PCT%` to add one."
        )
        return embed

    for a in alerts:
        if a["alert_type"] == "price":
            direction_str = "⬆️ Above" if a["direction"] == "upper" else "⬇️ Below"
            detail = f"{direction_str} `{fmt_usd(a['target_price'])}`"
        else:
            detail = (
                f"📈 `{fmt_pct(a['pct_change'])}` move "
                f"from base `{fmt_usd(a['base_price'])}`"
            )
        embed.add_field(
            name=f"[#{a['id']}] {a['symbol']}",
            value=detail,
            inline=False,
        )
    embed.set_footer(text=f"{len(alerts)} active alert(s)")
    return embed


def build_report_embed(
    holdings: list[dict],
    prices: dict[str, dict],
    sentiment_summary: str,
) -> discord.Embed:
    embed = discord.Embed(
        title="🌅 Morning Market Report",
        color=discord.Color.orange(),
        timestamp=_now(),
        description=sentiment_summary or "_AI summary unavailable._",
    )
    embed.add_field(name="\u200b", value="\u200b", inline=False)

    for h in holdings:
        symbol = h["symbol"]
        price_data = prices.get(symbol, {})
        price = price_data.get("price", 0.0)
        change_pct = price_data.get("change_pct", 0.0)
        emoji = _trend_emoji(change_pct)
        embed.add_field(
            name=f"{emoji} {symbol}",
            value=f"`{fmt_usd(price)}` ({fmt_pct(change_pct)})",
            inline=True,
        )

    embed.set_footer(text="Finance Bot • Morning Report")
    return embed


def build_help_embed() -> discord.Embed:
    embed = discord.Embed(
        title="📈 Finance Bot — Commands",
        description="Your personal investment assistant on Discord.",
        color=discord.Color.blue(),
        timestamp=_now(),
    )
    embed.add_field(
        name="🔔 Alerts",
        value=(
            "`!alert SYMBOL PRICE upper|lower` — Price alert\n"
            "`!alert SYMBOL PCT%` — % move alert\n"
            "`!alerts` — List your active alerts\n"
            "`!removealert ID` — Remove an alert by ID"
        ),
        inline=False,
    )
    embed.add_field(
        name="💼 Portfolio",
        value=(
            "`!addstock SYMBOL QTY COST` — Add / top-up a holding\n"
            "`!removestock SYMBOL` — Remove a holding\n"
            "`!port` — Portfolio summary with live P/L"
        ),
        inline=False,
    )
    embed.add_field(
        name="📰 News & Reports",
        value=(
            "`!news` — News for all holdings with AI sentiment\n"
            "`!news SYMBOL` — News for a specific symbol\n"
            "`!report` — Generate your morning market report"
        ),
        inline=False,
    )
    embed.set_footer(
        text="Prices refresh every 60 s  •  AI limit: 5 calls/user/day"
    )
    return embed