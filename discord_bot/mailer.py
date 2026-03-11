import aiosmtplib
from email.mime.text import MIMEText
from discord_bot.config import GMAIL_USER, GMAIL_APP_PASSWORD


async def send_email(to_email: str, subject: str, body: str) -> None:
    message = MIMEText(body, "plain")
    message["From"] = GMAIL_USER
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
