"""
cogs/reminder.py — Posts a daily reminder at a configurable UTC time.
Admins can set the reminder channel per-server with /set_reminder_channel.
Fallback: REMINDER_CHANNEL_ID from config.py / env var.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import (
    REMINDER_CHANNEL_ID,
    REMINDER_HOUR,
    REMINDER_MINUTE,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_ERROR,
)
from ui import PlayView

log = logging.getLogger("dialed.reminder")


class ReminderCog(commands.Cog, name="Reminder"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last_sent_date = None  # Track so we only fire once per day
        self.daily_reminder.start()

    def cog_unload(self):
        self.daily_reminder.cancel()

    # ── Slash Command ─────────────────────────────────────────────────────────

    @app_commands.command(
        name="set_reminder_channel",
        description="Set the channel where daily Dialed reminders are posted.",
    )
    @app_commands.describe(channel="The text channel to receive daily reminders")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def set_reminder_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        # Check the bot can actually send messages there
        perms = channel.permissions_for(interaction.guild.me)
        if not perms.send_messages or not perms.embed_links:
            embed = discord.Embed(
                title="❌ Missing Permissions",
                description=(
                    f"I need **Send Messages** and **Embed Links** "
                    f"permissions in {channel.mention}."
                ),
                color=COLOR_ERROR,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        await self.bot.db.set_reminder_channel(
            str(interaction.guild_id), channel.id
        )

        embed = discord.Embed(
            title="✅ Reminder Channel Updated",
            description=(
                f"Daily Dialed reminders will now be posted in {channel.mention}.\n\n"
                f"Reminders fire every day at "
                f"**{REMINDER_HOUR:02d}:{REMINDER_MINUTE:02d} UTC**."
            ),
            color=COLOR_SUCCESS,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        log.info(
            f"Reminder channel for guild {interaction.guild_id} set to {channel.id}"
        )

    @set_reminder_channel.error
    async def set_reminder_channel_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.MissingPermissions):
            embed = discord.Embed(
                title="🔒 Admin Only",
                description="Only server administrators can change the reminder channel.",
                color=COLOR_ERROR,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            log.error(f"Unhandled error in set_reminder_channel: {error}")

    # ── Background task ───────────────────────────────────────────────────────

    @tasks.loop(minutes=1)
    async def daily_reminder(self):
        """Fires every minute; posts the reminder once when the clock matches."""
        now = datetime.now(timezone.utc)

        if now.hour != REMINDER_HOUR or now.minute != REMINDER_MINUTE:
            return

        today = now.date()
        if self._last_sent_date == today:
            return  # Already sent today
        self._last_sent_date = today

        await self._send_reminder()

    @daily_reminder.before_loop
    async def before_reminder(self):
        await self.bot.wait_until_ready()

    # ── Dispatch ──────────────────────────────────────────────────────────────

    async def _send_reminder(self):
        # Gather channel IDs: DB entries + legacy env fallback
        db_channels = await self.bot.db.get_all_reminder_channels()
        channel_ids = set(db_channels)

        if REMINDER_CHANNEL_ID:
            channel_ids.add(REMINDER_CHANNEL_ID)

        if not channel_ids:
            log.warning(
                "No reminder channels configured — skipping daily reminder. "
                "Use /set_reminder_channel in your server."
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

        for ch_id in channel_ids:
            channel = self.bot.get_channel(ch_id)
            if channel is None:
                log.error(
                    f"Reminder channel {ch_id} not found. "
                    "Check the ID and bot permissions."
                )
                continue
            try:
                await channel.send(embed=embed, view=PlayView())
                log.info(f"Daily reminder posted to channel {ch_id}")
            except discord.Forbidden:
                log.error(f"Missing permissions to send to channel {ch_id}")
            except discord.HTTPException as e:
                log.error(f"Failed to send reminder to {ch_id}: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ReminderCog(bot))
