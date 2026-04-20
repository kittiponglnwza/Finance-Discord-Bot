import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv
from loguru import logger

from src.db.models import init_db
from src.services.scheduler import setup_scheduler

load_dotenv()

# ─── Logging ──────────────────────────────────────────────────────────────────

logger.add(
    "logs/bot.log",
    rotation="10 MB",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} | {message}",
)

# ─── Bot Setup ────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    help_command=None,
    case_insensitive=True,
)

COGS = [
    "src.cogs.alerts",
    "src.cogs.portfolio",
    "src.cogs.news",
    "src.cogs.report",
    "src.cogs.analyze",
]


# ─── Events ───────────────────────────────────────────────────────────────────


@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await init_db()
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info(f"Scheduler started | {len(bot.cogs)} cogs loaded")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Unknown command. Type `!help` to see all commands.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"❌ Missing required argument: `{error.param.name}`.\n"
            f"Use `!help` to see correct usage."
        )
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument: {error}\nUse `!help` for usage examples.")
    else:
        logger.error(f"Unhandled command error in '{ctx.command}': {error}")
        await ctx.send("❌ Something went wrong. Please try again later.")


# ─── Entry Point ──────────────────────────────────────────────────────────────


async def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("DISCORD_TOKEN is not set in environment variables.")

    async with bot:
        for cog in COGS:
            try:
                await bot.load_extension(cog)
                logger.info(f"✅ Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"❌ Failed to load cog {cog}: {e}")
        await bot.start(token)


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    asyncio.run(main())