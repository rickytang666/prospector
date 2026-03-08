
import asyncio
import hashlib
import discord
from discord.ext import commands
from discord import app_commands
from storage import db
from internal_context.ingestion.notion import scrape_notion
from internal_context.ingestion.confluence import scrape_confluence
from internal_context.ingestion.website import scrape_website
from internal_context.embedding.embedder import embed_chunks
from internal_context.extraction.extractor import extract_team_context
from internal_context.models import Chunk


class AddContext(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="add-context", description="Add a documentation source (Notion, Confluence, or URL) to your team.")
    @app_commands.describe(
        source_type="Type of source",
        url="Notion page URL, Confluence space URL, or any docs URL",
    )
    @app_commands.choices(source_type=[
        app_commands.Choice(name="Notion", value="notion"),
        app_commands.Choice(name="Confluence", value="confluence"),
        app_commands.Choice(name="Website / link", value="url"),
    ])
    async def add_context(
        self,
        interaction: discord.Interaction,
        source_type: str,
        url: str,
    ):
        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        user_id = str(interaction.user.id)
        if not guild_id or not url or not url.strip():
            await interaction.response.send_message("Use this in a server and provide a URL.", ephemeral=True)
            return

        team_name = await db.get_user_team(guild_id, user_id)
        if not team_name:
            await interaction.response.send_message(
                "Run `/configure-team add` first to join a team.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        url = url.strip()

        try:
            if source_type == "notion":
                chunks = await asyncio.to_thread(scrape_notion, url, team_name)
            elif source_type == "confluence":
                chunks = await asyncio.to_thread(scrape_confluence, url, team_name)
            else:
                chunks = await asyncio.to_thread(scrape_website, [url], team_name)
        except Exception as e:
            await interaction.followup.send(f"Failed to fetch from that URL: `{e}`", ephemeral=True)
            return

        if not chunks:
            await interaction.followup.send("No content could be extracted from that URL.", ephemeral=True)
            return

        for c in chunks:
            c.content_hash = hashlib.md5(c.content.encode()).hexdigest()
        existing = await db.get_existing_hashes(team_name)
        new_chunks = [c for c in chunks if c.content_hash not in existing]
        if not new_chunks:
            await interaction.followup.send("All content from that URL is already in your team context.", ephemeral=True)
            return

        new_chunks = await asyncio.to_thread(embed_chunks, new_chunks)
        await db.insert_chunks(new_chunks)

        all_rows = await db.get_chunks(team_name)
        all_chunks = [Chunk(team_name=r["team_name"], source_type=r["source_type"], source_url=r.get("source_url"), content=r["content"]) for r in all_rows]
        if all_chunks:
            ctx = await asyncio.to_thread(extract_team_context, team_name, all_chunks)
            await db.upsert_team_context(ctx)

        await interaction.followup.send(
            f"Added **{len(new_chunks)}** new chunk(s) to **{team_name}**. Use `/analyze-team` to refresh the summary.",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(AddContext(bot))
