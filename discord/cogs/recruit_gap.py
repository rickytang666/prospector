import discord
from discord.ext import commands
from discord import app_commands
from testing_info import MOCK_RECRUIT_GAPS


def recruit_gap_embed(gaps, team_name):
    embed = discord.Embed(
        title=f"{team_name} — Recruiting Gaps",
        color=discord.Color.orange()
    )

    for gap in gaps:
        embed.add_field(
            name=gap["role"],
            value=gap["reason"],
            inline=False
        )

    return embed


class RecruitGap(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="recruit-gap", description="Show inferred recruiting needs for your team.")
    async def recruit_gap(self, interaction: discord.Interaction):

        guild_id = interaction.guild_id
        team_context = interaction.client.team_context_cache.get(guild_id)

        if not team_context:
            await interaction.response.send_message("Run `/analyze-team` first.")
            return

        await interaction.response.defer()

        embed = recruit_gap_embed(MOCK_RECRUIT_GAPS, team_context["team_name"])
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(RecruitGap(bot))
