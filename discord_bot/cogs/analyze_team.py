import discord
from discord.ext import commands
from discord import app_commands
from testing_info import MOCK_TEAM_CONTEXT
from ui.embeds import team_context_embed


class AnalyzeTeam(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="analyze-team", description="Analyze the configured team repository and infer team context.")
    async def analyze_team(self, interaction: discord.Interaction):

        guild_id = interaction.guild_id
        config = interaction.client.team_configs.get(guild_id)

        if not config:
            await interaction.response.send_message("Run `/setup-team` first.")
            return

        await interaction.response.defer()

        team_context = {**MOCK_TEAM_CONTEXT, "team_name": config["team_name"], "repo_url": config["repo_url"]}
        interaction.client.team_context_cache[guild_id] = team_context

        embed = team_context_embed(team_context)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AnalyzeTeam(bot))