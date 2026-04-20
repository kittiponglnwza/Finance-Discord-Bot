"""
Alerts cog — handles all !alert, !alerts, !removealert commands.

This cog only handles Discord interaction.
All business logic lives in services/; all DB calls go through db/queries.
"""
from __future__ import annotations

from discord.ext import commands

from src.db import queries
from src.services.price import fetch_price
from src.utils.formatter import build_alert_list_embed


class AlertsCog(commands.Cog, name="Alerts"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── !alert ────────────────────────────────────────────────────────────────

    @commands.command(name="alert")
    async def create_alert(
        self,
        ctx: commands.Context,
        symbol: str,
        value: str,
        direction: str = "upper",
    ) -> None:
        """
        Create a price or % move alert.

        Examples:
          !alert AAPL 200 upper   → alert when AAPL ≥ $200
          !alert AAPL 150 lower   → alert when AAPL ≤ $150
          !alert AAPL 5%          → alert when AAPL moves ±5 %
        """
        symbol = symbol.upper()
        user_id = await queries.upsert_user(str(ctx.author.id), str(ctx.author))

        # ── Percent alert ────────────────────────────────────────────────────
        if value.endswith("%"):
            try:
                pct = float(value[:-1])
            except ValueError:
                await ctx.send(
                    "❌ Invalid percentage format. Example: `!alert AAPL 5%`"
                )
                return

            async with ctx.typing():
                price_data = await fetch_price(symbol)

            if not price_data:
                await ctx.send(
                    f"❌ Could not fetch a price for `{symbol}`. "
                    "Double-check the ticker and try again."
                )
                return

            alert_id = await queries.create_percent_alert(
                user_id, symbol, pct, price_data["price"]
            )
            await ctx.send(
                f"✅ **% Alert set!**\n"
                f"You'll be notified when `{symbol}` moves "
                f"**{pct:+.2f}%** from `${price_data['price']:,.2f}`\n"
                f"*(Alert ID: `#{alert_id}`)*"
            )
            return

        # ── Price alert ──────────────────────────────────────────────────────
        try:
            target_price = float(value.replace("$", "").replace(",", ""))
        except ValueError:
            await ctx.send(
                "❌ Invalid price format. Example: `!alert AAPL 200 upper`"
            )
            return

        if direction not in ("upper", "lower"):
            await ctx.send(
                "❌ Direction must be `upper` or `lower`.\n"
                "Example: `!alert AAPL 200 upper`"
            )
            return

        alert_id = await queries.create_price_alert(
            user_id, symbol, target_price, direction
        )
        verb = "rises above" if direction == "upper" else "drops below"
        await ctx.send(
            f"✅ **Price Alert set!**\n"
            f"You'll be notified when `{symbol}` **{verb}** "
            f"`${target_price:,.2f}`\n"
            f"*(Alert ID: `#{alert_id}`)*"
        )

    # ── !alerts ───────────────────────────────────────────────────────────────

    @commands.command(name="alerts")
    async def list_alerts(self, ctx: commands.Context) -> None:
        """List all your active alerts."""
        user_id = await queries.upsert_user(str(ctx.author.id), str(ctx.author))
        alerts = await queries.get_user_alerts(user_id)
        embed = build_alert_list_embed(alerts)
        await ctx.send(embed=embed)

    # ── !removealert ──────────────────────────────────────────────────────────

    @commands.command(name="removealert")
    async def remove_alert(self, ctx: commands.Context, alert_id: int) -> None:
        """
        Remove an alert by its ID.

        Example: !removealert 3
        """
        user_id = await queries.upsert_user(str(ctx.author.id), str(ctx.author))
        removed = await queries.deactivate_alert(alert_id, user_id)
        if removed:
            await ctx.send(f"✅ Alert `#{alert_id}` has been removed.")
        else:
            await ctx.send(
                f"❌ Alert `#{alert_id}` not found or doesn't belong to you.\n"
                "Use `!alerts` to see your active alerts."
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AlertsCog(bot))
