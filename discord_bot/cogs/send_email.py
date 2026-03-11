import discord
from discord import app_commands
from discord.ext import commands

from discord_bot.services.mailer import send_email as _send_email
from discord_bot.ui.buttons import CopyButton
from discord_bot.ui.embeds import email_sent_embed, _parse_subject_body


class SendEmail(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="send_email", description="Send the latest email draft via Gmail")
    @app_commands.describe(to_email="Recipient's email address")
    async def send_email_cmd(
        self,
        interaction: discord.Interaction,
        to_email: str,
    ):
        draft = self.bot.email_draft_cache.get(interaction.guild_id)
        if not draft:
            await interaction.response.send_message(
                "No draft found. Run `/sample_email` first.", ephemeral=True
            )
            return

        subject, body = _parse_subject_body(draft)

        await interaction.response.defer(ephemeral=True)

        try:
            await _send_email(to_email, subject, body)
        except Exception as e:
            await interaction.followup.send(f"Failed to send email: {e}", ephemeral=True)
            return

        embed = email_sent_embed(to_email, draft)
        view = discord.ui.View(timeout=300)
        view.add_item(CopyButton(draft))

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SendEmail(bot))
