import discord
from discord.ext import commands
from discord import app_commands
from testing_info import MOCK_EXPLANATIONS


def explanation_embed(data):
    embed = discord.Embed(
        title=data["entity_name"],
        color=discord.Color.green()
    )

    embed.add_field(
        name="Why it helps",
        value="\n".join(f"• {r}" for r in data["why_it_helps"]),
        inline=False
    )

    embed.add_field(
        name="Why they may care",
        value="\n".join(f"• {r}" for r in data["why_they_may_care"]),
        inline=False
    )

    embed.add_field(
        name="Recommended ask",
        value=data["recommended_ask"],
        inline=False
    )

    return embed


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

        embed = explanation_embed(explanation)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ExplainMatch(bot))