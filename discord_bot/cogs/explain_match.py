import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from retrieval.api import retrieve_context_pack_dict
from ui.embeds import explanation_embed


class ExplainMatch(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="explain-match", description="Explain why a candidate entity fits your team's needs.")
    async def explain_match(self, interaction: discord.Interaction, entity_id: str):

        guild_id = interaction.guild_id
        team_context = interaction.client.team_context_cache.get(guild_id)

        if not team_context:
            await interaction.response.send_message("Run `/analyze-team` first.")
            return

        await interaction.response.defer()

        pack = await asyncio.to_thread(
            retrieve_context_pack_dict,
            team_context=team_context,
            query=entity_id,
            k_entities=1,
        )
        matches = pack.get("entity_matches", [])

        if not matches:
            await interaction.followup.send(f"No match found for **{entity_id}**.")
            return

        entity = matches[0]
        support_types = entity.get("support_types") or []
        explanation = {
            "entity_name": entity.get("name", entity_id),
            "why_it_helps": entity.get("matched_reasons") or ["No reasons available."],
            "why_they_may_care": entity.get("evidence_snippets") or ["No evidence available."],
            "recommended_ask": support_types[0] if support_types else "Reach out to explore collaboration.",
        }

        embed = explanation_embed(explanation, team_name=team_context["team_name"])
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ExplainMatch(bot))