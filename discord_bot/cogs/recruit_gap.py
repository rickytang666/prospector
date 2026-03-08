import discord
from discord.ext import commands
from discord import app_commands
import re
from storage import db
from ui.embeds import recruit_gap_embed


class RecruitGap(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    def _infer_from_chunks(self, chunks):
        role_rules = [
            ("Embedded Systems / Firmware", ["firmware", "rtos", "interrupt", "embedded"]),
            ("RF / Communications", ["rf", "radio", "antenna", "signal", "communication"]),
            ("Geospatial / Ground Station", ["mapping", "geospatial", "ground station", "telemetry"]),
            ("Hardware / PCB Manufacturing", ["pcb", "manufacturing", "fabrication", "assembly", "components"]),
            ("Documentation / Onboarding", ["onboarding", "docs", "documentation", "knowledge base"]),
            ("Cloud / Simulation", ["cloud", "simulation", "compute"]),
        ]
        text = " ".join((c.get("content") or "") for c in chunks).lower()
        out = []
        for role, kws in role_rules:
            hit = [k for k in kws if re.search(r"\b" + re.escape(k) + r"\b", text)]
            if not hit:
                continue
            out.append({
                "role": role,
                "reason": f"Internal context mentions: {', '.join(hit[:3])}.",
            })
        return out

    @app_commands.command(name="recruit-gap", description="Show inferred recruiting needs for your team.")
    async def recruit_gap(self, interaction: discord.Interaction):

        guild_id = interaction.guild_id
        team_context = interaction.client.team_context_cache.get(guild_id)

        if not team_context:
            await interaction.response.send_message("Run `/analyze-team` first.")
            return

        await interaction.response.defer()

        team_name = team_context.get("team_name", "")
        chunks = await db.get_chunks(team_name) if team_name else []
        gaps = self._infer_from_chunks(chunks)

        if not gaps:
            gaps = [{"role": need, "reason": "Inferred from analyzed team context."} for need in team_context.get("inferred_support_needs", [])]

        if not gaps:
            await interaction.followup.send("No recruiting gaps inferred for this team.")
            return

        embed = recruit_gap_embed(gaps, team_context["team_name"])
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(RecruitGap(bot))
