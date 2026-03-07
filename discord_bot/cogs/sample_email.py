import discord
import google.generativeai as genai
from discord import app_commands
from discord.ext import commands

from config import GEMINI_API_KEY

genai.configure(api_key=GEMINI_API_KEY)
_model = genai.GenerativeModel("gemini-2.0-flash")


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
    response = await _model.generate_content_async(prompt)
    return response.text


class CopyButton(discord.ui.Button):
    def __init__(self, draft: str):
        super().__init__(label="Copy", style=discord.ButtonStyle.secondary)
        self.draft = draft

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(self.draft, ephemeral=True)


class EditEmailModal(discord.ui.Modal, title="Edit Email Draft"):
    body = discord.ui.TextInput(
        label="Email", style=discord.TextStyle.paragraph, max_length=4000
    )

    def __init__(self, draft: str, bot: commands.Bot):
        super().__init__()
        self.body.default = draft
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        edited = self.body.value
        self.bot.email_draft_cache[interaction.guild_id] = edited

        view = discord.ui.View(timeout=300)
        view.add_item(CopyButton(edited))
        await interaction.response.send_message(
            f"```\n{edited}\n```", view=view, ephemeral=True
        )


class EditEmailButton(discord.ui.Button):
    def __init__(self, draft: str, bot: commands.Bot):
        super().__init__(label="Edit Draft", style=discord.ButtonStyle.secondary)
        self.draft = draft
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EditEmailModal(self.draft, self.bot))


class EmailView(discord.ui.View):
    def __init__(self, draft: str, bot: commands.Bot):
        super().__init__(timeout=300)
        self.add_item(EditEmailButton(draft, bot))
        self.add_item(CopyButton(draft))


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

        await interaction.followup.send(f"```\n{draft}\n```", view=EmailView(draft, self.bot))


async def setup(bot: commands.Bot):
    await bot.add_cog(SampleEmail(bot))
