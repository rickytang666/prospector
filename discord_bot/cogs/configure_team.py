
import discord
from discord.ext import commands
from discord import app_commands
from storage import db


async def team_autocomplete(interaction: discord.Interaction, current: str):
    """All teams on the server (for add / join)."""
    guild_id = str(interaction.guild_id) if interaction.guild_id else ""
    if not guild_id:
        return []
    teams = await db.list_teams(guild_id)
    names = [t.get("team_name") or "" for t in teams if t.get("team_name")]
    return [
        app_commands.Choice(name=n, value=n)
        for n in names if current.lower() in n.lower()
    ][:25]


async def my_teams_autocomplete(interaction: discord.Interaction, current: str):
    """Only teams this user is in (for set-active-team / remove)."""
    guild_id = str(interaction.guild_id) if interaction.guild_id else ""
    user_id = str(interaction.user.id) if interaction.user else ""
    if not guild_id or not user_id:
        return []
    my_teams = await db.get_user_teams(guild_id, user_id)
    names = [t.get("team_name") or "" for t in my_teams if t.get("team_name")]
    return [
        app_commands.Choice(name=n, value=n)
        for n in names if current.lower() in n.lower()
    ][:25]


async def configure_team_name_autocomplete(interaction: discord.Interaction, current: str):
    """For configure-team: show my teams when removing, all teams when adding."""
    action = getattr(interaction.namespace, "action", None)
    if action == "remove":
        return await my_teams_autocomplete(interaction, current)
    return await team_autocomplete(interaction, current)


class ConfigureTeam(commands.Cog):
    @app_commands.command(name="configure-team", description="Add or remove yourself from a team (saved to your profile).")
    @app_commands.describe(
        action="Add yourself to a team or remove",
        team_name="Team to join (ignored when removing)",
    )
    @app_commands.choices(action=[app_commands.Choice(name="add", value="add"), app_commands.Choice(name="remove", value="remove")])
    @app_commands.autocomplete(team_name=configure_team_name_autocomplete)
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
            my_teams = await db.get_user_teams(guild_id, user_id)
            if not my_teams:
                await interaction.response.send_message("You are not in any team.", ephemeral=True)
                return
            if len(my_teams) > 1 and not (team_name and team_name.strip()):
                await interaction.response.send_message(
                    "You're in multiple teams; choose which to leave with the `team_name` option.",
                    ephemeral=True,
                )
                return
            to_remove = (team_name or my_teams[0]["team_name"]).strip()
            if not any((t.get("team_name") or "").strip() == to_remove for t in my_teams):
                await interaction.response.send_message(f"You're not in **{to_remove}**. Use `/my-team` to see your teams.", ephemeral=True)
                return
            await db.remove_user_team(guild_id, user_id, to_remove)
            await interaction.response.send_message(f"You left **{to_remove}**. Use `/configure-team add` to join another.", ephemeral=True)
            return

        if not (team_name and team_name.strip()):
            await interaction.response.send_message("Pick a team name when adding.", ephemeral=True)
            return

        teams = await db.list_teams(guild_id)
        if not any((t.get("team_name") or "").strip() == team_name.strip() for t in teams):
            await interaction.response.send_message(f"Team **{team_name}** is not registered. An admin can run `/setup-team` first.", ephemeral=True)
            return

        await db.set_user_team(guild_id, user_id, team_name.strip())
        await interaction.response.send_message(
            f"You are now assigned to **{team_name}**. Your context is loaded from the database when you use /chat, /find-support, etc. Use `/analyze-team` to view the summary.",
            ephemeral=True,
        )

    @app_commands.command(name="my-team", description="Show teams you're in (and which is active), plus teams you can join.")
    async def my_team(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        user_id = str(interaction.user.id)
        if not guild_id:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return

        my_teams = await db.get_user_teams(guild_id, user_id)
        active = await db.get_user_team(guild_id, user_id)
        all_teams = await db.list_teams(guild_id)
        available_names = [t.get("team_name") or "" for t in all_teams if t.get("team_name")]

        embed = discord.Embed(title="Your teams", color=discord.Color.blue())
        if my_teams:
            lines = []
            for t in my_teams:
                name = t.get("team_name") or ""
                mark = " **← active**" if name == active else ""
                lines.append(f"• {name}{mark}")
            embed.add_field(name="Teams you're in", value="\n".join(lines) or "—", inline=False)
            embed.add_field(name="Switch active", value="Use `/set-active-team` and pick a team to use for /chat, /find-support, etc.", inline=False)
        else:
            embed.add_field(name="Teams you're in", value="None — use `/configure-team add` to join one.", inline=False)
        if available_names:
            embed.add_field(name="Available on this server", value="\n".join(f"• {n}" for n in available_names), inline=False)
        else:
            embed.add_field(name="Available", value="No teams registered. An admin can run `/setup-team`.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="set-active-team", description="Set which team to use for /chat, /find-support, etc.")
    @app_commands.describe(team_name="Team to switch to (must be one you're in)")
    @app_commands.autocomplete(team_name=my_teams_autocomplete)
    async def set_active_team(self, interaction: discord.Interaction, team_name: str):
        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        user_id = str(interaction.user.id)
        if not guild_id or not (team_name and team_name.strip()):
            await interaction.response.send_message("Use this in a server and pick a team.", ephemeral=True)
            return

        my_teams = await db.get_user_teams(guild_id, user_id)
        if not my_teams:
            await interaction.response.send_message("Join a team first with `/configure-team add`. Use `/my-team` to see options.", ephemeral=True)
            return
        if not any((t.get("team_name") or "").strip() == team_name.strip() for t in my_teams):
            await interaction.response.send_message(f"You're not in **{team_name}**. Use `/my-team` to see your teams.", ephemeral=True)
            return

        await db.set_active_team(guild_id, user_id, team_name.strip())
        key = (guild_id, user_id)
        cache = getattr(interaction.client, "team_context_cache", None)
        if isinstance(cache, dict) and key in cache:
            del cache[key]
        await interaction.response.send_message(f"**{team_name}** is now your active team for /chat, /find-support, etc.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(ConfigureTeam(bot))
