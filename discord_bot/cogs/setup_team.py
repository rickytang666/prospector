import discord
from discord.ext import commands
from discord import app_commands

class SetupTeam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup-team", description="Configure the design team repository for this server.")
    async def setup_team(
        self,
        interaction: discord.Interaction,
        repo: str,
        team_name: str
    ):
        guild_id = interaction.guild_id

        interaction.client.team_configs[guild_id] = {
            "repo_url": repo,
            "team_name": team_name
        }

        await interaction.response.send_message(
            f"Team **{team_name}** configured.\n"
            f"Repository set to: {repo}"
        )

async def setup(bot):
    await bot.add_cog(SetupTeam(bot))