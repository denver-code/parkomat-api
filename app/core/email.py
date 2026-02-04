from email.message import EmailMessage
from typing import Optional

import aiosmtplib

from app.core.config import config


async def send_email(
    to: str,
    subject: str,
    body: str,
    sender: Optional[str] = None,
):
    if not all(
        [
            config.SMTP_HOST,
            config.SMTP_PORT,
            config.SMTP_USER,
            config.SMTP_PASSWORD,
            config.SMTP_SENDER,
        ]
    ):
        print("SMTP is not fully configured, skipping email sending.")
        return

    message = EmailMessage()
    message["From"] = sender or config.SMTP_SENDER
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    if config.ENV == "production":
        await aiosmtplib.send(
            message,
            hostname=config.SMTP_HOST,
            port=config.SMTP_PORT,
            username=config.SMTP_USER,
            password=config.SMTP_PASSWORD,
            start_tls=True if config.START_TLS and config.SMTP_PORT == 587 else False,
            use_tls=True if config.USE_TLS and config.SMTP_PORT == 465 else False,
            timeout=10,
        )
    else:
        await aiosmtplib.send(
            message,
            hostname=config.SMTP_HOST,
            port=config.SMTP_PORT,
            timeout=10,
        )
