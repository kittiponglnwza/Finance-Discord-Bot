"""
Report cog — handles !report (manual morning report trigger) and !help.
"""
from __future__ import annotations

from discord.ext import commands

from src.db import queries
from src.services.news import fetch_headlines_multi
from src.services.price import fetch_prices_batch
from src.services.sentiment import summarize_morning_report
from src.utils.formatter import build_help_embed, build_report_embed

MAX_NEWS_SYMBOLS = 5


class ReportCog(commands.Cog, name="Report"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── !report ───────────────────────────────────────────────────────────────

    @commands.command(name="report")
    async def report(self, ctx: commands.Context) -> None:
        """
        Generate a personalised morning market report for your holdings.
        Includes live prices, daily changes, and an AI-powered news summary.
        """
        user_id = await queries.upsert_user(str(ctx.author.id), str(ctx.author))
        holdings = await queries.get_holdings(user_id)

        if not holdings:
            await ctx.send(
                "📭 Your portfolio is empty.\n"
                "Use `!addstock SYMBOL QTY COST` to add holdings first."
            )
            return

        async with ctx.typing():
            symbols = [h["symbol"] for h in holdings]
            prices = await fetch_prices_batch(symbols)
            headlines = await fetch_headlines_multi(symbols[:MAX_NEWS_SYMBOLS])
            summary = await summarize_morning_report(holdings, headlines)

        embed = build_report_embed(
            holdings, prices, summary or "_AI summary unavailable._"
        )
        await ctx.send(embed=embed)

    # ── !help ─────────────────────────────────────────────────────────────────

    @commands.command(name="help")
    async def help_menu(self, ctx: commands.Context) -> None:
        """Show the full command reference."""
        embed = build_help_embed()
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReportCog(bot))