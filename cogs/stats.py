"""
cogs/stats.py — /stats for daily mode.
"""

import logging
import discord
from discord import app_commands
from discord.ext import commands
from config import COLOR_PRIMARY, COLOR_WARNING

log = logging.getLogger("dialed.stats")


class StatsCog(commands.Cog, name="Stats"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stats", description="View your Dialed daily stats.")
    @app_commands.describe(player="Look up another player (defaults to you).")
    async def stats(self, interaction: discord.Interaction, player: discord.Member | None = None):
        await interaction.response.defer()
        target = player or interaction.user
        db = self.bot.db

        s = await db.get_user_stats(str(target.id))
        if not s:
            embed = discord.Embed(
                title="No Stats Yet",
                description=f"**{target.display_name}** hasn't submitted any daily scores yet.\nShare a result from **dialed.gg** to get started! 🎨",
                color=COLOR_WARNING,
            )
            await interaction.followup.send(embed=embed)
            return

        streak = await db.get_win_streak(str(target.id))
        recent = await db.get_recent_scores(str(target.id), days=7)
        label = _score_label(s["mean_score"])

        embed = discord.Embed(title=f"🎨 Daily Stats — {target.display_name}", color=COLOR_PRIMARY)
        embed.set_thumbnail(url=target.display_avatar.url)

        embed.add_field(name="🎮 Games Played",   value=f"`{s['games_played']}`",          inline=True)
        embed.add_field(name="🎯 Average",        value=f"`{s['mean_score']}/50`  {label}", inline=True)
        embed.add_field(name="🏆 Personal Best",  value=f"`{s['personal_best']}/50`",      inline=True)
        embed.add_field(name="📉 Worst Score",    value=f"`{s['worst_score']}/50`",        inline=True)
        embed.add_field(name="🔥 Current Streak", value=_streak_display(streak),           inline=True)
        embed.add_field(name="\u200b",            value="\u200b",                          inline=True)

        if recent:
            spark = _sparkline([r["score"] for r in recent])
            scores_fmt = "  ".join(f"`{r['score']}`" for r in recent[-7:])
            embed.add_field(name="📈 Recent (last 7)", value=f"{spark}\n{scores_fmt}", inline=False)

        embed.set_footer(text="/leaderboard for today's rankings")
        embed.timestamp = discord.utils.utcnow()
        await interaction.followup.send(embed=embed)


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
