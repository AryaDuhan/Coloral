"""
cogs/scores.py — Listens for dialed.gg daily score pastes and records them.
"""

import re
import logging
import discord
from datetime import datetime, date
from discord.ext import commands
from config import CONFIRM_EMOJI, SCORE_CHANNEL_ID, COLOR_SUCCESS, COLOR_WARNING

log = logging.getLogger("dialed.scores")

# Matches: "Dialed Daily — Apr 5\n40.41/50 🟨🟧🟩🟧🟨\ndialed.gg?d=1&s=40.41"
DAILY_PATTERN = re.compile(
    r"Dialed\s+Daily\s*[—\-–]\s*(\w+\s+\d+).*?([\d]+(?:\.[\d]+)?)\s*/\s*50",
    re.IGNORECASE | re.DOTALL)
# Matches: "dialed.gg?d=1&s=46.24" (just the URL)
DAILY_URL = re.compile(r"dialed\.gg\?d=1&s=([\d]+(?:\.[\d]+)?)", re.IGNORECASE)
URL_PATTERN = re.compile(r"dialed\.gg", re.IGNORECASE)
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def _date_to_game(d: date) -> int:
    return int(d.strftime("%Y%m%d"))


def _parse_date(s: str) -> date | None:
    try:
        return datetime.strptime(f"{s.strip()} {datetime.now().year}", "%b %d %Y").date()
    except ValueError:
        return None


class ScoresCog(commands.Cog, name="Scores"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if SCORE_CHANNEL_ID and message.channel.id != SCORE_CHANNEL_ID:
            return
        if not URL_PATTERN.search(message.content):
            return

        match = DAILY_PATTERN.search(message.content)
        if match:
            date_str = match.group(1)
            score = float(match.group(2))
            parsed_date = _parse_date(date_str)
        else:
            # Fallback: just the URL like dialed.gg?d=1&s=46.24
            url_match = DAILY_URL.search(message.content)
            if not url_match:
                return
            score = float(url_match.group(1))
            parsed_date = None

        if score <= 0 or score > 50:
            return

        today = date.today()
        game_number = _date_to_game(parsed_date) if parsed_date else _date_to_game(today)
        is_old = (parsed_date < today) if parsed_date else False

        db = self.bot.db
        username = message.author.display_name
        user_id = str(message.author.id)

        existing = await db.get_existing_score(user_id, game_number)
        if existing is not None:
            await message.reply(
                embed=discord.Embed(
                    title="Score Already Recorded 🔒",
                    description=f"You already submitted **{existing}/50** for this daily.\nYour first score is locked in!",
                    color=COLOR_WARNING,
                ),
                delete_after=15,
            )
            return

        success = await db.insert_score(user_id, username, game_number, score)
        if not success:
            return

        try:
            await message.add_reaction(CONFIRM_EMOJI)
        except discord.HTTPException:
            pass

        rank = await db.get_user_rank(user_id, game_number)
        rank_str = f"  •  #{rank} today" if rank else ""

        desc = f"**{username}** — **{score}/50**\n{_score_bar(score)}{rank_str}"
        if is_old:
            desc += "\n⚠️ *Older daily — counted in stats but not today's leaderboard.*"

        # Append leaderboard
        if not is_old:
            rows = await db.get_leaderboard(game_number, limit=10)
            if rows:
                lines = []
                for i, row in enumerate(rows, start=1):
                    medal = MEDALS.get(i, f"{i}.")
                    name = discord.utils.escape_markdown(row["username"])
                    lines.append(f"{medal} **{name}** — `{row['score']}/50`")
                desc += "\n\n**📅 Today's Leaderboard**\n" + "\n".join(lines)

        embed = discord.Embed(description=desc, color=COLOR_SUCCESS)
        await message.reply(embed=embed)
        log.info(f"Recorded: user={user_id} name={username} game={game_number} score={score}")


def _score_bar(score: float, max_score: float = 50.0, length: int = 20) -> str:
    filled = round((score / max_score) * length)
    return f"`{'█' * filled + '░' * (length - filled)}` {round((score / max_score) * 100, 1)}%"


async def setup(bot: commands.Bot):
    await bot.add_cog(ScoresCog(bot))
