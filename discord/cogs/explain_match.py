import discord
from discord.ext import commands
from discord import app_commands
from testing_info import MOCK_EXPLANATIONS
from cogs.find_support import explanation_embed


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

        explanation = MOCK_EXPLANATIONS.get(entity_id.lower())

        if not explanation:
            valid = ", ".join(MOCK_EXPLANATIONS.keys())
            await interaction.followup.send(
                f"No explanation found for **{entity_id}**. Valid options: `{valid}`"
            )
            return

        embed = explanation_embed(explanation, team_name=team_context["team_name"])
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ExplainMatch(bot))