import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from retrieval.api import retrieve_context_pack_dict
from discord_bot.ui.embeds import explanation_embed
from discord_bot.ai import get_contact_infos


class ExplainMatch(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="explain-match", description="Explain why a candidate entity fits your team's needs.")
    async def explain_match(self, interaction: discord.Interaction, entity_id: str):

        guild_id = interaction.guild_id
        user_id = interaction.user.id
        await interaction.response.defer()

        from discord_bot.team_ctx import get_team_context_for_member
        team_context = await get_team_context_for_member(interaction.client, guild_id, user_id)

        if not team_context:
            await interaction.followup.send("Run `/configure-team add` first (use `/my-team` to see teams).", ephemeral=True)
            return

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
        entity_name = entity.get("name", entity_id)
        support_types = entity.get("support_types") or []
        contact_list = await get_contact_infos([entity])
        contact = contact_list[0] if contact_list else {}

        reasons = entity.get("matched_reasons") or []
        reason = reasons[0] if reasons else ""

        explanation = {
            "entity_name": entity_name,
            "reason": reason,
            "tags": entity.get("tags") or [],
            "contact_person": contact.get("contact_person", ""),
            "contact_email": contact.get("contact_email", ""),
            "contact_email_verified": contact.get("contact_email_verified", False),
            "website": contact.get("website", ""),
        }


        embed = explanation_embed(explanation, team_name=team_context["team_name"])
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ExplainMatch(bot))