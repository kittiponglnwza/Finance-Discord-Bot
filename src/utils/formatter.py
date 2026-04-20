"""
All Discord Embed construction lives here so cogs stay thin.
"""
from __future__ import annotations

from datetime import datetime, timezone

import discord


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _now() -> datetime:
    # อัปเดตให้ใช้ discord.utils.utcnow() เพื่อความเสถียรของเวลาใน Discord
    return discord.utils.utcnow()


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
        title="✨ Finance Bot — Command Center",
        description="ผู้ช่วยส่วนตัวสำหรับการลงทุนและจัดการพอร์ตของคุณบน Discord 🚀",
        color=discord.Color.brand_green(),
        timestamp=_now(),
    )

    embed.add_field(
        name="📊 Analysis & Market",
        value=(
            "> `!analyze SYMBOL` — วิเคราะห์หุ้นเชิงลึก (Technical, Big Money)\n"
            "> `!report` — สรุปรายงานตลาดช่วงเช้าของคุณ"
        ),
        inline=False,
    )

    embed.add_field(
        name="💼 Portfolio Management",
        value=(
            "> `!port` — สรุปพอร์ตโฟลิโอพร้อมดู P/L (กำไร/ขาดทุน) แบบ Real-time\n"
            "> `!addstock SYMBOL QTY COST` — เพิ่มหุ้น หรือ ซื้อถัวเฉลี่ย\n"
            "> `!removestock SYMBOL` — ลบหุ้นออกจากพอร์ต"
        ),
        inline=False,
    )

    embed.add_field(
        name="🔔 Smart Alerts",
        value=(
            "> `!alert SYMBOL PRICE upper|lower` — เตือนเมื่อราคา ทะลุขึ้น/ร่วงลง\n"
            "> `!alert SYMBOL PCT%` — เตือนเมื่อราคาสวิงกี่ %\n"
            "> `!alerts` — ดูรายการแจ้งเตือนที่ทำงานอยู่\n"
            "> `!removealert ID` — ยกเลิกการแจ้งเตือนตาม ID"
        ),
        inline=False,
    )

    embed.add_field(
        name="📰 News & AI Sentiment",
        value=(
            "> `!news` — สรุปข่าวหุ้นในพอร์ต พร้อมวิเคราะห์อารมณ์ตลาดด้วย AI\n"
            "> `!news SYMBOL` — ค้นหาข่าวเฉพาะหุ้นตัวนั้นๆ"
        ),
        inline=False,
    )

    embed.set_footer(
        text="💡 พิมพ์คำสั่งด้านบนเพื่อใช้งาน • ราคาอัปเดตทุกๆ 60 วินาที • AI limit: 5 ครั้ง/วัน"
    )
    
    return embed