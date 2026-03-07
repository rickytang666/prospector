import discord
from google import genai
from discord import app_commands
from discord.ext import commands

from config import GEMINI_API_KEY
from ui.buttons import EmailView
from ui.embeds import email_draft_embed

_client = genai.Client(api_key=GEMINI_API_KEY)


async def _generate_email(team_context: dict, organization: str, email_type: str, subject_line: str) -> str:
    prompt = f"""
Write a professional {email_type} email from {team_context['team_name']} to {organization}.

Subject: {subject_line}

Team context:
- Subsystems: {', '.join(team_context['subsystems'])}
- Tech stack: {', '.join(team_context['tech_stack'])}
- Current blockers: {', '.join(team_context['blockers'])}

Requirements:
- Tone: professional, concise, direct
- Length: 150-250 words
- Start with "Subject: ..." on the first line
- No placeholders — write a complete, sendable draft
- {"Request sponsorship or resources" if email_type == "sponsorship" else "Propose collaboration or outreach"}
"""
    response = await _client.aio.models.generate_content(
        model="gemini-2.0-flash", contents=prompt
    )
    return response.text


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
        team_context = self.bot.team_context_cache.get(interaction.guild_id)
        if not team_context:
            await interaction.response.send_message(
                "No team context found. Run `/setup-team` and `/analyze-team` first.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        draft = await _generate_email(team_context, organization, type.value, subject_line)
        self.bot.email_draft_cache[interaction.guild_id] = draft

        embed = email_draft_embed(draft, organization, type.value)
        await interaction.followup.send(embed=embed, view=EmailView(draft, self.bot))


async def setup(bot: commands.Bot):
    await bot.add_cog(SampleEmail(bot))