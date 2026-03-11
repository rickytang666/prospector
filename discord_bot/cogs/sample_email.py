import discord
from discord import app_commands
from discord.ext import commands

from discord_bot.services.ai import generate_email
from discord_bot.ui.buttons import EmailView
from discord_bot.ui.embeds import email_draft_embed


class SampleEmail(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="sample_email", description="Draft a cold email to a company (subject line auto-generated)")
    @app_commands.describe(
        organization="Company name to address the email to",
        type="Type of email to generate",
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

        draft = await generate_email(team_context, organization, type.value)
        self.bot.email_draft_cache[interaction.guild_id] = draft

        embed = email_draft_embed(draft, organization, type.value)
        await interaction.followup.send(embed=embed, view=EmailView(draft, self.bot))


async def setup(bot: commands.Bot):
    await bot.add_cog(SampleEmail(bot))