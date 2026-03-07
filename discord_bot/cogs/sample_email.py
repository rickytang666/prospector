import discord
from discord import app_commands
from discord.ext import commands

from emailgen.email import generate_email


class EditEmailModal(discord.ui.Modal, title="Edit Email Draft"):
    body = discord.ui.TextInput(
        label="Email", style=discord.TextStyle.paragraph, max_length=4000
    )

    def __init__(self, draft: str):
        super().__init__()
        self.body.default = draft

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"```\n{self.body.value}\n```", ephemeral=True
        )


class EditEmailButton(discord.ui.Button):
    def __init__(self, draft: str):
        super().__init__(label="Edit Draft", style=discord.ButtonStyle.secondary)
        self.draft = draft

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EditEmailModal(self.draft))


class EditEmailView(discord.ui.View):
    def __init__(self, draft: str):
        super().__init__(timeout=300)
        self.add_item(EditEmailButton(draft))


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

        draft = await generate_email(team_context, organization, type.value, subject_line)

        view = EditEmailView(draft)
        await interaction.followup.send(f"```\n{draft}\n```", view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(SampleEmail(bot))
