"""
cogs/stats.py — /stats with paginated Daily + Single Player views.
"""

import logging
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
from config import COLOR_PRIMARY, COLOR_WARNING, COLOR_SUCCESS

log = logging.getLogger("dialed.stats")

# Linear page order: 0 = Daily, 1 = Single Player
PAGES = ["daily", "singleplayer"]


class StatsView(discord.ui.View):
    def __init__(self, db, target: discord.Member):
        super().__init__(timeout=180)
        self.db = db
        self.target = target
        self.uid = str(target.id)
        self.page = 0  # index into PAGES

    def _update_buttons(self):
        """Enable/disable arrows based on current page position."""
        self.btn_prev.disabled = (self.page == 0)
        self.btn_next.disabled = (self.page == len(PAGES) - 1)

    async def get_daily_embed(self) -> discord.Embed:
        s = await self.db.get_user_stats(self.uid)
        if not s:
            embed = discord.Embed(
                title="No Stats Yet",
                description=f"**{self.target.display_name}** hasn't submitted any daily scores yet.\nClick **Play Daily** to get started! 🎨",
                color=COLOR_WARNING,
            )
            embed.set_footer(text="Page 1/2")
            return embed

        streak = await self.db.get_win_streak(self.uid)
        recent = await self.db.get_recent_scores(self.uid, days=7)
        label = _score_label(s["mean_score"])

        embed = discord.Embed(title=f"🎨 Daily Stats — {self.target.display_name}", color=COLOR_PRIMARY)
        embed.set_thumbnail(url=self.target.display_avatar.url)

        embed.add_field(name="🎮 Games Played",   value=f"`{s['games_played']}`",          inline=True)
        embed.add_field(name="🎯 Average",        value=f"`{s['mean_score']}/50`  {label}", inline=True)
        embed.add_field(name="🏆 Personal Best",  value=f"`{s['personal_best']}/50`",      inline=True)
        embed.add_field(name="📉 Worst Score",    value=f"`{s['worst_score']}/50`",        inline=True)
        embed.add_field(name="🔥 Current Streak", value=_streak_display(streak),           inline=True)
        embed.add_field(name="\u200b",            value="\u200b",                          inline=True)

        # Individual round extremes (out of 10)
        if s.get("best_round") is not None:
            embed.add_field(name="🎯 Best Round",  value=f"`{s['best_round']}/10`",  inline=True)
        if s.get("worst_round") is not None:
            embed.add_field(name="💀 Worst Round", value=f"`{s['worst_round']}/10`", inline=True)
        if s.get("best_round") is not None or s.get("worst_round") is not None:
            embed.add_field(name="\u200b", value="\u200b", inline=True)

        # Timing Stats
        if s.get("avg_time") is not None:
            embed.add_field(
                name="⏱️ Round Timing",
                value=f"Avg: `{s['avg_time']}s` | Fast: `{s['fastest_time']}s` | Slow: `{s['slowest_time']}s`",
                inline=False
            )

        if recent:
            spark = _sparkline([r["score"] for r in recent])
            scores_fmt = "  ".join(f"`{r['score']}`" for r in recent[-7:])
            embed.add_field(name="📈 Recent (last 7)", value=f"{spark}\n{scores_fmt}", inline=False)

        embed.set_footer(text="/leaderboard for today's rankings  •  Page 1/2")
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def get_sp_embed(self) -> discord.Embed:
        s = await self.db.get_sp_user_stats(self.uid)
        if not s:
            embed = discord.Embed(
                title="🎲 No Single Player Stats",
                description=f"**{self.target.display_name}** hasn't played any single player games yet.\nUse `/color` and click **Play Single Player** to get started!",
                color=COLOR_WARNING,
            )
            embed.set_footer(text="Page 2/2")
            return embed

        recent = await self.db.get_sp_recent_scores(self.uid, limit=7)
        label = _score_label(s["mean_score"])

        embed = discord.Embed(title=f"🎲 Single Player Stats — {self.target.display_name}", color=COLOR_PRIMARY)
        embed.set_thumbnail(url=self.target.display_avatar.url)

        embed.add_field(name="🎮 Games Played",  value=f"`{s['games_played']}`",          inline=True)
        embed.add_field(name="🎯 Average",       value=f"`{s['mean_score']}/50`  {label}", inline=True)
        embed.add_field(name="🏆 Personal Best", value=f"`{s['personal_best']}/50`",      inline=True)
        embed.add_field(name="📉 Worst Score",   value=f"`{s['worst_score']}/50`",        inline=True)
        embed.add_field(name="\u200b",           value="\u200b",                          inline=True)
        embed.add_field(name="\u200b",           value="\u200b",                          inline=True)

        # Individual round extremes (out of 10)
        if s.get("best_round") is not None:
            embed.add_field(name="🎯 Best Round",  value=f"`{s['best_round']}/10`",  inline=True)
        if s.get("worst_round") is not None:
            embed.add_field(name="💀 Worst Round", value=f"`{s['worst_round']}/10`", inline=True)
        if s.get("best_round") is not None or s.get("worst_round") is not None:
            embed.add_field(name="\u200b", value="\u200b", inline=True)

        # Timing Stats
        if s.get("avg_time") is not None:
            embed.add_field(
                name="⏱️ Round Timing",
                value=f"Avg: `{s['avg_time']}s` | Fast: `{s['fastest_time']}s` | Slow: `{s['slowest_time']}s`",
                inline=False
            )

        if recent:
            spark = _sparkline([r["score"] for r in recent])
            scores_fmt = "  ".join(f"`{r['score']}`" for r in recent[-7:])
            embed.add_field(name="📈 Recent (last 7)", value=f"{spark}\n{scores_fmt}", inline=False)

        embed.set_footer(text="Unlimited practice mode  •  Page 2/2")
        embed.timestamp = discord.utils.utcnow()
        return embed

    async def _get_embed(self) -> discord.Embed:
        mode = PAGES[self.page]
        if mode == "daily":
            return await self.get_daily_embed()
        else:
            return await self.get_sp_embed()

    async def update_view(self, interaction: discord.Interaction):
        self._update_buttons()
        embed = await self._get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="stats_prev")
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
        await self.update_view(interaction)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="stats_next")
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < len(PAGES) - 1:
            self.page += 1
        await self.update_view(interaction)


