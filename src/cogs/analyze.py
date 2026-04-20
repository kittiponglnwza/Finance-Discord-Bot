"""
Analyze cog — !analyze SYMBOL
Full stock analysis: Technical + Institutional + Sentiment + Signal
"""
from __future__ import annotations

import discord
from discord.ext import commands

from src.services.analyze import build_analysis
from src.services.news import fetch_headlines


class AnalyzeCog(commands.Cog, name="Analyze"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="analyze", aliases=["an", "วิเคราะห์"])
    async def analyze(self, ctx: commands.Context, symbol: str = "") -> None:
        """
        วิเคราะห์หุ้นแบบครบวงจร: Technical + Big Money + Sentiment + สรุป
        Usage: !analyze NVDA
        """
        if not symbol:
            await ctx.send("❌ ระบุชื่อหุ้นด้วยครับ เช่น `!analyze NVDA`")
            return

        symbol = symbol.upper()

        async with ctx.typing():
            headlines = await fetch_headlines(symbol)
            data = await build_analysis(symbol, headlines)

        tech = data["technical"]
        inst = data["institutional"]
        sent = data["sentiment"]
        signal = data["signal"]

        if not tech:
            await ctx.send(f"❌ ไม่พบข้อมูลสำหรับ `{symbol}` ครับ")
            return

        embed = discord.Embed(
            title=f"📊 วิเคราะห์หุ้น {symbol}",
            color=discord.Color.blue(),
        )

        # ── Technical ──
        ma200_str = f"{tech['ma200']}" if tech.get("ma200") else "N/A"
        above_ma20 = "✅" if tech.get("above_ma20") else "❌"
        above_ma50 = "✅" if tech.get("above_ma50") else "❌"
        above_ma200 = "✅" if tech.get("above_ma200") else ("❌" if tech.get("ma200") else "N/A")

        rsi = tech.get("rsi", 0)
        rsi_label = "Oversold 🟢" if rsi < 30 else ("Overbought 🔴" if rsi > 70 else "Normal 🟡")

        macd_direction = "▲ Bullish" if tech.get("macd_hist", 0) > 0 else "▼ Bearish"

        embed.add_field(
            name="📈 Technical Analysis",
            value=(
                f"**ราคาปัจจุบัน:** ${tech['price']}\n"
                f"**MA20:** {tech['ma20']} {above_ma20}\n"
                f"**MA50:** {tech['ma50']} {above_ma50}\n"
                f"**MA200:** {ma200_str} {above_ma200}\n"
                f"**RSI(14):** {rsi} — {rsi_label}\n"
                f"**MACD:** {macd_direction} (Hist: {tech['macd_hist']})"
            ),
            inline=False,
        )

        # ── Institutional ──
        if inst:
            top3 = inst[:3]
            inst_text = "\n".join(
                f"**{i['holder']}** — {i['pct_out']}% of shares"
                for i in top3
            )
        else:
            inst_text = "_ไม่พบข้อมูล Institutional Holders_"

        embed.add_field(
            name="🏦 Big Money (Top Institutional Holders)",
            value=inst_text,
            inline=False,
        )

        # ── Sentiment ──
        embed.add_field(
            name="📰 News Sentiment",
            value=(
                f"**สถานะ:** {sent['label']}\n"
                f"**Score:** {sent['score']}/100\n"
                f"Positive signals: {sent['pos']} | Negative: {sent['neg']}"
            ),
            inline=False,
        )

        # ── Signal ──
        embed.add_field(
            name="🎯 สรุปสัญญาณ",
            value=signal,
            inline=False,
        )

        embed.set_footer(text="⚠️ ข้อมูลนี้ไม่ใช่คำแนะนำการลงทุน | ที่มา: yfinance")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AnalyzeCog(bot))
