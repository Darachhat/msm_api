import smtplib
from email.message import EmailMessage
from typing        import Callable, Optional

from app.core.config import settings
from app.core.log    import logger

EmailSenderHook = Callable[[str, str, str], None]


class EmailService:
    """Pluggable email delivery service with built-in SMTP transport."""

    _custom_sender : Optional[EmailSenderHook] = None


    @classmethod
    def register_sender(cls, sender: Optional[EmailSenderHook]) -> None:
        """Register a custom email delivery hook (e.g., Resend, SES, or test double)."""
        cls._custom_sender = sender


    @classmethod
    def send_email(cls, to_email: str, subject: str, body: str) -> bool:
        """Send an email via registered hook or SMTP. Returns True if dispatched."""
        if cls._custom_sender is not None:
            try:
                cls._custom_sender(to_email, subject, body)
                return True
            except Exception as hook_error:
                logger.error(f"EmailService custom sender failed: {str(hook_error)}")
                return False

        if not settings.SMTP_HOST:
            logger.warn(
                f"EmailService.send_email: SMTP_HOST not configured — skipping email to {to_email}"
            )
            return False

        try:
            message            = EmailMessage()
            message["From"]    = settings.SMTP_FROM
            message["To"]      = to_email
            message["Subject"] = subject
            message.set_content(body)

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
                if settings.SMTP_USE_TLS:
                    smtp.starttls()
                if settings.SMTP_USER and settings.SMTP_PASS:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASS)
                smtp.send_message(message)

            logger.info(f"EmailService.send_email: Sent email to {to_email}, subject: {subject}")
            return True
        except Exception as smtp_error:
            logger.error(f"EmailService.send_email: SMTP delivery failed: {str(smtp_error)}")
            return False


    @classmethod
    def send_password_reset_email(
        cls
        , to_email    : str
        , username    : str
        , reset_url   : str
        , reset_token : str
    ) -> bool:
        subject = f"[{settings.PROJECT_NAME}] Password Reset Request"
        body    = (
            f"Hello {username},\n\n"
            f"We received a request to reset your password.\n"
            f"Use the link below (valid for {settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes):\n\n"
            f"{reset_url}\n\n"
            f"If you did not request this, you can safely ignore this email.\n"
        )
        return cls.send_email(to_email=to_email, subject=subject, body=body)
