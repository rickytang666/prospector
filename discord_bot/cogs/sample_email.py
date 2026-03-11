import os
import discord
from openai import AsyncOpenAI
from discord import app_commands
from discord.ext import commands

from discord_bot.ui.buttons import EmailView
from discord_bot.ui.embeds import email_draft_embed


async def _generate_email(team_context: dict, organization: str, email_type: str, subject_line: str) -> str:
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    prompt = f"""Write a professional {email_type} email from {team_context['team_name']} to {organization}.

Subject: {subject_line}

Team context:
- Subsystems: {', '.join(team_context.get('subsystems') or [])}
- Tech stack: {', '.join(team_context.get('tech_stack') or [])}
- Current blockers: {', '.join(team_context.get('blockers') or [])}

Requirements:
- Tone: professional, concise, direct
- Length: 150-250 words
- Start with "Subject: ..." on the first line
- No placeholders — write a complete, sendable draft
- {"Request sponsorship or resources" if email_type == "sponsorship" else "Propose collaboration or outreach"}"""
    resp = await client.chat.completions.create(
        model="google/gemini-2.5-flash-lite",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
    )
    return (resp.choices[0].message.content or "").strip()


class SampleEmail(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="sample_email", description="Generate a professional email draft using AI")
    @app_commands.describe(
        organization="The organization to address the email to",
        type="Type of email to generate",
        subject_line="Subject line for the email",
    )
    @app_commands.choices(type=[
        app_commands.Choice(name="sponsorship", value="sponsorship"),
        app_commands.Choice(name="outreach", value="outreach"),
    ])
    async def sample_email(
        self,
        interaction: discord.Interaction,
        organization: str,
        type: app_commands.Choice[str],
        subject_line: str,
    ):
        await interaction.response.defer()

        from discord_bot.team_ctx import get_team_context_for_member
        team_context = await get_team_context_for_member(self.bot, interaction.guild_id, interaction.user.id)
        if not team_context:
            await interaction.followup.send(
                "Run `/configure-team add` first (use `/my-team` to see teams).",
                ephemeral=True,
            )
            return

        draft = await _generate_email(team_context, organization, type.value, subject_line)
        self.bot.email_draft_cache[interaction.guild_id] = draft

        embed = email_draft_embed(draft, organization, type.value)
        await interaction.followup.send(embed=embed, view=EmailView(draft, self.bot))


async def setup(bot: commands.Bot):
    await bot.add_cog(SampleEmail(bot))