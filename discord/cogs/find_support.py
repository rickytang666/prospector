import discord
from discord.ext import commands
from discord import app_commands
from testing_info import MOCK_CANDIDATES
from ui.embeds import candidates_embed
from ui.buttons import CandidateView


class FindSupport(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="find-support", description="Retrieve ranked external support candidates for your team.")
    async def find_support(self, interaction: discord.Interaction, query: str):

        guild_id = interaction.guild_id
        team_context = interaction.client.team_context_cache.get(guild_id)

        if not team_context:
            await interaction.response.send_message("Run `/analyze-team` first.")
            return

        await interaction.response.defer()

        embed = candidates_embed(MOCK_CANDIDATES, query)
        view = CandidateView(MOCK_CANDIDATES)

        await interaction.followup.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(FindSupport(bot))
