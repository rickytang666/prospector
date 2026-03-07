import discord
from discord.ext import commands
from discord import app_commands
from storage import db
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
        print("[analyze_team] deferred, starting db lookup")

        team_name = config["team_name"]
        print(f"[analyze_team] calling get_team_context for '{team_name}'")
        stored = await db.get_team_context(team_name)
        print(f"[analyze_team] db returned: {stored}")

        if not stored:
            await interaction.followup.send(
                f"No context found for **{team_name}**. Ingest data first via `POST /internal/ingest`.",
                ephemeral=True,
            )
            return

        blockers = stored.get("blockers", [])
        team_context = {
            "team_name": team_name,
            "repo": config["repo_url"],
            "repo_url": config["repo_url"],
            "subsystems": stored.get("focus_areas", []),
            "tech_stack": stored.get("tech_stack", []),
            "blockers": blockers,
            # Shape expected by retrieval.api (ranking uses active_blockers + inferred_support_needs)
            "active_blockers": [{"summary": b, "tags": [], "severity": "medium"} for b in blockers],
            "inferred_support_needs": stored.get("needs", []),
            "context_summary": stored.get("raw_llm_output", ""),
        }
        print(f"[analyze_team] built team_context, sending embed")
        interaction.client.team_context_cache[guild_id] = team_context

        embed = team_context_embed(team_context)
        print(f"[analyze_team] calling followup.send")
        await interaction.followup.send(embed=embed)
        print(f"[analyze_team] done")


async def setup(bot):
    await bot.add_cog(AnalyzeTeam(bot))