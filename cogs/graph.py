"""
cogs/graph.py — /graph slash command.
Generates a styled score-over-time line chart with matplotlib.
"""

import io
import logging
import discord
from discord import app_commands
from discord.ext import commands
from config import COLOR_WARNING, GRAPH_DAYS

log = logging.getLogger("dialed.graph")


class GraphCog(commands.Cog, name="Graph"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="graph",
        description=f"See your score trend over the last {GRAPH_DAYS} games.",
    )
    @app_commands.describe(player="The player to graph (defaults to you).")
    async def graph(
        self,
        interaction: discord.Interaction,
        player: discord.Member | None = None,
    ):
        await interaction.response.defer()

        target = player or interaction.user
        db     = self.bot.db

        records = await db.get_recent_scores(str(target.id), days=GRAPH_DAYS)

        if len(records) < 2:
            embed = discord.Embed(
                title="Not Enough Data",
                description=(
                    f"**{target.display_name}** needs at least 2 scores to generate a graph.\n"
                    "Keep playing **Colorle** and check back! 🎨"
                ),
                color=COLOR_WARNING,
            )
            await interaction.followup.send(embed=embed)
            return

        # ── Draw chart ────────────────────────────────────────────────────────
        buf = await _render_chart(
            records=records,
            username=target.display_name,
        )

        file  = discord.File(buf, filename="colorle_progress.png")
        embed = discord.Embed(
            title=f"📈 Score History — {target.display_name}",
            color=0xE96479,
        )
        embed.set_image(url="attachment://colorle_progress.png")
        embed.set_footer(text=f"Last {len(records)} games  •  Max score: 50")
        embed.timestamp = discord.utils.utcnow()

        await interaction.followup.send(embed=embed, file=file)


# ── Chart renderer ────────────────────────────────────────────────────────────

async def _render_chart(records: list[dict], username: str) -> io.BytesIO:
    """
    Build the matplotlib chart in memory and return a BytesIO PNG buffer.
    Imported inside the function so the bot still starts if matplotlib is missing
    (it will just error on /graph, not on startup).
    """
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend — must be set before pyplot import
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    import numpy as np

    game_labels = [f"#{r['game_number']}" for r in records]
    scores      = [r["score"] for r in records]
    x           = list(range(len(scores)))

    # ── Smooth trend line (moving average) ───────────────────────────────────
    window = min(3, len(scores))
    ma     = np.convolve(scores, np.ones(window) / window, mode="valid")
    ma_x   = list(range(window - 1, len(scores)))

    # ── Style ─────────────────────────────────────────────────────────────────
    BG       = "#1e1e2e"   # Dark background
    SURFACE  = "#2a2a3e"   # Card surface
    PINK     = "#E96479"   # Primary accent
    PURPLE   = "#9a82db"   # Trend line
    TEXT     = "#cdd6f4"   # Text
    GRIDLINE = "#313244"

    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=130)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(SURFACE)

    # Gradient fill under the score line
    ax.fill_between(x, scores, alpha=0.18, color=PINK, zorder=1)

    # Main score line
    ax.plot(x, scores, color=PINK, linewidth=2.5, marker="o",
            markersize=7, markerfacecolor=PINK, markeredgecolor=BG,
            markeredgewidth=1.5, zorder=3, label="Score")

    # Annotate each point
    for xi, yi in zip(x, scores):
        ax.annotate(
            f"{yi}",
            xy=(xi, yi),
            xytext=(0, 10),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            color=TEXT,
            fontweight="bold",
        )

    # Trend / moving-average line
    if len(ma) > 1:
        ax.plot(ma_x, ma, color=PURPLE, linewidth=1.8, linestyle="--",
                alpha=0.75, zorder=2, label=f"{window}-game avg")

    # Perfect-score reference line
    ax.axhline(y=50, color=TEXT, linestyle=":", linewidth=1, alpha=0.3, zorder=0)
    ax.text(len(x) - 0.5, 50.8, "max 50", color=TEXT, alpha=0.4, fontsize=7, ha="right")

    # ── Axes formatting ───────────────────────────────────────────────────────
    ax.set_xlim(-0.5, len(x) - 0.5)
    ax.set_ylim(max(0, min(scores) - 5), 53)
    ax.set_xticks(x)
    ax.set_xticklabels(game_labels, rotation=30, ha="right", fontsize=8, color=TEXT)
    ax.tick_params(colors=TEXT, which="both")
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))
    for spine in ax.spines.values():
        spine.set_edgecolor(GRIDLINE)
    ax.grid(axis="y", color=GRIDLINE, linewidth=0.8, alpha=0.6)

    ax.set_title(
        f"Colorle — {username}'s Score History",
        color=TEXT, fontsize=13, fontweight="bold", pad=14,
    )
    ax.set_ylabel("Score / 50", color=TEXT, fontsize=9)

    legend = ax.legend(fontsize=8, facecolor=SURFACE, edgecolor=GRIDLINE, labelcolor=TEXT)

    # Stats annotation box
    mean_ = sum(scores) / len(scores)
    best_ = max(scores)
    stats_txt = f"avg: {mean_:.2f}   best: {best_}"
    fig.text(
        0.99, 0.01, stats_txt,
        ha="right", va="bottom",
        color=TEXT, alpha=0.5, fontsize=7.5,
        transform=fig.transFigure,
    )

    plt.tight_layout(pad=1.2)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", facecolor=BG)
    plt.close(fig)
    buf.seek(0)
    return buf


async def setup(bot: commands.Bot):
    await bot.add_cog(GraphCog(bot))
