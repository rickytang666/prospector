import aiosmtplib
import discord
from discord import app_commands
from discord.ext import commands
from email.mime.text import MIMEText

from config import GMAIL_USER, GMAIL_APP_PASSWORD
from cogs.sample_email import CopyButton


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

    @app_commands.command(name="send_email", description="Send an email via Gmail")
    @app_commands.describe(
        from_email="Your team's Gmail address",
        to_email="Recipient's email address",
        subject="Email subject line",
        body="Email body text",
    )
    async def send_email_cmd(
        self,
        interaction: discord.Interaction,
        from_email: str,
        to_email: str,
        subject: str,
        body: str,
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            await _send_email(from_email, to_email, subject, body)
        except Exception as e:
            await interaction.followup.send(f"Failed to send email: {e}", ephemeral=True)
            return

        view = discord.ui.View(timeout=300)
        view.add_item(CopyButton(body))

        await interaction.followup.send(
            f"Email sent to **{to_email}**.\n```\n{body}\n```",
            view=view,
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SendEmail(bot))
