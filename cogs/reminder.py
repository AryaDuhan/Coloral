"""
cogs/reminder.py — Posts a daily reminder at a configurable UTC time.
Configure REMINDER_CHANNEL_ID, REMINDER_HOUR, REMINDER_MINUTE in config.py
or via environment variables.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands, tasks

from config import (
    REMINDER_CHANNEL_ID,
    REMINDER_HOUR,
    REMINDER_MINUTE,
    COLOR_PRIMARY,
)
from ui import PlayView

log = logging.getLogger("dialed.reminder")


class ReminderCog(commands.Cog, name="Reminder"):
    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self._last_sent_date = None   # Track so we only fire once per day
        self.daily_reminder.start()

    def cog_unload(self):
        self.daily_reminder.cancel()

    # ── Background task ───────────────────────────────────────────────────────

    @tasks.loop(minutes=1)
    async def daily_reminder(self):
        """Fires every minute; posts the reminder once when the clock matches."""
        now = datetime.now(timezone.utc)

        if now.hour != REMINDER_HOUR or now.minute != REMINDER_MINUTE:
            return

        today = now.date()
        if self._last_sent_date == today:
            return   # Already sent today
        self._last_sent_date = today

        await self._send_reminder()

    @daily_reminder.before_loop
    async def before_reminder(self):
        await self.bot.wait_until_ready()

    # ── Dispatch ──────────────────────────────────────────────────────────────

    async def _send_reminder(self):
        if not REMINDER_CHANNEL_ID:
            log.warning(
                "REMINDER_CHANNEL_ID not configured — skipping daily reminder."
            )
            return

        channel = self.bot.get_channel(REMINDER_CHANNEL_ID)
        if channel is None:
            log.error(
                f"Reminder channel {REMINDER_CHANNEL_ID} not found. "
                "Check the ID and bot permissions."
            )
            return

        game_number = await self.bot.db.get_current_game_number()
        game_str = f"#**{game_number + 1}**" if game_number else ""

        embed = discord.Embed(
            title="🎨 A New Color is Waiting!",
            description=(
                f"Today's Dialed puzzle {game_str} is live!\n\n"
                "Can you guess the color from memory?\n"
                "**[▶️ Play now at dialed.gg](https://dialed.gg)**\n\n"
                "Share your result here once you're done — "
                "scores are tracked automatically. 🏆"
            ),
            color=COLOR_PRIMARY,
        )
        embed.set_footer(
            text=f"Daily reminder  •  {datetime.now(timezone.utc).strftime('%B %d, %Y')}"
        )

        try:
            await channel.send(embed=embed, view=PlayView())
            log.info(f"Daily reminder posted to channel {REMINDER_CHANNEL_ID}")
        except discord.Forbidden:
            log.error(
                f"Missing permissions to send to channel {REMINDER_CHANNEL_ID}"
            )
        except discord.HTTPException as e:
            log.error(f"Failed to send reminder: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ReminderCog(bot))
