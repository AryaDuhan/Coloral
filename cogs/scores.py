"""
cogs/scores.py — Listens for dialed.gg daily score pastes and Coloral webhook submissions.
"""

import re
import hmac
import hashlib
import logging
import discord
from datetime import datetime, date
from discord.ext import commands
from config import (
    CONFIRM_EMOJI, SCORE_CHANNEL_ID, COLOR_SUCCESS, COLOR_WARNING,
    HMAC_SECRET, BOT_OWNER_ID,
)

log = logging.getLogger("dialed.scores")

# Matches: "Dialed Daily — Apr 5\n40.41/50 🟨🟧🟩🟧🟨\ndialed.gg?d=1&s=40.41"
DAILY_PATTERN = re.compile(
    r"Dialed\s+Daily\s*[—\-–]\s*(\w+\s+\d+).*?([\d]+(?:\.[\d]+)?)\s*/\s*50",
    re.IGNORECASE | re.DOTALL)
# Matches: "dialed.gg?d=12&s=46.24" (just the URL)
DAILY_URL = re.compile(r"dialed\.gg\?d=(\d+)&s=([\d]+(?:\.[\d]+)?)", re.IGNORECASE)
URL_PATTERN = re.compile(r"dialed\.gg", re.IGNORECASE)
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

# Webhook author name used by Coloral website
COLORAL_WEBHOOK_NAME = "Coloral"


def _date_to_game(d: date) -> int:
    return int(d.strftime("%Y%m%d"))


def _parse_date(s: str) -> date | None:
    try:
        return datetime.strptime(f"{s.strip()} {datetime.now().year}", "%b %d %Y").date()
    except ValueError:
        return None


