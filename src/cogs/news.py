"""
News cog — handles !news [SYMBOL].

Fetches headlines via the news service, runs GPT-4o-mini sentiment
analysis (respecting the per-user daily limit), and renders a rich embed.
"""
from __future__ import annotations

import os

import discord
from discord.ext import commands
from loguru import logger

from src.db import queries
from src.services.news import fetch_headlines_multi
from src.services.sentiment import analyze_sentiment

OPENAI_DAILY_LIMIT: int = int(os.getenv("OPENAI_DAILY_LIMIT", "5"))
MAX_SYMBOLS_NEWS: int = 5   # cap to avoid spammy embeds
MAX_HEADLINES_SHOWN: int = 8


class NewsCog(commands.Cog, name="News"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="news")
    async def news(self, ctx: commands.Context, symbol: str = None) -> None:
        """
        Fetch news for your holdings (or a specific symbol) with AI sentiment.

        Examples:
          !news          → news for all holdings
          !news TSLA     → news for TSLA only
        """
        user_id = await queries.upsert_user(str(ctx.author.id), str(ctx.author))

        # ── Resolve symbols ───────────────────────────────────────────────────
        if symbol:
            symbols = [symbol.upper()]
        else:
            holdings = await queries.get_holdings(user_id)
            if not holdings:
                await ctx.send(
                    "📭 You have no holdings. "
                    "Add some with `!addstock SYMBOL QTY COST` first."
                )
                return
            symbols = [h["symbol"] for h in holdings]

        # ── OpenAI rate-limit check ───────────────────────────────────────────
        usage = await queries.get_openai_usage(user_id)
        ai_enabled = usage < OPENAI_DAILY_LIMIT
        if not ai_enabled:
            await ctx.send(
                f"⚠️ Daily AI analysis limit reached (`{OPENAI_DAILY_LIMIT}` calls). "
                "News shown without sentiment summary."
            )

        # ── Fetch headlines ───────────────────────────────────────────────────
        async with ctx.typing():
            headlines = await fetch_headlines_multi(symbols[:MAX_SYMBOLS_NEWS])

            if not headlines:
                await ctx.send(
                    f"❌ No news found for `{'`, `'.join(symbols)}`."
                )
                return

            # ── AI sentiment ─────────────────────────────────────────────────
            sentiment: str | None = None
            if ai_enabled:
                context = f"Portfolio symbols: {', '.join(symbols)}"
                sentiment = await analyze_sentiment(headlines, context=context)
                if sentiment:
                    await queries.increment_openai_usage(user_id)

        # ── Build embed ───────────────────────────────────────────────────────
        title_symbols = ", ".join(symbols[:MAX_SYMBOLS_NEWS])
        embed = discord.Embed(
            title=f"📰 News — {title_symbols}",
            color=discord.Color.blurple(),
        )

        if sentiment:
            embed.add_field(
                name="🤖 AI Sentiment",
                value=sentiment[:1024],
                inline=False,
            )
            embed.add_field(name="\u200b", value="\u200b", inline=False)

        for headline in headlines[:MAX_HEADLINES_SHOWN]:
            embed.add_field(name="•", value=headline[:200], inline=False)

        remaining = OPENAI_DAILY_LIMIT - (usage + (1 if sentiment else 0))
        embed.set_footer(text=f"AI calls remaining today: {max(remaining, 0)}")

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NewsCog(bot))