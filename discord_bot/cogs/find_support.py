import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from retrieval.api import rank_candidates_dict
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

        result = await asyncio.to_thread(rank_candidates_dict, team_context=team_context, query=query, k=5)
        candidates = result["candidates"]
        retrieval_metadata = result.get("retrieval_metadata") or {}

        embed = candidates_embed(candidates, query, retrieval_metadata)
        view = CandidateView(candidates)

        await interaction.followup.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(FindSupport(bot))
