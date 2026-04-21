"""
ui.py — Persistent Discord UI views (Play Daily button + HMAC token generation).
"""

from datetime import datetime, timezone
import discord
import asyncio
import logging
import hmac
import hashlib
import base64
import json
import time

from config import HMAC_SECRET, WEBSITE_URL, GAME_TZ

# No tracking sessions needed since game auto-submits


def _today_game() -> int:
    """Get today's game number (YYYYMMDD format, game timezone)."""
    return int(datetime.now(GAME_TZ).strftime("%Y%m%d"))


def _today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


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

        # Check if they already submitted today's score
        db = getattr(interaction.client, "db", None)
        if db is not None:
            existing = await db.get_existing_score(user_id, _today_game())
            if existing is not None:
                try:
                    await interaction.response.send_message(
                        f"🔒 You already submitted your score for today!",
                        ephemeral=True,
                    )
                except discord.errors.NotFound:
                    pass
                return

        if HMAC_SECRET and WEBSITE_URL:
            token = _generate_token(user_id, username)
            game_url = f"https://{WEBSITE_URL}/?token={token}&t={int(time.time())}"

            try:
                await interaction.response.send_message(
                    f"🎮 **Let's go!**\n\n"
                    f"Open your secure game link:\n"
                    f"**[Play Dialed Daily]({game_url})**\n\n"
                    f"*Your score will be logged automatically when you finish.*",
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

    @discord.ui.button(label="Play Single Player", style=discord.ButtonStyle.secondary, emoji="🎲", custom_id="play_singleplayer_btn")
    async def singleplayer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        username = interaction.user.display_name

        if HMAC_SECRET and WEBSITE_URL:
            token = _generate_token(user_id, username)
            game_url = f"https://{WEBSITE_URL}/play?token={token}&t={int(time.time())}"

            try:
                await interaction.response.send_message(
                    f"🎲 **Single Player Mode**\n\n"
                    f"Open your game link:\n"
                    f"**[Play Single Player]({game_url})**\n\n"
                    f"*Random colors every game. Play as many times as you want!*",
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

