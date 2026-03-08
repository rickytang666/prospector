"""Configure which team you're in: add yourself to a team or remove (persisted in DB)."""
import discord
from discord.ext import commands
from discord import app_commands
from storage import db


async def team_autocomplete(interaction: discord.Interaction, current: str):
    guild_id = str(interaction.guild_id) if interaction.guild_id else ""
    if not guild_id:
        return []
    teams = await db.list_teams(guild_id)
    names = [t.get("team_name") or "" for t in teams if t.get("team_name")]
    return [
        app_commands.Choice(name=n, value=n)
        for n in names if current.lower() in n.lower()
    ][:25]


class ConfigureTeam(commands.Cog):
    @app_commands.command(name="configure-team", description="Add or remove yourself from a team (saved to your profile).")
    @app_commands.describe(
        action="Add yourself to a team or remove",
        team_name="Team to join (ignored when removing)",
    )
    @app_commands.choices(action=[app_commands.Choice(name="add", value="add"), app_commands.Choice(name="remove", value="remove")])
    @app_commands.autocomplete(team_name=team_autocomplete)
    async def configure_team(
        self,
        interaction: discord.Interaction,
        action: str,
        team_name: str = "",
    ):
        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        user_id = str(interaction.user.id)
        if not guild_id:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return

        if action == "remove":
            await db.remove_user_team(guild_id, user_id)
            await interaction.response.send_message("You are no longer assigned to a team. Use `/configure-team add` to join one.", ephemeral=True)
            return

        if not (team_name and team_name.strip()):
            await interaction.response.send_message("Pick a team name when adding.", ephemeral=True)
            return

        teams = await db.list_teams(guild_id)
        if not any((t.get("team_name") or "").strip() == team_name.strip() for t in teams):
            await interaction.response.send_message(f"Team **{team_name}** is not registered. An admin can run `/setup-team` first.", ephemeral=True)
            return

        await db.set_user_team(guild_id, user_id, team_name.strip())
        await interaction.response.send_message(f"You are now assigned to **{team_name}**. Run `/analyze-team` to load context.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(ConfigureTeam(bot))
