import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from discord_bot.ui.embeds import explanation_embed
from discord_bot.services.ai import get_contact_infos


def _find_in_cache(candidates: list, name: str) -> dict | None:
    name_lower = name.lower()
    # exact match first
    for c in candidates:
        if c.get("name", "").lower() == name_lower:
            return c
    # fallback: substring
    for c in candidates:
        if name_lower in c.get("name", "").lower():
            return c
    return None


class ExplainMatch(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="explain-match", description="Explain why a candidate from your last /find-sponsors fits your team.")
    @app_commands.describe(company="Company name from your last /find-sponsors results")
    async def explain_match(self, interaction: discord.Interaction, company: str):
        guild_id = interaction.guild_id
        user_id = interaction.user.id
        await interaction.response.defer()

        from discord_bot.team_ctx import get_team_context_for_member
        team_context = await get_team_context_for_member(interaction.client, guild_id, user_id)
        if not team_context:
            await interaction.followup.send("Run `/configure-team add` first (use `/my-team` to see teams).", ephemeral=True)
            return

        cache_key = (guild_id, user_id)
        cached = getattr(interaction.client, "sponsor_search_cache", {}).get(cache_key, [])
        entity = _find_in_cache(cached, company)

        if not entity:
            await interaction.followup.send(
                f"No match for **{company}** in your last search. Run `/find-sponsors` first, then use the Explain buttons or type the exact company name.",
                ephemeral=True,
            )
            return

        contact_list = await get_contact_infos([entity])
        contact = contact_list[0] if contact_list else {}
        reasons = entity.get("matched_reasons") or []

        explanation = {
            "entity_name": entity.get("name", company),
            "reason": reasons[0] if reasons else "",
            "tags": entity.get("tags") or [],
            "contact_person": contact.get("contact_person", ""),
            "contact_email": contact.get("contact_email", ""),
            "contact_email_verified": contact.get("contact_email_verified", False),
            "website": contact.get("website", ""),
            "waterloo_affinity_evidence": entity.get("waterloo_affinity_evidence") or [],
            "overall_score": entity.get("overall_score", 0.0),
            "score_breakdown": entity.get("score_breakdown") or {},
        }

        embed = explanation_embed(explanation, team_name=team_context["team_name"])
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ExplainMatch(bot))
