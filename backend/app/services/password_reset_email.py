"""Send GeneGlass password reset links using Gmail SMTP over STARTTLS."""

from email.message import EmailMessage
import smtplib
import ssl
from urllib.parse import quote

from app.core.config import get_settings


class PasswordResetEmailError(RuntimeError):
    """Raised when the configured SMTP service cannot deliver a reset email."""


def send_password_reset_email(recipient_email: str, token: str) -> None:
    """Deliver a password-reset URL; never log the token or credentials."""
    settings = get_settings()
    if not settings.smtp_email or not settings.smtp_app_password:
        raise RuntimeError("Password reset email has not been configured")

    reset_url = settings.frontend_reset_url + "#reset=" + quote(token, safe="")
    message = EmailMessage()
    message["Subject"] = "GeneGlass | Reset your password"
    message["From"] = settings.smtp_email
    message["To"] = recipient_email
    message.set_content(
        "A password reset was requested for your GeneGlass account.\n\n"
        "Open this link to set a new password:\n"
        f"{reset_url}\n\n"
        "The link expires in 15 minutes and works only once.\n"
        "If you did not request this change, you can ignore this email.\n"
        "Do not forward this link."
    )

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(settings.smtp_email, settings.smtp_app_password)
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as error:
        raise PasswordResetEmailError("Password reset email delivery failed") from error
