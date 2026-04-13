"""
ui.py — Persistent Discord UI views (Play Daily button + HMAC token generation).
"""

from datetime import datetime, date, timezone
import discord
import asyncio
import logging
import hmac
import hashlib
import base64
import json
import time

from config import HMAC_SECRET, WEBSITE_URL

log = logging.getLogger("dialed.ui")

# Track players who clicked "Play Daily" today so we don't spam them
# Key: (user_id, game_date_str), Value: True
_active_play_sessions: set[tuple[str, str]] = set()


def _today_game() -> int:
    """Get today's game number (YYYYMMDD format)."""
    return int(date.today().strftime("%Y%m%d"))


def _today_str() -> str:
    return date.today().isoformat()


def _generate_token(user_id: str, username: str) -> str:
    """
    Generate an HMAC-signed stateless token for website authentication.

    Token format: base64url(json_payload).hex(hmac_sha256(encoded_payload, secret))
    Payload: { user_id, username, exp (1 hour from now) }
    """
    payload = json.dumps({
        "user_id": user_id,
        "username": username,
        "exp": int(time.time()) + 3600,  # 1-hour expiry
    })
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig = hmac.new(HMAC_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


class PlayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Play Daily", style=discord.ButtonStyle.secondary, emoji="▶️", custom_id="play_daily_btn")
    async def play_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        username = interaction.user.display_name
        today = _today_str()
        session_key = (user_id, today)

        # Main button now points to the real dialed.gg ALWAYS
        try:
            await interaction.response.send_message(
                f"🎮 Let's go! Open the game here: **[dialed.gg](https://dialed.gg)**\n"
                f"*Paste your score back in this channel when you finish.*",
                ephemeral=True,
            )
        except discord.errors.NotFound:
            pass

        # Check if they already submitted today's score BEFORE waiting
        db = getattr(interaction.client, "db", None)
        if db is not None:
            existing = await db.get_existing_score(user_id, _today_game())
            if existing is not None:
                return  # Already submitted, no reminder needed

        # Check if we already have a pending reminder for this player today
        if session_key in _active_play_sessions:
            return  # Don't stack multiple reminders
        _active_play_sessions.add(session_key)

        # Wait 40 seconds for them to play
        await asyncio.sleep(40)

        # Clean up the session tracker
        _active_play_sessions.discard(session_key)

        # Check AGAIN if they submitted during the wait
        if db is not None:
            existing = await db.get_existing_score(user_id, _today_game())
            if existing is not None:
                return  # They submitted while we were waiting — no reminder

        # They didn't submit — nudge them
        try:
            await interaction.channel.send(
                f"🎨 {interaction.user.mention} — done playing? "
                f"Paste your score link here to record it!",
                delete_after=60,
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            log.error(f"Failed to send play reminder to {user_id}: {e}")

    @discord.ui.button(label="Test Webhook Clone", style=discord.ButtonStyle.success, emoji="🧪", custom_id="test_daily_btn")
    async def test_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        username = interaction.user.display_name

        if HMAC_SECRET and WEBSITE_URL:
            token = _generate_token(user_id, username)
            game_url = f"https://{WEBSITE_URL}/?token={token}&test=1"

            try:
                await interaction.response.send_message(
                    f"🧪 **Test Mode Active!**\n\n"
                    f"Open your secure test link:\n"
                    f"**[Test Coloral Clone]({game_url})**\n\n"
                    f"*Scores from this link will be sent to the webhook but saved to a separate Test Leaderboard.*",
                    ephemeral=True,
                )
            except discord.errors.NotFound:
                pass
        else:
            try:
                await interaction.response.send_message(
                    f"⚠️ The `HMAC_SECRET` and `WEBSITE_URL` environment variables are not configured.",
                    ephemeral=True,
                )
            except discord.errors.NotFound:
                pass