def _verify_score_signature(user_id: str, game_number: int, score: float, cheat_count: int, sig: str) -> bool:
    """Verify the HMAC signature on a Coloral webhook score submission."""
    if not HMAC_SECRET:
        return False
    data = f"{user_id}:{game_number}:{score}:{cheat_count}"
    expected = hmac.new(HMAC_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()[:16]
    return hmac.compare_digest(sig, expected)


# ── Anti-cheat event labels ───────────────────────────────────────────────────
CHEAT_LABELS = {
    "print_screen": "🖨️ PrintScreen key pressed",
    "ctrl_shift_s": "✂️ Ctrl+Shift+S pressed (Snipping Tool)",
    "win_shift_s": "✂️ Win+Shift+S pressed (Snip & Sketch)",
    "alt_print_screen": "🖨️ Alt+PrintScreen pressed",
    "window_blur": "👁️ Window lost focus",
    "tab_hidden": "👁️ Tab was hidden",
    "right_click": "🖱️ Right-click on game",
}


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
                    # Check for webhook messages (Coloral auto-submissions)
                    if message.webhook_id and message.embeds:
                        await self._process_webhook_score(message, is_catchup=True)
                        count += 1
                        continue

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
        # Check for Coloral webhook messages first
        if message.webhook_id and message.embeds:
            await self._process_webhook_score(message, is_catchup=False)
            return

        # Skip bot messages for normal score parsing
        if message.author.bot:
            return

        await self.process_message(message, is_catchup=False)

    # ── Coloral Webhook Score Processing ──────────────────────────────────────

    async def _process_webhook_score(self, message: discord.Message, is_catchup: bool = False):
        """Process a score submitted via the Coloral website webhook."""
        if not message.embeds:
            return

        embed = message.embeds[0]

        # Verify it's from our webhook by checking author name
        if not message.author.name == COLORAL_WEBHOOK_NAME:
            return

        # Parse footer: "userId|gameNumber|score|cheatCount|hmacSig|cheatDetails?"
        if not embed.footer or not embed.footer.text:
            return

        parts = embed.footer.text.split("|")
        if len(parts) < 5:
            return

        try:
            user_id = parts[0]
            game_number = int(parts[1])
            score = float(parts[2])
            cheat_count = int(parts[3])
            sig = parts[4]
            cheat_details = parts[5] if len(parts) > 5 else ""
            is_test = "TEST" in parts
            round_data = ""
            for p in parts[5:]:
                if p and p != "TEST" and ":" not in p:
                    round_data = p
                    break
        except (ValueError, IndexError):
            log.warning(f"Malformed Coloral webhook footer: {embed.footer.text}")
            return

        # Verify HMAC signature
        if not _verify_score_signature(user_id, game_number, score, cheat_count, sig):
            log.warning(f"Invalid Coloral signature for user {user_id}, game {game_number}")
            return

        # Validate score range
        if score <= 0 or score > 50:
            return

        # Get username from embed title (format: "🎨 Username")
        username = embed.title.replace("🎨 ", "").replace("🧪 [TEST] ", "").strip() if embed.title else f"User {user_id}"

        db = self.bot.db

        if is_test:
            # Handle Test Mode Submission
            success = await db.insert_test_score(user_id, username, game_number, score, round_data)
            if not success:
                return

            log.info(f"[TEST] Recorded: user={user_id} name={username} game={game_number} score={score}")

            if not is_catchup:
                rank = await db.get_user_test_rank(user_id, game_number)
                rank_str = f"  •  #{rank} in testing" if rank else ""

                desc = f"**{username}** — **{score}/50**\n{_score_bar(score)}{rank_str}"

                rows = await db.get_test_leaderboard(game_number, limit=10)
                if rows:
                    lines = []
                    
                    # Dump for web UI
                    try:
                        import json
                        lb_data = {"scores": [{"username": r["username"], "total_score": r["score"]} for r in rows]}
                        with open("web/leaderboard.json", "w", encoding="utf-8") as f:
                            json.dump(lb_data, f)
                    except Exception as e:
                        log.error(f"Failed to generate leaderboard.json: {e}")

                    for i, row in enumerate(rows, start=1):
                        medal = MEDALS.get(i, f"{i}.")
                        name = discord.utils.escape_markdown(row["username"])
                        lines.append(f"{medal} **{name}** — `{row['score']}/50`")
                    desc += "\n\n**🧪 Test Leaderboard**\n" + "\n".join(lines)

                reply_embed = discord.Embed(description=desc, color=0x3498DB) # Blue for test
                try:
                    await message.delete()
                    await message.channel.send(embed=reply_embed)
                except discord.HTTPException:
                    pass

            return # Stop processing, avoid inserting into real db

        # ── Normal Mode Submission ──
        # Check for duplicate
        existing = await db.get_existing_score(user_id, game_number)
        if existing is not None:
            log.info(f"[COLORAL] Duplicate score for user={user_id} game={game_number}, already have {existing}")
            return

        # Record the score
        success = await db.insert_score(user_id, username, game_number, score, round_data)
        if not success:
            return

        log.info(f"{'[CATCHUP] ' if is_catchup else ''}[COLORAL] Recorded: user={user_id} name={username} game={game_number} score={score}")

        # Reply with leaderboard (only for live submissions, not catchup)
        if not is_catchup:
            rank = await db.get_user_rank(user_id, game_number)
            rank_str = f"  •  #{rank} today" if rank else ""

            desc = f"**{username}** — **{score}/50**\n{_score_bar(score)}{rank_str}"

            today = date.today()
            today_game = _date_to_game(today)
            if game_number == today_game:
                rows = await db.get_leaderboard(game_number, limit=10)
                if rows:
                    lines = []
                    for i, row in enumerate(rows, start=1):
                        medal = MEDALS.get(i, f"{i}.")
                        name = discord.utils.escape_markdown(row["username"])
                        lines.append(f"{medal} **{name}** — `{row['score']}/50`")
                    desc += "\n\n**📅 Today's Leaderboard**\n" + "\n".join(lines)

            reply_embed = discord.Embed(description=desc, color=COLOR_SUCCESS)
            try:
                await message.delete()
                await message.channel.send(embed=reply_embed)
            except discord.HTTPException:
                pass

        # ── Secret Anti-Cheat Alert ───────────────────────────────────────────
        if cheat_count > 0 and BOT_OWNER_ID:
            await self._send_cheat_alert(user_id, username, game_number, score, cheat_count, cheat_details)

    async def _send_cheat_alert(self, user_id: str, username: str, game_number: int, score: float, cheat_count: int, cheat_details: str):
        """Send a secret DM to the bot owner about suspicious activity."""
        try:
            owner = await self.bot.fetch_user(BOT_OWNER_ID)
            if not owner:
                return

            # Parse cheat details: "R2:print_screen,R4:window_blur"
            event_lines = []
            if cheat_details:
                for event in cheat_details.split(","):
                    parts = event.split(":", 1)
                    if len(parts) == 2:
                        round_num = parts[0]  # e.g. "R2"
                        event_type = parts[1]  # e.g. "print_screen"
                        label = CHEAT_LABELS.get(event_type, f"⚠️ {event_type}")
                        event_lines.append(f"• Round {round_num[1:]}: {label}")

            events_text = "\n".join(event_lines) if event_lines else f"• {cheat_count} suspicious event(s) detected"

            embed = discord.Embed(
                title="🕵️ Cheat Alert",
                description=(
                    f"**{username}** (`{user_id}`) triggered suspicious activity during today's game.\n\n"
                    f"**Score:** {score}/50 • **Game:** #{game_number}\n\n"
                    f"**Events during memorize phase:**\n{events_text}"
                ),
                color=0xFF6B6B,
            )
            embed.set_footer(text="This alert is secret — the player sees nothing.")

            await owner.send(embed=embed)
            log.info(f"[ANTICHEAT] Sent cheat alert for user={user_id} ({cheat_count} events)")

        except discord.HTTPException as e:
            log.error(f"Failed to send cheat alert DM: {e}")
        except Exception as e:
            log.error(f"Unexpected error in cheat alert: {e}")

    # ── Standard dialed.gg Score Processing ───────────────────────────────────

    async def process_message(self, message: discord.Message, is_catchup: bool = False):
        if message.author.bot:
            return
        if SCORE_CHANNEL_ID and message.channel.id != SCORE_CHANNEL_ID:
            return
        if not URL_PATTERN.search(message.content):
            return

        match = DAILY_PATTERN.search(message.content)
        url_match = DAILY_URL.search(message.content)

        if not match and url_match:
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


    @discord.app_commands.command(name="cleartest", description="Clear all scores from the Test Leaderboard")
    async def clear_test_cmd(self, interaction: discord.Interaction):
        if str(interaction.user.id) != BOT_OWNER_ID:
            await interaction.response.send_message("❌ This command is restricted.", ephemeral=True)
            return

        count = await self.bot.db.clear_test_scores()
        await interaction.response.send_message(f"🧹 Cleared {count} records from the Test Leaderboard.", ephemeral=True)

def _score_bar(score: float, max_score: float = 50.0, length: int = 20) -> str:
    filled = round((score / max_score) * length)
    return f"`{'█' * filled + '░' * (length - filled)}` {round((score / max_score) * 100, 1)}%"


async def setup(bot: commands.Bot):
    await bot.add_cog(ScoresCog(bot))
