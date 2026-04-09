"""
cogs/lifecycle.py — Manages bot startup/shutdown messages and the 6-hour auto-restart.
"""

import sys
import os
import asyncio
import logging
import discord
from discord.ext import commands, tasks
from config import COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, REMINDER_CHANNEL_ID

log = logging.getLogger("dialed.lifecycle")


async def broadcast(bot, embed: discord.Embed):
    """Sends the given embed to all registered reminder channels."""
    channels = set()
    try:
        db_channels = await bot.db.get_all_reminder_channels()
        channels.update(db_channels)
    except Exception:
        pass
    if REMINDER_CHANNEL_ID:
        channels.add(REMINDER_CHANNEL_ID)

    for ch_id in channels:
        channel = bot.get_channel(ch_id)
        if not channel:
            continue
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            pass


async def shutdown_and_restart(bot):
    """Broadcast shutdown, close the bot, then replace the process."""
    embed = discord.Embed(
        title="🔄 Restarting...",
        description="The bot is shutting down for a restart. Be right back!",
        color=COLOR_WARNING,
    )
    await broadcast(bot, embed)
    # Small delay to ensure messages are delivered
    await asyncio.sleep(1)
    await bot.close()
    # Exit cleanly at OS level — phone_start.sh's while-true loop will restart us
    os._exit(0)


class LifecycleCog(commands.Cog, name="Lifecycle"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.auto_restart.start()

    async def send_online_message(self):
        """Send the startup announcement. Called from bot.py after cogs load."""
        log.info("Announcing startup to channels...")
        embed = discord.Embed(
            title="🟢 Bot Online",
            description="The Dialed bot has successfully started and is ready to track scores!",
            color=COLOR_SUCCESS,
        )
        await broadcast(self.bot, embed)

    def cog_unload(self):
        self.auto_restart.cancel()

    @tasks.loop(hours=6)
    async def auto_restart(self):
        # Skip the immediate execution on startup
        if self.auto_restart.current_loop == 0:
            return

        log.info("6-hour auto-restart triggered.")
        await shutdown_and_restart(self.bot)

    @auto_restart.before_loop
    async def before_auto_restart(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(LifecycleCog(bot))
