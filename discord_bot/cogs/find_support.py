import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from retrieval.api import find_support_dict, find_providers_dict
from discord_bot.ui.embeds import candidates_embed
from discord_bot.ui.buttons import CandidateView
from discord_bot.ai import get_contact_infos


class FindSupport(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    async def _run_and_send(self, interaction: discord.Interaction, query: str, fn, title: str, k: int = 5, max_items: int = 5, **kwargs):
        guild_id = interaction.guild_id
        team_context = interaction.client.team_context_cache.get(guild_id)
        if not team_context:
            await interaction.response.send_message("Run `/analyze-team` first.")
            return
        await interaction.response.defer()
        result = await asyncio.to_thread(fn, team_context=team_context, query=query, k=k, **kwargs)
        candidates = result["candidates"]
        retrieval_metadata = result.get("retrieval_metadata") or {}
        displayed = candidates[:max_items]
        contact_infos = await get_contact_infos(displayed)
        embed = candidates_embed(candidates, query, retrieval_metadata, title=title, max_items=max_items, contact_infos=contact_infos)
        view = CandidateView(candidates)
        await interaction.followup.send(embed=embed, view=view)

    @app_commands.command(name="find-support", description="Retrieve ranked external support candidates for your team.")
    async def find_support(self, interaction: discord.Interaction, query: str):
        await self._run_and_send(
            interaction,
            query,
            find_support_dict,
            title="Top Support Matches",
        )

    @app_commands.command(name="find-providers", description="Find providers and relevant entities for a technical need.")
    async def find_providers(self, interaction: discord.Interaction, query: str):
        await self._run_and_send(
            interaction,
            query,
            find_providers_dict,
            title="Top Provider Matches",
        )


async def setup(bot):
    await bot.add_cog(FindSupport(bot))
