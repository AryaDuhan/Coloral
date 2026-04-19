"""
cogs/scores.py — Listens for dialed.gg daily score pastes and Coloral webhook submissions.
"""

import re
import json
import base64
import hmac
import hashlib
import logging
import discord
from datetime import datetime, date, timezone
from discord.ext import commands
from config import (
    CONFIRM_EMOJI, SCORE_CHANNEL_ID, COLOR_SUCCESS, COLOR_WARNING,
    HMAC_SECRET, BOT_OWNER_ID,
)

log = logging.getLogger("dialed.scores")

# Matches dialed.gg URLs... removed completely.
MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}

# Webhook author name used by Colorle website
COLORAL_WEBHOOK_NAME = "Colorle"

# Matches share links: https://site.com/share?u=...&g=...&s=...&sig=...
SHARE_URL_PATTERN = re.compile(r'/share\?[^\s]+sig=[a-f0-9]{16}', re.IGNORECASE)


def _date_to_game(d: date) -> int:
    """Convert a date to game number (YYYYMMDD)."""
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


def _verify_share_signature(user_id: str, game_number: int, score: float, round_data: str, sig: str) -> bool:
    """Verify the HMAC signature on a share link."""
    if not HMAC_SECRET:
        return False
    data = f"{user_id}:{game_number}:{score}:{round_data}"
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
        # Sync test leaderboard file on boot
        await self._sync_test_leaderboard_file()
        
        if getattr(self, "_caught_up_scores", False):
            return
        self._caught_up_scores = True
        self.bot.loop.create_task(self._run_catchup())
        
    async def _sync_test_leaderboard_file(self):
        try:
            import json
            today_game = int(datetime.now(timezone.utc).strftime("%Y%m%d"))
            rows = await self.bot.db.get_leaderboard(today_game, limit=10)
            # Fallback to latest game if today has no scores yet
            if not rows:
                latest = await self.bot.db.get_current_game_number()
                if latest:
                    rows = await self.bot.db.get_leaderboard(latest, limit=10)
            if rows:
                lb_data = {"scores": [{"username": r["username"], "total_score": r["score"]} for r in rows]}
            else:
                lb_data = {"scores": []}
            with open("web/leaderboard.json", "w", encoding="utf-8") as f:
                json.dump(lb_data, f)
        except Exception as e:
            log.error(f"Failed to sync init leaderboard.json: {e}")

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

        # Check for share links pasted by users
        if SHARE_URL_PATTERN.search(message.content):
            await self._process_share_link(message)

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

        # ── Secret Anti-Cheat Alert (fires BEFORE duplicate check) ────────────
        if cheat_count > 0 and BOT_OWNER_ID:
            await self._send_cheat_alert(user_id, username, game_number, score, cheat_count, cheat_details)

        # ── Normal Mode Submission ──
        existing = await db.get_existing_score(user_id, game_number)
        if existing is not None:
            log.info(f"[COLORAL] Duplicate score for user={user_id} game={game_number}, already have {existing}")
            # Delete the raw webhook after confirming duplicate
            try:
                await message.delete()
            except discord.HTTPException:
                pass
            return

        # Record the score
        success = await db.insert_score(user_id, username, game_number, score, round_data)
        if not success:
            # Don't delete webhook if DB insert failed — keep it for retry
            return

        log.info(f"{'[CATCHUP] ' if is_catchup else ''}[COLORAL] Recorded: user={user_id} name={username} game={game_number} score={score}")

        # Build the bot's own clean embed with leaderboard
        rank = await db.get_user_rank(user_id, game_number)
        rank_str = f"  •  #{rank} today" if rank else ""

        desc = f"**{username}** — **{score}/50**\n{_score_bar(score)}{rank_str}"

        # Add per-round score breakdown with color-coded indicators
        round_breakdown = _format_round_breakdown(round_data)
        if round_breakdown:
            desc += f"\n\n{round_breakdown}"

        # Always show leaderboard for the submitted game and update website JSON
        rows = await db.get_leaderboard(game_number, limit=10)
        if rows:
            lines = []
            for i, row in enumerate(rows, start=1):
                medal = MEDALS.get(i, f"{i}.")
                name = discord.utils.escape_markdown(row["username"])
                lines.append(f"{medal} **{name}** — `{row['score']}/50`")
            desc += "\n\n**📅 Today's Leaderboard**\n" + "\n".join(lines)

            # Generate the json for the website
            try:
                lb_data = {"scores": [{"username": r["username"], "total_score": r["score"]} for r in rows]}
                with open("web/leaderboard.json", "w", encoding="utf-8") as f:
                    json.dump(lb_data, f)
            except Exception as e:
                log.error(f"Failed to generate leaderboard.json: {e}")

        reply_embed = discord.Embed(description=desc, color=COLOR_SUCCESS)

        # STEP 1: Send the bot's clean embed FIRST
        try:
            await message.channel.send(embed=reply_embed)
        except discord.HTTPException:
            # If we can't send our own message, DON'T delete the webhook — keep the raw data visible
            log.error(f"Failed to send score embed for user={user_id}")
            return

        # STEP 2: Only delete the raw webhook AFTER our message is confirmed sent
        try:
            await message.delete()
        except discord.HTTPException:
            pass

    # ── Share Link Processing ─────────────────────────────────────────────────

    async def _process_share_link(self, message: discord.Message):
        """Process a tamper-proof share link pasted by a user."""
        try:
            from urllib.parse import urlparse, parse_qs
            match = SHARE_URL_PATTERN.search(message.content)
            if not match:
                return

            # Extract the full URL from the message
            url_match = re.search(r'(https?://[^\s]+/share\?[^\s]+)', message.content)
            if not url_match:
                return

            parsed = urlparse(url_match.group(1))
            params = parse_qs(parsed.query)

            user_id = params.get('u', [None])[0]
            game_number = int(params.get('g', [0])[0])
            score = float(params.get('s', [0])[0])
            username = params.get('n', [f'User {user_id}'])[0]
            round_data = params.get('r', [''])[0]
            sig = params.get('sig', [''])[0]

            if not user_id or not game_number or not sig:
                return

            # Verify the link sender is the actual player
            if str(message.author.id) != user_id:
                await message.reply(
                    "❌ This score link belongs to a different user.",
                    delete_after=10,
                )
                return

            # Verify HMAC signature — prevents any tampering
            if not _verify_share_signature(user_id, game_number, score, round_data, sig):
                log.warning(f"Invalid share link signature from {message.author} for game {game_number}")
                return

            # Validate score range
            if score <= 0 or score > 50:
                return

            db = self.bot.db

            # Check for duplicate
            existing = await db.get_existing_score(user_id, game_number)
            if existing is not None:
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass
                await message.channel.send(
                    "🔒 Score already recorded for this game!",
                    delete_after=10,
                )
                return

            # Record the score
            success = await db.insert_score(user_id, username, game_number, score, round_data)
            if not success:
                return

            log.info(f"[SHARE LINK] Recorded: user={user_id} name={username} game={game_number} score={score}")

            # Build response embed with leaderboard
            rank = await db.get_user_rank(user_id, game_number)
            rank_str = f"  •  #{rank} today" if rank else ""

            desc = f"**{username}** — **{score}/50**\n{_score_bar(score)}{rank_str}"

            # Add per-round score breakdown with color-coded indicators
            round_breakdown = _format_round_breakdown(round_data)
            if round_breakdown:
                desc += f"\n\n{round_breakdown}"

            # Always show leaderboard for the submitted game and update website JSON
            rows = await db.get_leaderboard(game_number, limit=10)
            if rows:
                lines = []
                for i, row in enumerate(rows, start=1):
                    medal = MEDALS.get(i, f"{i}.")
                    name = discord.utils.escape_markdown(row["username"])
                    lines.append(f"{medal} **{name}** — `{row['score']}/50`")
                desc += "\n\n**📅 Today's Leaderboard**\n" + "\n".join(lines)

                try:
                    lb_data = {"scores": [{"username": r["username"], "total_score": r["score"]} for r in rows]}
                    with open("web/leaderboard.json", "w", encoding="utf-8") as f:
                        json.dump(lb_data, f)
                except Exception as e:
                    log.error(f"Failed to generate leaderboard.json: {e}")

            reply_embed = discord.Embed(description=desc, color=COLOR_SUCCESS)

            # Delete the share link message and reply with clean embed
            try:
                await message.delete()
            except discord.HTTPException:
                pass
            try:
                await message.channel.send(embed=reply_embed)
            except discord.HTTPException:
                pass

        except (ValueError, KeyError, IndexError) as e:
            log.warning(f"Failed to parse share link: {e}")


    async def _send_cheat_alert(self, user_id: str, username: str, game_number: int, score: float, cheat_count: int, cheat_details: str):
        """Send a secret DM to the bot owner with grouped cheat breakdown."""
        try:
            owner = await self.bot.fetch_user(BOT_OWNER_ID)
            if not owner:
                return

            # Parse and group: "R2:print_screen,R4:window_blur,R4:print_screen"
            # -> { "print_screen": [2, 4], "window_blur": [4] }
            grouped: dict[str, list[int]] = {}
            if cheat_details:
                for event in cheat_details.split(","):
                    parts = event.split(":", 1)
                    if len(parts) == 2:
                        try:
                            round_num = int(parts[0][1:])  # "R2" -> 2
                        except ValueError:
                            continue
                        event_type = parts[1]
                        grouped.setdefault(event_type, []).append(round_num)

            if grouped:
                event_lines = []
                for event_type, rounds in grouped.items():
                    label = CHEAT_LABELS.get(event_type, f"⚠️ {event_type}")
                    rounds_str = ", ".join(str(r) for r in sorted(rounds))
                    count = len(rounds)
                    event_lines.append(
                        f"{label}\n"
                        f"  × **{count}** time{'s' if count > 1 else ''} — Rounds: **{rounds_str}**"
                    )
                events_text = "\n\n".join(event_lines)
            else:
                events_text = f"• {cheat_count} suspicious event(s) detected (no details available)"

            embed = discord.Embed(
                title="🕵️ Cheat Alert",
                description=(
                    f"**{username}** (`{user_id}`) triggered **{cheat_count}** suspicious event{'s' if cheat_count > 1 else ''} "
                    f"during today's game.\n\n"
                    f"**Score:** {score}/50 • **Game:** #{game_number}\n\n"
                    f"**Breakdown:**\n{events_text}"
                ),
                color=0xFF6B6B,
            )
            embed.set_footer(text="This alert is secret — the player sees nothing.")

            await owner.send(embed=embed)
            log.info(f"[ANTICHEAT] Sent cheat alert for user={user_id} ({cheat_count} events)")

        except discord.HTTPException as e:
            log.error(f"Failed to send cheat alert DM: {e}")


