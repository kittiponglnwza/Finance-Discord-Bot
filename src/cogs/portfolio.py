"""
Portfolio cog — handles !addstock, !removestock, !port.
"""
from __future__ import annotations

from discord.ext import commands

from src.db import queries
from src.services.price import fetch_prices_batch
from src.utils.formatter import build_portfolio_embed


class PortfolioCog(commands.Cog, name="Portfolio"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── !addstock ─────────────────────────────────────────────────────────────

    @commands.command(name="addstock")
    async def add_stock(
        self,
        ctx: commands.Context,
        symbol: str,
        quantity: float,
        avg_cost: float,
    ) -> None:
        """
        Add shares to your portfolio (or top-up an existing holding).
        If the symbol already exists, your average cost is recalculated.

        Example: !addstock AAPL 10 175.50
        """
        if quantity <= 0:
            await ctx.send("❌ Quantity must be greater than 0.")
            return
        if avg_cost < 0:
            await ctx.send("❌ Average cost cannot be negative.")
            return

        symbol = symbol.upper()
        user_id = await queries.upsert_user(str(ctx.author.id), str(ctx.author))

        await queries.upsert_holding(user_id, symbol, quantity, avg_cost)
        await ctx.send(
            f"✅ Added **{quantity:g}×** `{symbol}` @ `${avg_cost:,.2f}` "
            f"to your portfolio.\nUse `!port` to see your updated summary."
        )

    # ── !removestock ──────────────────────────────────────────────────────────

    @commands.command(name="removestock")
    async def remove_stock(self, ctx: commands.Context, symbol: str) -> None:
        """
        Remove a holding entirely from your portfolio.

        Example: !removestock AAPL
        """
        symbol = symbol.upper()
        user_id = await queries.upsert_user(str(ctx.author.id), str(ctx.author))
        removed = await queries.remove_holding(user_id, symbol)
        if removed:
            await ctx.send(f"✅ Removed `{symbol}` from your portfolio.")
        else:
            await ctx.send(
                f"❌ `{symbol}` was not found in your portfolio.\n"
                "Use `!port` to see your current holdings."
            )

    # ── !port ─────────────────────────────────────────────────────────────────

    @commands.command(name="port")
    async def portfolio(self, ctx: commands.Context) -> None:
        """
        Show your full portfolio summary with live prices and P/L.
        """
        user_id = await queries.upsert_user(str(ctx.author.id), str(ctx.author))
        holdings = await queries.get_holdings(user_id)

        if not holdings:
            await ctx.send(
                "📭 Your portfolio is empty.\n"
                "Use `!addstock SYMBOL QTY COST` to add your first holding."
            )
            return

        async with ctx.typing():
            symbols = [h["symbol"] for h in holdings]
            prices = await fetch_prices_batch(symbols)

        embed = build_portfolio_embed(holdings, prices)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(PortfolioCog(bot))