import aiosmtplib
import discord
from discord import app_commands
from discord.ext import commands
from email.mime.text import MIMEText

from config import GMAIL_USER, GMAIL_APP_PASSWORD
from ui.buttons import CopyButton
from ui.embeds import email_sent_embed, _parse_subject_body


async def _send_email(from_email: str, to_email: str, subject: str, body: str) -> None:
    message = MIMEText(body, "plain")
    message["From"] = from_email
    message["To"] = to_email
    message["Subject"] = subject

    await aiosmtplib.send(
        message,
        hostname="smtp.gmail.com",
        port=465,
        username=GMAIL_USER,
        password=GMAIL_APP_PASSWORD,
        use_tls=True,
    )


class SendEmail(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="send_email", description="Send the latest email draft via Gmail")
    @app_commands.describe(
        from_email="Your team's Gmail address",
        to_email="Recipient's email address",
    )
    async def send_email_cmd(
        self,
        interaction: discord.Interaction,
        from_email: str,
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
            await _send_email(from_email, to_email, subject, body)
        except Exception as e:
            await interaction.followup.send(f"Failed to send email: {e}", ephemeral=True)
            return

        embed = email_sent_embed(to_email, draft)
        view = discord.ui.View(timeout=300)
        view.add_item(CopyButton(draft))

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SendEmail(bot))
