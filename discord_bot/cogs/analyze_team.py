import asyncio
import json
import os
import discord
from discord.ext import commands
from discord import app_commands
from openai import AsyncOpenAI
from storage import db
from discord_bot.ui.embeds import team_context_embed


async def _llm_recruiting_gaps(team_name: str, stored: dict) -> list[dict]:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        return []
    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)

    import json as _json
    subsystems = stored.get("focus_areas") or []
    blockers = stored.get("blockers") or []
    needs = stored.get("needs") or []
    tech_stack = stored.get("tech_stack") or []

    # raw_llm_output is JSON — parse it to get any extra fields
    raw = stored.get("raw_llm_output") or ""
    if raw:
        try:
            parsed = _json.loads(raw)
            subsystems = subsystems or parsed.get("focus_areas") or []
            blockers = blockers or parsed.get("blockers") or []
            needs = needs or parsed.get("needs") or []
            tech_stack = tech_stack or parsed.get("tech_stack") or []
        except Exception:
            pass

    prompt = f"""You are analyzing a university engineering design team called "{team_name}".

Subsystems / focus areas: {', '.join(subsystems) if subsystems else 'not specified'}
Tech stack: {', '.join(tech_stack) if tech_stack else 'not specified'}
Active blockers: {', '.join(blockers) if blockers else 'none listed'}
Support needs: {', '.join(needs) if needs else 'none listed'}

Based on all the above, what specific engineering or technical roles should this team recruit for?
Be specific to what this team actually does — mention the relevant technology or subsystem in the reason.
Do not give generic answers like "software engineer" without saying what specifically they'd work on.

Return JSON: {{"gaps": [{{"role": "Role Title", "reason": "1 sentence why, mentioning the specific work"}}]}}
3-5 gaps max."""

    try:
        resp = await client.chat.completions.create(
            model="google/gemini-2.5-flash-lite",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=500,
        )
        parsed = json.loads(resp.choices[0].message.content)
        return parsed.get("gaps", [])[:5]
    except Exception as e:
        # print(f"[analyze_team] llm gaps failed: {e}")
        return []


class AnalyzeTeam(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="analyze-team", description="Load your team's context (run after configure-team add).")
    async def analyze_team(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id) if interaction.guild_id else ""
        user_id = str(interaction.user.id)
        if not guild_id:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return

        await interaction.response.defer()

        ctx = await db.get_team_context_for_user(guild_id, user_id)
        if not ctx:
            await interaction.followup.send(
                "Run `/configure-team add` to join a team first. Use `/my-team` to see available teams (admins register them with `/setup-team`).",
                ephemeral=True,
            )
            return

        stored = await db.get_team_context(ctx["team_name"])
        if not stored:
            await interaction.followup.send(
                f"No ingested context for **{ctx['team_name']}**. Run `/setup-team` for that team first.",
                ephemeral=True,
            )
            return

        # print(f"[analyze_team] stored keys: {list(stored.keys())}")
        # print(f"[analyze_team] focus_areas: {stored.get('focus_areas')}")
        # print(f"[analyze_team] blockers: {stored.get('blockers')}")
        # print(f"[analyze_team] raw_llm_output[:200]: {str(stored.get('raw_llm_output', ''))[:200]}")
        # print(f"[analyze_team] ctx subsystems: {ctx.get('subsystems')}")
        recruiting_gaps = await _llm_recruiting_gaps(ctx["team_name"], stored)
        team_context = {
            **ctx,
            "recruiting_gaps": recruiting_gaps,
        }
        key = (str(guild_id), str(user_id))
        if not hasattr(interaction.client, "team_context_cache"):
            interaction.client.team_context_cache = {}
        interaction.client.team_context_cache[key] = team_context

        embed = team_context_embed(team_context)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AnalyzeTeam(bot))
