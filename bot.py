"""
Dialed Discord Bot — Main Entry Point
Run with: python bot.py
"""

import discord
from discord.ext import commands
import asyncio
import logging
import os
import traceback
from dotenv import load_dotenv
from database import Database
from logging.handlers import RotatingFileHandler

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler("dialed_bot.log", maxBytes=5*1024*1024, backupCount=3),
    ],
)
log = logging.getLogger("dialed")

# ── Bot Setup ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True  # Required to read message text

class DialedBot(commands.Bot):
    async def setup_hook(self):
        await self.db.init()

        from ui import PlayView
        self.add_view(PlayView())

        # Load all cogs (skip if already loaded — happens on os.execv restarts)
        exts = ["cogs.scores", "cogs.leaderboard", "cogs.stats", "cogs.graph", "cogs.reminder", "cogs.color", "cogs.lifecycle"]
        for cog in exts:
            try:
                if cog not in self.extensions:
                    await self.load_extension(cog)
                    log.info(f"  ✓ Loaded {cog}")
            except Exception as e:
                log.error(f"  ✗ Failed to load {cog}: {e}")

        # Sync slash commands globally
        try:
            synced = await self.tree.sync()
            log.info(f"Synced {len(synced)} slash command(s)")
        except Exception as e:
            log.error(f"Failed to sync commands: {e}")

bot = DialedBot(command_prefix="!", intents=intents)
bot.db = Database("dialed.db")


# ── Events ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="dialed.gg 🎨"
        )
    )

    # Announce that the bot is online
    lifecycle_cog = bot.get_cog("Lifecycle")
    if lifecycle_cog:
        await lifecycle_cog.send_online_message()

    log.info("Bot is ready!")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    log.error("".join(traceback.format_exception(type(error), error, error.__traceback__)))


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise ValueError("DISCORD_TOKEN not found in environment. Check your .env file.")
    bot.run(token, log_handler=None)  # We handle logging ourselves
