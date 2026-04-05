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


class LeaderboardView(discord.ui.View):
    def __init__(self, db, uid: str, game: int):
        super().__init__(timeout=180)
        self.db = db
        self.uid = uid
        self.game = game
        self.mode = "daily"

    async def get_daily_embed(self) -> discord.Embed:
        rows = await self.db.get_leaderboard(self.game, limit=10)
        if not rows:
            return discord.Embed(
                title="📅 Daily Leaderboard",
                description="No daily scores yet today.\nShare your result from **dialed.gg** here! 🎨",
                color=COLOR_WARNING,
            )

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

        user_rank = await self.db.get_user_rank(self.uid, self.game)
        user_score = await self.db.get_existing_score(self.uid, self.game)
        if user_score is not None and user_rank is not None:
            embed.set_footer(text=f"You are #{user_rank} with {user_score}/50")
        else:
            embed.set_footer(text="Submit your score by sharing your daily result!")
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def get_all_time_embed(self) -> discord.Embed:
        rows = await self.db.get_all_time_leaderboard(limit=10)
        if not rows:
            return discord.Embed(
                title="🏆 All-Time Leaderboard",
                description="No scores recorded yet.",
                color=COLOR_WARNING,
            )

        lines = [
            "```text",
            "Rnk Name        Total       %-age  PB   G  🔥",
            "----------------------------------------------"
        ]
        
        for i, row in enumerate(rows, start=1):
            uid = row["user_id"]
            name = (row["username"][:10]).ljust(11)
            games = row["games"]
            total = row["total_score"]
            pb = row["pb"]
            
            max_pos = games * 50
            streak = await self.db.get_max_streak(uid)
            
            rank = f"{i}.".rjust(3)
            tot_str = f"{total:g}/{max_pos}".ljust(11)
            pct = f"{(total / max_pos * 100):.1f}%".ljust(6)
            pb_str = f"{pb:g}".ljust(4)
            g_str = str(games).ljust(2)
            strk = str(streak).rjust(2)

            lines.append(f"{rank} {name} {tot_str} {pct} {pb_str} {g_str} {strk}")
            
        lines.append("```")

        embed = discord.Embed(
            title="🏆 All-Time Leaderboard",
            description="\n".join(lines),
            color=COLOR_PRIMARY,
        )
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def update_view(self, interaction: discord.Interaction):
        if self.mode == "daily":
            embed = await self.get_daily_embed()
        else:
            embed = await self.get_all_time_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="lb_prev")
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.mode = "all_time" if self.mode == "daily" else "daily"
        await self.update_view(interaction)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="lb_next")
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.mode = "all_time" if self.mode == "daily" else "daily"
        await self.update_view(interaction)


class LeaderboardCog(commands.Cog, name="Leaderboard"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="leaderboard", description="Show the Dialed leaderboards (Daily / All-Time).")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        game = int(date.today().strftime("%Y%m%d"))
        
        view = LeaderboardView(self.bot.db, str(interaction.user.id), game)
        embed = await view.get_daily_embed()
        await interaction.followup.send(embed=embed, view=view)


def _mini_bar(score: float, max_score: float = 50.0, length: int = 10) -> str:
    filled = round((score / max_score) * length)
    return "█" * filled + "░" * (length - filled)


async def setup(bot: commands.Bot):
    await bot.add_cog(LeaderboardCog(bot))
