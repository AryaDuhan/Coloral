"""
cogs/lifecycle.py — Manages bot startup/shutdown messages and the 6-hour auto-restart.
"""

import sys
import logging
import discord
from discord.ext import commands, tasks
from config import COLOR_SUCCESS, COLOR_WARNING

log = logging.getLogger("dialed.lifecycle")


class LifecycleCog(commands.Cog, name="Lifecycle"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.auto_restart.start()

    def cog_unload(self):
        self.auto_restart.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        # Only send the startup message once per process
        if getattr(self, "_startup_sent", False):
            return
        self._startup_sent = True

        log.info("Announcing startup to channels...")
        embed = discord.Embed(
            title="🟢 Bot Online",
            description="The Dialed bot has successfully started (or restarted) and is ready to track scores!",
            color=COLOR_SUCCESS,
        )
        await self._broadcast(embed)

    @tasks.loop(hours=6)
    async def auto_restart(self):
        # Skip the immediate execution on startup
        if self.auto_restart.current_loop == 0:
            return

        log.info("6-hour auto-restart triggered.")
        embed = discord.Embed(
            title="🔄 Auto-Restarting",
            description="The bot is performing its scheduled 6-hour cache reset. Be right back in 5 seconds!",
            color=COLOR_WARNING,
        )
        await self._broadcast(embed)
        
        # Replace the current process with a fresh bot instance (same terminal)
        await self.bot.close()
        import sys, os
        os.execv(sys.executable, [sys.executable, "bot.py"])

    @auto_restart.before_loop
    async def before_auto_restart(self):
        await self.bot.wait_until_ready()

    async def _broadcast(self, embed: discord.Embed):
        """Sends the given embed to all registered reminder channels."""
        channels = set()
        db_channels = await self.bot.db.get_all_reminder_channels()
        channels.update(db_channels)

        # Also fallback to the SCORE_CHANNEL_ID if imported, but usually config channels is enough here.
        # We'll just rely on the DB channels since that's verified to be set.
        
        for ch_id in channels:
            channel = self.bot.get_channel(ch_id)
            if not channel:
                continue
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(LifecycleCog(bot))
