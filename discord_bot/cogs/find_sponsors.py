import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from retrieval.api import find_support_dict
from discord_bot.ui.embeds import candidates_embed
from discord_bot.ui.buttons import CandidateView
from discord_bot.services.ai import get_contact_infos


class FindSponsors(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="find-sponsors", description="Find ranked sponsor and support candidates for your team.")
    async def find_sponsors(self, interaction: discord.Interaction, query: str):
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        try:
            await interaction.response.defer()
        except discord.NotFound:
            return

        from discord_bot.team_ctx import get_team_context_for_member
        team_context = await get_team_context_for_member(interaction.client, guild_id, user_id)
        if not team_context:
            await interaction.followup.send("Run `/configure-team add` first (use `/my-team` to see teams).", ephemeral=True)
            return

        result = await asyncio.to_thread(find_support_dict, team_context=team_context, query=query, k=7)
        candidates = result["candidates"]
        retrieval_metadata = result.get("retrieval_metadata") or {}

        # cache for explain-match and draft-email buttons
        cache_key = (guild_id, user_id)
        interaction.client.sponsor_search_cache[cache_key] = candidates

        contact_infos = await get_contact_infos(candidates[:7])
        embed = candidates_embed(candidates, query, retrieval_metadata, title="Top Sponsor Matches", max_items=7, contact_infos=contact_infos)
        view = CandidateView(candidates)
        await interaction.followup.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(FindSponsors(bot))
