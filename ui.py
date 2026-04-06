from datetime import datetime, date, timezone
import discord
import asyncio
import logging

log = logging.getLogger("dialed.ui")

# Track players who clicked "Play Daily" today so we don't spam them
# Key: (user_id, game_date_str), Value: True
_active_play_sessions: set[tuple[str, str]] = set()


def _today_game() -> int:
    """Get today's game number (YYYYMMDD format)."""
    return int(date.today().strftime("%Y%m%d"))


def _today_str() -> str:
    return date.today().isoformat()


class PlayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Play Daily", style=discord.ButtonStyle.success, emoji="▶️", custom_id="play_daily_btn")
    async def play_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        today = _today_str()
        session_key = (user_id, today)

        # Send the play link
        try:
            await interaction.response.send_message(
                f"🎮 Let's go! Open the game here: **[dialed.gg](https://dialed.gg)**",
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
