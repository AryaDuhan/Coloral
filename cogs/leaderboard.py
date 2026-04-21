"""
cogs/leaderboard.py — /leaderboard for daily mode.
"""

import logging
import discord
from datetime import datetime, timezone
from discord import app_commands
from discord.ext import commands
from config import COLOR_PRIMARY, COLOR_WARNING, GAME_TZ

log = logging.getLogger("dialed.leaderboard")
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

# Linear page order: 0 = Daily, 1 = All-Time, 2 = Round Records
PAGES = ["daily", "all_time", "rounds"]


class LeaderboardView(discord.ui.View):
    def __init__(self, db, uid: str, game: int):
        super().__init__(timeout=180)
        self.db = db
        self.uid = uid
        self.game = game
        self.page = 0  # index into PAGES

    def _update_buttons(self):
        """Enable/disable arrows based on current page position."""
        self.btn_prev.disabled = (self.page == 0)
        self.btn_next.disabled = (self.page == len(PAGES) - 1)

    async def get_daily_embed(self) -> discord.Embed:
        rows = await self.db.get_leaderboard(self.game, limit=10)
        if not rows:
            return discord.Embed(
                title="📅 Daily Leaderboard",
                description="No daily scores yet today.\nClick **Play Daily** to be the first! 🎨",
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
        user_data = await self.db.get_existing_score(self.uid, self.game)
        if user_data is not None and user_rank is not None:
            user_score = user_data["score"] if isinstance(user_data, dict) else user_data
            embed.set_footer(text=f"You are #{user_rank} with {user_score}/50  •  Page 1/3")
        else:
            embed.set_footer(text="Submit your score by sharing your daily result!  •  Page 1/3")
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

        # Column widths — must fit ~56 chars for Discord code blocks
        W_RNK = 3
        W_NAME = 8
        W_TOTAL = 10
        W_PCT = 4
        W_PB = 5
        W_BR = 4
        W_WR = 4
        W_G = 2
        W_S = 2

        header = (
            f"{'#'.center(W_RNK)} {'Name'.center(W_NAME)} {'Total'.center(W_TOTAL)} "
            f"{'%'.center(W_PCT)} {'PB'.center(W_PB)} {'BR'.center(W_BR)} {'WR'.center(W_WR)} "
            f"{'G'.center(W_G)} {'S'.center(W_S)}"
        )
        sep = "─" * len(header)

        lines = ["```text", header, sep]

        for i, row in enumerate(rows, start=1):
            uid = row["user_id"]
            name = row["username"][:W_NAME].center(W_NAME)
            games = row["games"]
            total = row["total_score"]
            pb = row["pb"]
            br = row.get("best_round")
            wr = row.get("worst_round")

            max_pos = games * 50
            streak = await self.db.get_max_streak(uid)

            rank_s = f"{i}.".center(W_RNK)
            tot_s = f"{total:g}/{max_pos}".center(W_TOTAL)
            pct_s = f"{(total / max_pos * 100):.0f}%".center(W_PCT)
            pb_s = f"{pb:g}".center(W_PB)
            br_s = f"{br:g}".center(W_BR) if br is not None else "—".center(W_BR)
            wr_s = f"{wr:g}".center(W_WR) if wr is not None else "—".center(W_WR)
            g_s = str(games).center(W_G)
            strk_s = str(streak).center(W_S)

            lines.append(f"{rank_s} {name} {tot_s} {pct_s} {pb_s} {br_s} {wr_s} {g_s} {strk_s}")

        lines.append("```")

        embed = discord.Embed(
            title="🏆 All-Time Leaderboard",
            description="\n".join(lines),
            color=COLOR_PRIMARY,
        )
        embed.set_footer(text="Page 2/3")
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def get_rounds_embed(self) -> discord.Embed:
        rows = await self.db.get_round_records_leaderboard(limit=10)
        if not rows:
            return discord.Embed(
                title="🎯 Round Records",
                description="No round data recorded yet.",
                color=COLOR_WARNING,
            )

        # Best Round ranking (already sorted by best_round desc)
        best_lines = []
        for i, row in enumerate(rows, start=1):
            medal = MEDALS.get(i, f"**{i}.**")
            name = discord.utils.escape_markdown(row["username"])
            br = row.get("best_round")
            if br is not None:
                best_lines.append(f"{medal} **{name}** — `{br}/10`")

        # Worst Round ranking (sort by worst_round ascending — lowest is "worst")
        worst_sorted = sorted(
            [r for r in rows if r.get("worst_round") is not None],
            key=lambda x: x["worst_round"],
        )
        worst_lines = []
        for i, row in enumerate(worst_sorted, start=1):
            medal = MEDALS.get(i, f"**{i}.**")
            name = discord.utils.escape_markdown(row["username"])
            wr = row["worst_round"]
            worst_lines.append(f"{medal} **{name}** — `{wr}/10`")

        embed = discord.Embed(
            title="🎯 Round Records",
            color=COLOR_PRIMARY,
        )

        if best_lines:
            embed.add_field(
                name="🏆 Best Single Round",
                value="\n".join(best_lines),
                inline=True,
            )
        if worst_lines:
            embed.add_field(
                name="💀 Worst Single Round",
                value="\n".join(worst_lines),
                inline=True,
            )

        embed.set_footer(text="Best & worst individual round scores across all games  •  Page 3/3")
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def _get_embed(self) -> discord.Embed:
        mode = PAGES[self.page]
        if mode == "daily":
            return await self.get_daily_embed()
        elif mode == "all_time":
            return await self.get_all_time_embed()
        else:
            return await self.get_rounds_embed()

    async def update_view(self, interaction: discord.Interaction):
        self._update_buttons()
        embed = await self._get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="lb_prev")
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
        await self.update_view(interaction)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="lb_next")
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < len(PAGES) - 1:
            self.page += 1
        await self.update_view(interaction)


class LeaderboardCog(commands.Cog, name="Leaderboard"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="leaderboard", description="Show the Dialed leaderboards (Daily / All-Time / Round Records).")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        game = int(datetime.now(GAME_TZ).strftime("%Y%m%d"))
        
        # If no scores for today yet, try the latest game in the DB
        rows = await self.bot.db.get_leaderboard(game, limit=1)
        if not rows:
            latest = await self.bot.db.get_current_game_number()
            if latest:
                game = latest
        
        view = LeaderboardView(self.bot.db, str(interaction.user.id), game)
        view._update_buttons()
        embed = await view.get_daily_embed()
        await interaction.followup.send(embed=embed, view=view)


def _mini_bar(score: float, max_score: float = 50.0, length: int = 10) -> str:
    filled = round((score / max_score) * length)
    return "█" * filled + "░" * (length - filled)


async def setup(bot: commands.Bot):
    await bot.add_cog(LeaderboardCog(bot))
