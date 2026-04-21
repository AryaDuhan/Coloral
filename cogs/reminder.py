"""
cogs/reminder.py — Posts a daily reminder at a configurable UTC time.
Admins can set the reminder channel per-server with /set_reminder_channel.
Fallback: REMINDER_CHANNEL_ID from config.py / env var.

Reminder time default: 18:30 UTC = 12:00 AM IST (midnight Indian time).
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta, time

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
    GAME_TZ,
)
from ui import PlayView

log = logging.getLogger("dialed.reminder")


class ReminderCog(commands.Cog, name="Reminder"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.daily_reminder.start()

    def cog_unload(self):
        self.daily_reminder.cancel()

    # ── Slash Commands ────────────────────────────────────────────────────────

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

        # Convert UTC time to IST for display
        ist_hour = (REMINDER_HOUR + 5) % 24
        ist_minute = (REMINDER_MINUTE + 30) % 60
        if REMINDER_MINUTE + 30 >= 60:
            ist_hour = (ist_hour + 1) % 24

        embed = discord.Embed(
            title="✅ Reminder Channel Updated",
            description=(
                f"Daily Dialed reminders will now be posted in {channel.mention}.\n\n"
                f"Reminders fire every day at "
                f"**{REMINDER_HOUR:02d}:{REMINDER_MINUTE:02d} UTC** "
                f"(**{ist_hour:02d}:{ist_minute:02d} IST**)."
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

    @app_commands.command(
        name="test_reminder",
        description="Send a test reminder right now to verify your setup.",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def test_reminder(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            await self._send_reminder(test=True)
            
            now = datetime.now(timezone.utc)
            scheduled_time = now.replace(
                hour=REMINDER_HOUR, minute=REMINDER_MINUTE, second=0, microsecond=0
            )
            if now >= scheduled_time:
                scheduled_time += timedelta(days=1)
            
            diff = scheduled_time - now
            hours, remainder = divmod(int(diff.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)

            embed = discord.Embed(
                title="✅ Test Reminder Sent",
                description=(
                    "Check your reminder channel — the test reminder should be there!\n\n"
                    f"⏳ The next automated daily reminder will fire in **{hours}h {minutes}m**."
                ),
                color=COLOR_SUCCESS,
            )
        except Exception as e:
            log.error(f"Test reminder failed: {e}")
            embed = discord.Embed(
                title="❌ Test Failed",
                description=f"Error: `{e}`\n\nMake sure you've used `/set_reminder_channel` first.",
                color=COLOR_ERROR,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @test_reminder.error
    async def test_reminder_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.MissingPermissions):
            embed = discord.Embed(
                title="🔒 Admin Only",
                description="Only server administrators can test reminders.",
                color=COLOR_ERROR,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            log.error(f"Unhandled error in test_reminder: {error}")

    @app_commands.command(
        name="restart",
        description="Restart the bot (useful when running with auto-start scripts).",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def restart_bot(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🔄 Restarting...",
            description="The bot is restarting. It will be back online in a few seconds!",
            color=COLOR_SUCCESS,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        log.info(f"Bot restart requested by {interaction.user} in {interaction.guild_id}")
        from cogs.lifecycle import shutdown_and_restart
        await shutdown_and_restart(self.bot)

    @restart_bot.error
    async def restart_bot_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.MissingPermissions):
            embed = discord.Embed(
                title="🔒 Admin Only",
                description="Only server administrators can restart the bot.",
                color=COLOR_ERROR,
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            log.error(f"Unhandled error in restart_bot: {error}")

    @app_commands.command(
        name="gitpull",
        description="Pull the latest updates from GitHub and restart the bot.",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(administrator=True)
    async def gitpull(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            import asyncio
            proc = await asyncio.create_subprocess_shell(
                "git pull",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode().strip()
            error = stderr.decode().strip()

            if proc.returncode != 0:
                embed = discord.Embed(
                    title="❌ Git Pull Failed",
                    description=f"```\n{error or output}\n```",
                    color=COLOR_ERROR
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            embed = discord.Embed(
                title="✅ Git Pull",
                description=f"```\n{output}\n```\n🔄 Restarting bot to apply changes...",
                color=COLOR_SUCCESS
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            log.info(f"Git pull and restart requested by {interaction.user}")
            
            from cogs.lifecycle import shutdown_and_restart
            await shutdown_and_restart(self.bot)

        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"```{e}```",
                color=COLOR_ERROR
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            log.error(f"Unhandled error in gitpull: {e}")

    # ── Background task ───────────────────────────────────────────────────────

    @tasks.loop(minutes=1)
    async def daily_reminder(self):
        """
        Fires every minute. Uses catch-up logic:
        - If it's past the scheduled time AND we haven't sent today yet → send.
        - This means if the bot was offline at the scheduled time, it will
          send the reminder as soon as it comes back online.
        """
        now = datetime.now(timezone.utc)
        
        # Have we passed today's scheduled time?
        scheduled_today = now.replace(
            hour=REMINDER_HOUR, minute=REMINDER_MINUTE, second=0, microsecond=0
        )
        if now < scheduled_today:
            return  # Not yet time today

        # We're past the scheduled time. The "Game Day" is based on GAME_TZ.
        current_game_day_str = datetime.now(GAME_TZ).date().isoformat()

        # Check if we already sent for this Dialed Day
        last_sent = await self.bot.db.get_last_reminder_date()
        if last_sent == current_game_day_str:
            return  # Already sent for this Dialed Day

        # It's past the scheduled time and we haven't sent today — fire!
        log.info(f"Reminder due for Dialed Day {current_game_day_str} "
                 f"(scheduled {REMINDER_HOUR:02d}:{REMINDER_MINUTE:02d} UTC, now {now.strftime('%H:%M')} UTC)")
        
        # Persist that we sent so we don't double fire if the network takes longer than 1 min
        await self.bot.db.set_last_reminder_date(current_game_day_str)
        try:
            await self._send_reminder()
        except Exception as e:
            log.error(f"Unhandled error in _send_reminder: {e}")

    @daily_reminder.before_loop
    async def before_reminder(self):
        await self.bot.wait_until_ready()
        # Small delay to ensure DB is initialized
        await asyncio.sleep(5)
        log.info(
            f"Reminder loop started — scheduled for {REMINDER_HOUR:02d}:{REMINDER_MINUTE:02d} UTC daily"
        )

    # ── Dispatch ──────────────────────────────────────────────────────────────

    async def _send_reminder(self, test: bool = False):
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

        title = "🧪 Test Reminder" if test else "🎨 A New Color is Waiting!"
        embed = discord.Embed(
            title=title,
            description=(
                f"Today's Colorle puzzle {game_str} is live!\n\n"
                "Can you guess the color from memory?\n"
                "Click **Play Daily** below to start! 🎨\n\n"
                "Scores are tracked automatically. 🏆"
            ),
            color=COLOR_PRIMARY,
        )
        footer_text = f"{'Test reminder' if test else 'Daily reminder'}  •  {datetime.now(timezone.utc).strftime('%B %d, %Y')}"
        if test:
            now = datetime.now(timezone.utc)
            scheduled_time = now.replace(
                hour=REMINDER_HOUR, minute=REMINDER_MINUTE, second=0, microsecond=0
            )
            if now >= scheduled_time:
                scheduled_time += timedelta(days=1)
            diff = scheduled_time - now
            hours, remainder = divmod(int(diff.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            footer_text += f"  •  ⏳ Next reminder in {hours}h {minutes}m"

        embed.set_footer(text=footer_text)

        players = await self.bot.db.get_all_players()
        mention_str = " ".join(f"<@{p}>" for p in players) if players else ""

        sent_count = 0
        for ch_id in channel_ids:
            channel = self.bot.get_channel(ch_id)
            if channel is None:
                log.error(
                    f"Reminder channel {ch_id} not found. "
                    "Check the ID and bot permissions."
                )
                continue
            try:
                await channel.send(
                    content=mention_str[:2000] if mention_str else None,
                    embed=embed,
                    view=PlayView(),
                )
                sent_count += 1
                log.info(f"{'Test' if test else 'Daily'} reminder posted to channel {ch_id}")
            except discord.Forbidden:
                log.error(f"Missing permissions to send to channel {ch_id}")
            except discord.HTTPException as e:
                log.error(f"Failed to send reminder to {ch_id}: {e}")

        if sent_count == 0:
            log.error("Reminder was due but could not be sent to any channel!")
        else:
            log.info(f"Reminder sent to {sent_count} channel(s)")


async def setup(bot: commands.Bot):
    await bot.add_cog(ReminderCog(bot))
