"""Nuke a team's data with confirmation (emoji + timeout)."""
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from storage import db

CONFIRM_EMOJI = "✅"
TIMEOUT_SEC = 30


class Nuke(commands.Cog):
    @app_commands.command(name="nuke", description="Wipe all data for your team (chunks, context, assignments). Confirm with ✅.")
    async def nuke(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        user_id = str(interaction.user.id)
        if not guild_id:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return

        team_name = await db.get_user_team(guild_id, user_id)
        if not team_name:
            await interaction.response.send_message("You are not assigned to a team. Use `/configure-team add` first.", ephemeral=True)
            return

        embed = discord.Embed(
            title="⚠️ Nuke team data",
            description=f"**{team_name}** will be fully wiped: all ingested chunks, team context, and everyone's assignment to this team.",
            color=discord.Color.red(),
        )
        embed.add_field(name="Confirm", value=f"React with {CONFIRM_EMOJI} within {TIMEOUT_SEC} seconds to confirm.", inline=False)
        await interaction.response.send_message(embed=embed)

        message = await interaction.original_response()
        try:
            await message.add_reaction(CONFIRM_EMOJI)
        except Exception:
            pass

        def check(reaction: discord.Reaction, u: discord.User):
            return u.id == interaction.user.id and reaction.message.id == message.id and str(reaction.emoji) == CONFIRM_EMOJI

        try:
            await self.bot.wait_for("reaction_add", timeout=TIMEOUT_SEC, check=check)
        except asyncio.TimeoutError:
            await message.edit(content="Nuke cancelled (timeout).", embed=None)
            return

        await message.edit(content="Nuking...", embed=None)
        try:
            await db.delete_chunks(team_name)
            await db.delete_team_context(team_name)
            await db.remove_user_teams_for_team(guild_id, team_name)
            await db.delete_team(guild_id, team_name)
        except Exception as e:
            await message.edit(content=f"Nuke failed: `{e}`")
            return

        cache = getattr(self.bot, "team_context_cache", {})
        for key in list(cache.keys()):
            if cache[key].get("team_name") == team_name:
                del cache[key]

        await message.edit(content=f"**{team_name}** has been nuked. All chunks, context, and assignments removed.")


async def setup(bot):
    await bot.add_cog(Nuke(bot))
