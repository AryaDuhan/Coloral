from datetime import datetime, timezone
import discord
import asyncio


class PlayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Play Daily", style=discord.ButtonStyle.success, emoji="▶️", custom_id="play_daily_btn")
    async def play_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.send_message(
                f"🎮 Let's go! Open the game here: **[dialed.gg](https://dialed.gg)**",
                ephemeral=True,
            )
        except discord.errors.NotFound:
            # Interaction token expired before we could respond (high network latency on phone)
            # We silently pass so the 30s reminder timer still activates.
            pass
        
        # Wait 30 seconds then remind them to share their score
        await asyncio.sleep(30)
        
        # Verify if they already posted today's score
        db = getattr(interaction.client, "db", None)
        if db is not None:
            today_game = int(datetime.now(timezone.utc).strftime("%Y%m%d"))
            existing = await db.get_existing_score(str(interaction.user.id), today_game)
            if existing is not None:
                return  # They already submitted their score, stop reminder

        # If we got here, they didn't submit a score
        await interaction.channel.send(
            f"🎨 {interaction.user.mention} — done playing? Paste your score link here to record it!",
            delete_after=60,
        )
