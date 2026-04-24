"""
cogs/lifecycle.py — Manages bot startup/shutdown messages and admin commands.
"""

import asyncio
import logging
import discord
from discord.ext import commands
from datetime import datetime, timezone
from config import COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, REMINDER_CHANNEL_ID, BOT_OWNER_ID, GAME_TZ

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


class LifecycleCog(commands.Cog, name="Lifecycle"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def send_online_message(self):
        """Send the startup announcement. Called from bot.py after cogs load."""
        log.info("Announcing startup to channels...")
        embed = discord.Embed(
            title="🟢 Bot Online",
            description="The Colorle bot has successfully started and is ready to track scores!",
            color=COLOR_SUCCESS,
        )
        await broadcast(self.bot, embed)

    # ── Owner-only commands ────────────────────────────────────────────────

    @discord.app_commands.command(name="shutdown", description="Shut down the bot completely (owner only).")
    async def shutdown_cmd(self, interaction: discord.Interaction):
        if str(interaction.user.id) != str(BOT_OWNER_ID):
            await interaction.response.send_message("❌ This command is restricted to the bot owner.", ephemeral=True)
            return

        await interaction.response.send_message("🚭 Shutting down...", ephemeral=True)
        await asyncio.sleep(1)
        await self.bot.close()

    @discord.app_commands.command(
        name="admindeletescore",
        description="Delete any user's score for a specific day (owner only)."
    )
    @discord.app_commands.describe(
        player="The user whose score to delete.",
        game_date="The date in YYYYMMDD format (e.g. 20260416). Defaults to today."
    )
    async def admin_delete_score(
        self,
        interaction: discord.Interaction,
        player: discord.Member,
        game_date: str | None = None,
    ):
        if str(interaction.user.id) != str(BOT_OWNER_ID):
            await interaction.response.send_message("❌ This command is restricted to the bot owner.", ephemeral=True)
            return

        game_number = int(game_date) if game_date else int(datetime.now(GAME_TZ).strftime("%Y%m%d"))
        user_id = str(player.id)

        success = await self.bot.db.delete_score(user_id, game_number)
        if success:
            embed = discord.Embed(
                title="✅ Score Deleted",
                description=(
                    f"Deleted **{player.display_name}**'s score for game **#{game_number}**.\n"
                    f"They can now play again for that day."
                ),
                color=COLOR_SUCCESS,
            )
        else:
            embed = discord.Embed(
                title="❌ No Score Found",
                description=f"No score found for **{player.display_name}** on game **#{game_number}**.",
                color=COLOR_WARNING,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.app_commands.command(
        name="adminaddscore",
        description="Manually insert a score for any user (owner only)."
    )
    @discord.app_commands.describe(
        player="The user to add a score for.",
        score="The total score (e.g. 44.57).",
        game_date="The date in YYYYMMDD format (e.g. 20260417). Defaults to latest game or today."
    )
    async def admin_add_score(
        self,
        interaction: discord.Interaction,
        player: discord.Member,
        score: float,
        game_date: str | None = None,
    ):
        if str(interaction.user.id) != str(BOT_OWNER_ID):
            await interaction.response.send_message("❌ This command is restricted to the bot owner.", ephemeral=True)
            return

        if score <= 0 or score > 50:
            await interaction.response.send_message("❌ Score must be between 0 and 50.", ephemeral=True)
            return

        if game_date:
            game_number = int(game_date)
        else:
            # Use latest game number from DB, fallback to today (UTC)
            latest = await self.bot.db.get_current_game_number()
            game_number = latest if latest else int(datetime.now(GAME_TZ).strftime("%Y%m%d"))

        user_id = str(player.id)
        username = player.display_name

        success = await self.bot.db.insert_score(user_id, username, game_number, score)
        if success:
            rank = await self.bot.db.get_user_rank(user_id, game_number)
            embed = discord.Embed(
                title="✅ Score Added",
                description=(
                    f"**{username}** — **{score}/50**\n"
                    f"Game **#{game_number}** • Rank **#{rank}**"
                ),
                color=COLOR_SUCCESS,
            )
        else:
            embed = discord.Embed(
                title="❌ Score Already Exists",
                description=f"**{username}** already has a score for game **#{game_number}**.\nUse `/admindeletescore` first to replace it.",
                color=COLOR_WARNING,
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(LifecycleCog(bot))
