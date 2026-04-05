import discord
import asyncio


class PlayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="Play Daily", style=discord.ButtonStyle.link, url="https://dialed.gg", emoji="▶️"))

    @discord.ui.button(label="I'm Playing!", style=discord.ButtonStyle.success, emoji="🎮", custom_id="playing_btn")
    async def playing_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"🎮 Good luck {interaction.user.mention}! Go crush it at **[dialed.gg](https://dialed.gg)**!",
            ephemeral=True,
        )
        # Wait 25 seconds then remind them to share their score
        await asyncio.sleep(25)
        await interaction.channel.send(
            f"🎨 {interaction.user.mention} — done playing? Paste your score link here to record it!",
            delete_after=60,
        )
