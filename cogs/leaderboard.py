"""
cogs/leaderboard.py — /leaderboard for daily mode.
"""

import logging
import discord
from datetime import date
from discord import app_commands
from discord.ext import commands
from config import COLOR_PRIMARY, COLOR_WARNING

log = logging.getLogger("dialed.leaderboard")
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


class LeaderboardCog(commands.Cog, name="Leaderboard"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="leaderboard", description="Show today's daily leaderboard.")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        db = self.bot.db
        game = int(date.today().strftime("%Y%m%d"))

        rows = await db.get_leaderboard(game, limit=10)
        if not rows:
            embed = discord.Embed(
                title="📅 Daily Leaderboard",
                description="No daily scores yet today.\nShare your result from **dialed.gg** here! 🎨",
                color=COLOR_WARNING,
            )
            await interaction.followup.send(embed=embed)
            return

        lines = []
        for i, row in enumerate(rows, start=1):
            medal = MEDALS.get(i, f"**{i}.**")
            username = discord.utils.escape_markdown(row["username"])
            score = row["score"]
            bar = _mini_bar(score)
            lines.append(f"{medal} **{username}** — `{score}/50` {bar}")

        embed = discord.Embed(
            title="📅 Daily Leaderboard",
            description="\n".join(lines),
            color=COLOR_PRIMARY,
        )

        uid = str(interaction.user.id)
        user_rank = await db.get_user_rank(uid, game)
        user_score = await db.get_existing_score(uid, game)
        if user_score is not None and user_rank is not None:
            embed.set_footer(text=f"You are #{user_rank} with {user_score}/50")
        else:
            embed.set_footer(text="Submit your score by sharing your daily result!")
        embed.timestamp = discord.utils.utcnow()
        await interaction.followup.send(embed=embed)


def _mini_bar(score: float, max_score: float = 50.0, length: int = 10) -> str:
    filled = round((score / max_score) * length)
    return "█" * filled + "░" * (length - filled)


async def setup(bot: commands.Bot):
    await bot.add_cog(LeaderboardCog(bot))
