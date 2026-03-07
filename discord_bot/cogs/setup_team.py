import discord
from discord.ext import commands
from discord import app_commands


async def repo_autocomplete(interaction: discord.Interaction, current: str):
    options = ["https://github.com/UWOrbital/orbital-software/"]
    return [
        app_commands.Choice(name=url, value=url)
        for url in options if current.lower() in url.lower()
    ]


async def team_name_autocomplete(interaction: discord.Interaction, current: str):
    options = ["University of Waterloo Orbital"]
    return [
        app_commands.Choice(name=name, value=name)
        for name in options if current.lower() in name.lower()
    ]


class SetupTeam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup-team", description="Configure the design team repository for this server.")
    @app_commands.autocomplete(repo=repo_autocomplete, team_name=team_name_autocomplete)
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