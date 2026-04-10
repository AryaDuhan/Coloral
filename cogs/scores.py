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
# Matches: "dialed.gg?d=12&s=46.24" (just the URL)
DAILY_URL = re.compile(r"dialed\.gg\?d=(\d+)&s=([\d]+(?:\.[\d]+)?)", re.IGNORECASE)
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
    async def on_ready(self):
        if getattr(self, "_caught_up_scores", False):
            return
        self._caught_up_scores = True
        self.bot.loop.create_task(self._run_catchup())

    async def _run_catchup(self):
        await self.bot.wait_until_ready()
        channels = set()
        if SCORE_CHANNEL_ID:
            channels.add(SCORE_CHANNEL_ID)
        else:
            db_channels = await self.bot.db.get_all_reminder_channels()
            channels.update(db_channels)

        if not channels:
            return

        log.info("Starting catch-up check for missed scores...")
        count = 0
        for ch_id in channels:
            channel = self.bot.get_channel(ch_id)
            if not channel:
                continue
            
            try:
                # Fetch recent messages chronological
                recent_msgs = [msg async for msg in channel.history(limit=20)]
                for message in reversed(recent_msgs):
                    if URL_PATTERN.search(message.content):
                        await self.process_message(message, is_catchup=True)
                        count += 1
            except discord.Forbidden:
                pass
            except discord.HTTPException as e:
                log.error(f"Error checking channel {ch_id}: {e}")
                
        log.info(f"Catch-up completed by matching against {count} dialed message(s)")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        await self.process_message(message, is_catchup=False)

    async def process_message(self, message: discord.Message, is_catchup: bool = False):
        if message.author.bot:
            return
        if SCORE_CHANNEL_ID and message.channel.id != SCORE_CHANNEL_ID:
            return
        if not URL_PATTERN.search(message.content):
            return

        match = DAILY_PATTERN.search(message.content)
        url_match = DAILY_URL.search(message.content)
        
        if url_match:
            d_val = int(url_match.group(1))
            if d_val < 20000000:
                # This is likely a single mode score (e.g. d=1 for difficulty 1), ignore it.
                return

        if match:
            date_str = match.group(1)
            score = float(match.group(2))
            parsed_date = _parse_date(date_str)
            
            # Anti-cheat: verify the text score matches the URL score exactly
            if url_match:
                url_score = float(url_match.group(2))
                if score != url_score:
                    if not is_catchup:
                        await message.reply(
                            embed=discord.Embed(
                                title="❌ Altered Score Detected",
                                description="Nice try! The score in your text doesn't match the hidden score in the dialed.gg URL. 🕵️\n\nPlease paste your authentic score directly from the game.",
                                color=COLOR_WARNING,
                            ),
                            delete_after=15,
                        )
                    return
        else:
            # Fallback: just the URL like dialed.gg?d=20260405&s=46.24
            if not url_match:
                return
            score = float(url_match.group(2))
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
            if not is_catchup:
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
        log.info(f"{'[CATCHUP] ' if is_catchup else ''}Recorded: user={user_id} name={username} game={game_number} score={score}")


def _score_bar(score: float, max_score: float = 50.0, length: int = 20) -> str:
    filled = round((score / max_score) * length)
    return f"`{'█' * filled + '░' * (length - filled)}` {round((score / max_score) * 100, 1)}%"


async def setup(bot: commands.Bot):
    await bot.add_cog(ScoresCog(bot))
