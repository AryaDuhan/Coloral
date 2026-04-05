"""
cogs/color.py — /color slash command.
Sends a playable link block to start the game directly.
"""

import discord
from discord import app_commands
from discord.ext import commands
from config import COLOR_PRIMARY
from ui import PlayView

class ColorCog(commands.Cog, name="Color"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="color",
        description="Start a new game of Dialed and get the link to play!",
    )
    async def color(self, interaction: discord.Interaction):
        game_number = await self.bot.db.get_current_game_number()
        game_str = f"#{game_number + 1}" if game_number else "Today's Puzzle"

        embed = discord.Embed(
            title="🎨 Ready to play?",
            description=(
                f"**{game_str}** awaits!\n\n"
                "Click the button below to test your color memory. "
                "Once you're done, paste your results back into this channel!"
            ),
            color=COLOR_PRIMARY,
        )

        await interaction.response.send_message(embed=embed, view=PlayView())

async def setup(bot: commands.Bot):
    await bot.add_cog(ColorCog(bot))