class StatsCog(commands.Cog, name="Stats"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stats", description="View your Dialed stats (Daily + Single Player).")
    @app_commands.describe(player="Look up another player (defaults to you).")
    async def stats(self, interaction: discord.Interaction, player: discord.Member | None = None):
        target = player or interaction.user
        
        if target.bot:
            embed = discord.Embed(
                title="❌ Invalid Player",
                description="Bots don't play Colorle!",
                color=COLOR_WARNING,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
            
        await interaction.response.defer()

        view = StatsView(self.bot.db, target)
        view._update_buttons()
        embed = await view.get_daily_embed()
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(
        name="cleartoday",
        description="Clear your Colorle daily score for today, letting you submit again."
    )
    async def cleartoday(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        db = self.bot.db
        user_id = str(interaction.user.id)
        game_number = int(datetime.now(timezone.utc).strftime("%Y%m%d"))
        
        success = await db.delete_score(user_id, game_number)
        if success:
            embed = discord.Embed(
                title="✅ Score Cleared",
                description="Your score for today has been deleted. You can now play again!",
                color=COLOR_SUCCESS,
            )
        else:
            embed = discord.Embed(
                title="❌ No Score Found",
                description="I couldn't find a score for you today to delete.",
                color=COLOR_WARNING,
            )
            
        await interaction.followup.send(embed=embed, ephemeral=True)


def _score_label(mean: float) -> str:
    if mean >= 48: return "🌈 Chromatic Master"
    if mean >= 45: return "🎨 Color Expert"
    if mean >= 40: return "👁️ Sharp Eye"
    if mean >= 35: return "🖌️ Decent Palette"
    if mean >= 25: return "🎭 Learning the Hues"
    return "🌱 Just Getting Started"

def _streak_display(streak: int) -> str:
    if streak == 0:  return "`0 days`"
    if streak >= 30: return f"`{streak} days` 🔥🔥🔥"
    if streak >= 7:  return f"`{streak} days` 🔥🔥"
    if streak >= 3:  return f"`{streak} days` 🔥"
    return f"`{streak} day{'s' if streak != 1 else ''}`"

def _sparkline(scores: list[float]) -> str:
    bars = "▁▂▃▄▅▆▇█"
    if not scores: return ""
    lo, hi = min(scores), max(scores)
    rng = hi - lo or 1
    return "".join(bars[round((s - lo) / rng * 7)] for s in scores)


async def setup(bot: commands.Bot):
    await bot.add_cog(StatsCog(bot))