def _score_bar(score: float, max_score: float = 50.0, length: int = 20) -> str:
    filled = round((score / max_score) * length)
    return f"`{'█' * filled + '░' * (length - filled)}` {round((score / max_score) * 100, 1)}%"


def _round_score_emoji(score: float) -> str:
    """Return a colored circle emoji based on the round score (0-10)."""
    if score >= 9.5:
        return "🟢"  # Perfect / near-perfect
    if score >= 8.0:
        return "🟢"  # Great
    if score >= 6.0:
        return "🟡"  # Good
    if score >= 4.0:
        return "🟠"  # Okay
    if score >= 2.0:
        return "🔴"  # Poor
    return "⚫"      # Terrible


def _format_round_breakdown(round_data_b64: str) -> str:
    """Decode base64url round data and format a per-round score breakdown."""
    if not round_data_b64:
        return ""
    try:
        # Re-add base64 padding
        b64 = round_data_b64.replace('-', '+').replace('_', '/')
        padding = 4 - (len(b64) % 4)
        if padding != 4:
            b64 += '=' * padding
        raw = base64.b64decode(b64)
        rounds = json.loads(raw)

        if not isinstance(rounds, list) or len(rounds) == 0:
            return ""

        parts = []
        for i, r in enumerate(rounds, start=1):
            s = r.get("s", 0)
            emoji = _round_score_emoji(s)
            parts.append(f"{emoji} `{s:.2f}`")

        return "  ".join(parts)
    except Exception:
        return ""


async def setup(bot: commands.Bot):
    await bot.add_cog(ScoresCog(bot))
