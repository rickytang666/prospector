import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from internal_context.ingestion.github import scrape_github
from internal_context.ingestion.website import scrape_website
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

    @app_commands.command(name="setup-team", description="Configure a design team and ingest their repository.")
    @app_commands.describe(
        team_name="Name of the team (e.g. UW Orbital)",
        repo="GitHub org URL (e.g. https://github.com/UWOrbital)",
        website_url="Optional team website or docs URL",
    )
    @app_commands.autocomplete(repo=repo_autocomplete, team_name=team_name_autocomplete)
    async def setup_team(
        self,
        interaction: discord.Interaction,
        team_name: str,
        repo: str,
        website_url: str = "",
    ):
        guild_id = interaction.guild_id

        interaction.client.team_configs[guild_id] = {
            "repo_url": repo,
            "team_name": team_name,
        }

        await interaction.response.defer()
        await interaction.followup.send(
            f"Team **{team_name}** configured. Ingesting repository — this may take a minute..."
        )

        try:
            await db.delete_chunks(team_name)
            chunks = []

            if website_url:
                website_chunks = await asyncio.to_thread(scrape_website, [website_url], team_name)
                chunks.extend(website_chunks)
                print(f"[setup_team] {len(website_chunks)} chunks from website")

            github_chunks = await asyncio.to_thread(scrape_github, repo, team_name)
            chunks.extend(github_chunks)
            print(f"[setup_team] {len(github_chunks)} chunks from github")

            if chunks:
                chunks = await asyncio.to_thread(embed_chunks, chunks)
                await db.insert_chunks(chunks)
                ctx = await asyncio.to_thread(extract_team_context, team_name, chunks)
                await db.upsert_team_context(ctx)
                print(f"[setup_team] context upserted for {team_name}")
                await interaction.followup.send(
                    f"Ingestion complete for **{team_name}** — {len(chunks)} chunks indexed. "
                    f"Run `/analyze-team` to load the context."
                )
            else:
                await interaction.followup.send(
                    f"No chunks found for **{team_name}**. Check that the GitHub org URL is correct."
                )
        except Exception as e:
            print(f"[setup_team] ingestion error: {e}")
            await interaction.followup.send(f"Ingestion failed: `{e}`")


async def setup(bot):
    await bot.add_cog(SetupTeam(bot))