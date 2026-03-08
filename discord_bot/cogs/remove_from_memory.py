"""Remove inaccurate chunks from your team's memory by query."""
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from storage import db
from internal_context.extraction.extractor import extract_team_context
from internal_context.models import Chunk


class RemoveFromMemory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="remove_from_memory", description="Find and remove chunks that match a query (e.g. inaccurate info).")
    @app_commands.describe(query="Text to search for in stored chunks; matching chunks will be deleted.")
    async def remove_from_memory(self, interaction: discord.Interaction, query: str):
        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        user_id = str(interaction.user.id)
        if not guild_id:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return

        team_name = await db.get_user_team(guild_id, user_id)
        if not team_name:
            await interaction.response.send_message("Run `/configure-team add` first to have a team.", ephemeral=True)
            return

        query = (query or "").strip()
        if not query:
            await interaction.response.send_message("Provide a `query` string to search for.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        ids = await db.find_chunk_ids_by_query(team_name, query, limit=50)
        if not ids:
            await interaction.followup.send(f"No chunks found containing \"{query[:50]}...\" for **{team_name}**.", ephemeral=True)
            return

        await db.delete_chunks_by_ids(ids)
        all_rows = await db.get_chunks(team_name)
        if all_rows:
            all_chunks = [Chunk(team_name=r["team_name"], source_type=r["source_type"], source_url=r.get("source_url"), content=r["content"]) for r in all_rows]
            ctx = await asyncio.to_thread(extract_team_context, team_name, all_chunks)
            await db.upsert_team_context(ctx)

        cache = getattr(self.bot, "team_context_cache", {})
        for key in list(cache.keys()):
            if cache[key].get("team_name") == team_name:
                del cache[key]

        await interaction.followup.send(
            f"Removed **{len(ids)}** chunk(s) matching \"{query[:40]}{'...' if len(query) > 40 else ''}\" from **{team_name}**. Run `/analyze-team` to refresh.",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(RemoveFromMemory(bot))
