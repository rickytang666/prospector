import asyncio
import hashlib
import discord
from discord.ext import commands
from discord import app_commands
from internal_context.ingestion.github import scrape_github
from internal_context.ingestion.website import scrape_website
from internal_context.ingestion.notion import scrape_notion
from internal_context.ingestion.confluence import scrape_confluence
from internal_context.embedding.embedder import embed_chunks
from internal_context.extraction.extractor import extract_team_context
from storage import db


async def repo_autocomplete(interaction: discord.Interaction, current: str):
    options = [
        "https://github.com/UWOrbital",
        "https://github.com/WATonomous",
    ]
    return [
        app_commands.Choice(name=url, value=url)
        for url in options if current.lower() in url.lower()
    ]


async def team_name_autocomplete(interaction: discord.Interaction, current: str):
    options = ["UW Orbital", "WATonomous"]
    return [
        app_commands.Choice(name=name, value=name)
        for name in options if current.lower() in name.lower()
    ]


class SetupTeam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup-team", description="Register a team and ingest its repository (first step, server-wide).")
    @app_commands.describe(
        team_name="Name of the team (e.g. UW Orbital)",
        repo="GitHub org URL (e.g. https://github.com/UWOrbital)",
        website_url="Optional team website or docs URL",
        notion_url="Optional Notion page URL",
        confluence_url="Optional Confluence space URL (e.g. https://team.atlassian.net/wiki/spaces/KEY)",
    )
    @app_commands.autocomplete(repo=repo_autocomplete, team_name=team_name_autocomplete)
    async def setup_team(
        self,
        interaction: discord.Interaction,
        team_name: str,
        repo: str,
        website_url: str = "",
        notion_url: str = "",
        confluence_url: str = "",
    ):
        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        if not guild_id:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return

        await db.upsert_team(guild_id, team_name, repo)

        await interaction.response.defer()
        await interaction.followup.send(
            f"Team **{team_name}** registered. Ingesting repository — this may take a minute..."
        )

        try:
            chunks = []

            if website_url:
                website_chunks = await asyncio.to_thread(scrape_website, [website_url], team_name)
                chunks.extend(website_chunks)
                print(f"[setup_team] {len(website_chunks)} chunks from website")

            github_chunks = await asyncio.to_thread(scrape_github, repo, team_name)
            chunks.extend(github_chunks)
            print(f"[setup_team] {len(github_chunks)} chunks from github")

            if notion_url:
                print(f"[setup_team] scraping notion: {notion_url}")
                await interaction.followup.send(f"Scraping Notion page...")
                notion_chunks = await asyncio.to_thread(scrape_notion, notion_url, team_name)
                chunks.extend(notion_chunks)
                print(f"[setup_team] {len(notion_chunks)} chunks from notion")
                await interaction.followup.send(f"Notion: {len(notion_chunks)} chunks indexed.")

            if confluence_url:
                print(f"[setup_team] scraping confluence: {confluence_url}")
                await interaction.followup.send(f"Scraping Confluence space...")
                confluence_chunks = await asyncio.to_thread(scrape_confluence, confluence_url, team_name)
                chunks.extend(confluence_chunks)
                print(f"[setup_team] {len(confluence_chunks)} chunks from confluence")
                await interaction.followup.send(f"Confluence: {len(confluence_chunks)} chunks indexed.")

            if chunks:
                for c in chunks:
                    c.content_hash = hashlib.md5(c.content.encode()).hexdigest()

                existing = await db.get_existing_hashes(team_name)
                new_hashes = {c.content_hash for c in chunks}
                stale_ids = [cid for h, cid in existing.items() if h not in new_hashes]
                await db.delete_chunks_by_ids(stale_ids)

                new_chunks = [c for c in chunks if c.content_hash not in existing]
                if new_chunks:
                    new_chunks = await asyncio.to_thread(embed_chunks, new_chunks)
                    await db.insert_chunks(new_chunks)
                print(f"[setup_team] inserted {len(new_chunks)}, skipped {len(chunks) - len(new_chunks)} unchanged")

                ctx = await asyncio.to_thread(extract_team_context, team_name, chunks)
                await db.upsert_team_context(ctx)
                print(f"[setup_team] context upserted for {team_name}")
                await interaction.followup.send(
                    f"Ingestion complete for **{team_name}**. Members can run `/configure-team add` to join and `/my-team` to see all teams."
                )
            else:
                await interaction.followup.send(
                    f"No chunks found for **{team_name}**. Team is registered. Check the GitHub org URL or run `/add-context` later."
                )
        except Exception as e:
            print(f"[setup_team] ingestion error: {e}")
            await interaction.followup.send(f"Ingestion failed: `{e}`")


async def setup(bot):
    await bot.add_cog(SetupTeam(bot))