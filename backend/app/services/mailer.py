"""Optional SMTP delivery for school notifications.

The application remains usable without SMTP: callers can present one-time
credentials in the UI when mail is not configured.
"""

import logging
import smtplib
from email.message import EmailMessage

from ..core.config import settings

logger = logging.getLogger(__name__)


def mail_configured() -> bool:
    """Return whether enough settings exist to attempt SMTP delivery."""
    return bool(settings.SMTP_HOST and settings.MAIL_FROM)


def send_teacher_credentials(
    recipient: str,
    teacher_name: str,
    login_email: str,
    temporary_password: str,
    school_name: str,
) -> bool:
    """Send initial teacher credentials, returning False instead of breaking signup."""
    if not mail_configured():
        return False

    message = EmailMessage()
    message["Subject"] = f"Your {school_name} SchoolAssist account"
    message["From"] = settings.MAIL_FROM
    message["To"] = recipient
    message.set_content(
        f"Hello {teacher_name},\n\n"
        f"An account has been created for you at {school_name}.\n\n"
        f"Login email: {login_email}\n"
        f"Temporary password: {temporary_password}\n\n"
        "Please sign in and change your password as soon as possible.\n\n"
        "SchoolAssist"
    )

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            if settings.SMTP_STARTTLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
        return True
    except (OSError, smtplib.SMTPException):
        logger.exception("Unable to send teacher credential email")
        return False
