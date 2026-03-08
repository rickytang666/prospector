import discord
from discord.ext import commands
from discord import app_commands
from storage import db
from discord_bot.ui.embeds import team_context_embed


class AnalyzeTeam(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    def _build_recruiting_gaps(self, blockers: list[str], needs: list[str]):
        text = " ".join((blockers or []) + (needs or [])).lower()
        role_rules = [
            ("Embedded Systems / Firmware", ["firmware", "rtos", "interrupt", "embedded"]),
            ("RF / Communications", ["rf", "radio", "antenna", "signal", "communication"]),
            ("Geospatial / Ground Station", ["mapping", "geospatial", "ground station", "telemetry"]),
            ("Hardware / PCB Manufacturing", ["pcb", "manufacturing", "fabrication", "assembly", "components"]),
            ("Documentation / Onboarding", ["onboarding", "docs", "documentation", "knowledge base"]),
            ("Cloud / Simulation", ["cloud", "simulation", "compute"]),
        ]
        out = []
        for role, kws in role_rules:
            hit = [k for k in kws if k in text]
            if not hit:
                continue
            out.append({
                "role": role,
                "reason": f"Inferred from analyzed context keywords: {', '.join(hit[:3])}.",
            })
        if not out:
            for n in (needs or []):
                if str(n).strip():
                    out.append({"role": str(n), "reason": "Inferred from analyzed team needs."})
        return out[:6]

    @app_commands.command(name="analyze-team", description="Analyze the configured team repository and infer team context.")
    async def analyze_team(self, interaction: discord.Interaction):

        guild_id = interaction.guild_id
        config = interaction.client.team_configs.get(guild_id)

        if not config:
            await interaction.response.send_message("Run `/setup-team` first.")
            return

        await interaction.response.defer()

        team_name = config["team_name"]
        stored = await db.get_team_context(team_name)

        if not stored:
            await interaction.followup.send(
                f"No context found for **{team_name}**. Ingest data first via `POST /internal/ingest`.",
                ephemeral=True,
            )
            return

        blockers = stored.get("blockers", [])
        needs = stored.get("needs", [])
        recruiting_gaps = self._build_recruiting_gaps(blockers, needs)
        team_context = {
            "team_name": team_name,
            "repo": config["repo_url"],
            "repo_url": config["repo_url"],
            "subsystems": stored.get("focus_areas", []),
            "tech_stack": stored.get("tech_stack", []),
            "blockers": blockers,
            # Shape expected by retrieval.api (ranking uses active_blockers + inferred_support_needs)
            "active_blockers": [{"summary": b, "tags": [], "severity": "medium"} for b in blockers],
            "inferred_support_needs": needs,
            "recruiting_gaps": recruiting_gaps,
            "context_summary": stored.get("raw_llm_output", ""),
        }
        interaction.client.team_context_cache[guild_id] = team_context

        embed = team_context_embed(team_context)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AnalyzeTeam(bot))
