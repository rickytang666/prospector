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

    @app_commands.command(name="analyze-team", description="Load your team's context (run after configure-team add).")
    async def analyze_team(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        user_id = str(interaction.user.id)
        if not guild_id:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return

        ctx = await db.get_team_context_for_user(guild_id, user_id)
        if not ctx:
            await interaction.response.send_message(
                "Run `/configure-team add` and pick a team first. Teams are registered with `/setup-team`.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
<<<<<<< HEAD

        team_name = config["team_name"]
        stored = await db.get_team_context(team_name)

=======
        stored = await db.get_team_context(ctx["team_name"])
>>>>>>> 37f84260dcddf53ec65b52a28d5cd3165dc3dc5c
        if not stored:
            await interaction.followup.send(
                f"No ingested context for **{ctx['team_name']}**. Run `/setup-team` for that team first.",
                ephemeral=True,
            )
            return

        blockers = stored.get("blockers", [])
        needs = stored.get("needs", [])
        recruiting_gaps = self._build_recruiting_gaps(blockers, needs)
        team_context = {
            **ctx,
            "recruiting_gaps": recruiting_gaps,
        }
<<<<<<< HEAD
        interaction.client.team_context_cache[guild_id] = team_context
=======
        key = (guild_id, user_id)
        if not hasattr(interaction.client, "team_context_cache"):
            interaction.client.team_context_cache = {}
        interaction.client.team_context_cache[key] = team_context
>>>>>>> 37f84260dcddf53ec65b52a28d5cd3165dc3dc5c

        embed = team_context_embed(team_context)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AnalyzeTeam(bot))
