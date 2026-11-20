import smtplib
import threading
import time
from email.message import EmailMessage
from typing        import Any, Callable, Dict, Optional

from app.core.config       import settings
from app.core.db           import getStaticSession
from app.core.enum         import AUTH_TYPE_ENUM, STATUS_CODE_ENUM, TRAFFIC_TYPE_ENUM
from app.core.log          import logger
from app.models.auth_model import CREDENTIAL_BASIC_MODEL, SYSTEM_CREDENTIAL_MODEL, SYSTEM_MODEL

EmailSenderHook  = Callable[[str, str, str], None]
SMTP_SYSTEM_CODE = "SMTP_MAILER"
_CACHE_TTL       = 300  # seconds


class EmailService:
    """Pluggable email delivery service with DB-first (auth.system) + .env SMTP fallback."""

    _custom_sender    : Optional[EmailSenderHook]  = None
    _cached_smtp      : Optional[Dict[str, Any]]   = None
    _cache_expires_at : float                      = 0.0


    @classmethod
    def register_sender(cls, sender: Optional[EmailSenderHook]) -> None:
        """Register a custom email delivery hook (e.g., Resend, SES, or test double)."""
        cls._custom_sender = sender


    @classmethod
    def _load_smtp_from_db(cls) -> Optional[Dict[str, Any]]:
        try:
            session = getStaticSession()
            try:
                system = (
                    session.query(SYSTEM_MODEL)
                    .filter(
                        SYSTEM_MODEL.code == SMTP_SYSTEM_CODE
                        , SYSTEM_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                        , SYSTEM_MODEL.deleted_datetime.is_(None)
                    )
                    .first()
                )
                if not system or not system.base_url:
                    return None

                cred = (
                    session.query(CREDENTIAL_BASIC_MODEL)
                    .join(
                        SYSTEM_CREDENTIAL_MODEL
                        , (SYSTEM_CREDENTIAL_MODEL.system_code == CREDENTIAL_BASIC_MODEL.system_code)
                        & (SYSTEM_CREDENTIAL_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.OUTBOUND.value)
                        & (SYSTEM_CREDENTIAL_MODEL.auth_type_code == AUTH_TYPE_ENUM.BASIC.value)
                        & (SYSTEM_CREDENTIAL_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value)
                        & (SYSTEM_CREDENTIAL_MODEL.deleted_datetime.is_(None))
                    )
                    .filter(
                        CREDENTIAL_BASIC_MODEL.system_code == SMTP_SYSTEM_CODE
                        , CREDENTIAL_BASIC_MODEL.traffic_type == TRAFFIC_TYPE_ENUM.OUTBOUND.value
                        , CREDENTIAL_BASIC_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                        , CREDENTIAL_BASIC_MODEL.deleted_datetime.is_(None)
                    )
                    .first()
                )
                meta = system.metadata_json or {}
                return {
                    "host"         : system.base_url
                    , "port"       : int(meta.get("port") or settings.SMTP_PORT)
                    , "user"       : cred.username if cred else ""
                    , "password"   : cred.password if cred else ""
                    , "from_email" : meta.get("from_email") or settings.SMTP_FROM
                    , "use_tls"    : bool(meta.get("use_tls", settings.SMTP_USE_TLS))
                }
            finally:
                session.close()
        except Exception as db_error:
            logger.warn(f"EmailService._load_smtp_from_db: falling back to .env ({str(db_error)})")
            return None


    @classmethod
    def resolve_smtp_config(cls) -> Dict[str, Any]:
        """Return SMTP config from auth.system (DB) or fall back to .env settings."""
        now = time.monotonic()
        if cls._cached_smtp is not None and now < cls._cache_expires_at:
            return cls._cached_smtp

        db_cfg = cls._load_smtp_from_db()
        if db_cfg and db_cfg.get("host"):
            cls._cached_smtp      = db_cfg
            cls._cache_expires_at = now + _CACHE_TTL
            return db_cfg

        env_cfg = {
            "host"         : settings.SMTP_HOST
            , "port"       : settings.SMTP_PORT
            , "user"       : settings.SMTP_USER
            , "password"   : settings.SMTP_PASS
            , "from_email" : settings.SMTP_FROM
            , "use_tls"    : settings.SMTP_USE_TLS
        }
        cls._cached_smtp      = env_cfg
        cls._cache_expires_at = now + _CACHE_TTL
        return env_cfg


    @classmethod
    def send_email(cls, to_email: str, subject: str, body: str) -> bool:
        """Send an email via registered hook or background SMTP thread."""
        if cls._custom_sender is not None:
            try:
                cls._custom_sender(to_email, subject, body)
                return True
            except Exception as hook_error:
                logger.error(f"EmailService custom sender failed: {str(hook_error)}")
                return False

        smtp_cfg = cls.resolve_smtp_config()
        if not smtp_cfg["host"]:
            logger.warn(
                f"EmailService.send_email: SMTP host not configured (DB or .env) — skipping email to {to_email}"
            )
            return False

        def _deliver_smtp() -> None:
            try:
                message            = EmailMessage()
                message["From"]    = smtp_cfg["from_email"]
                message["To"]      = to_email
                message["Subject"] = subject
                message.set_content(body)

                with smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"], timeout=10) as smtp:
                    if smtp_cfg["use_tls"]:
                        smtp.starttls()
                    if smtp_cfg["user"] and smtp_cfg["password"]:
                        smtp.login(smtp_cfg["user"], smtp_cfg["password"])
                    smtp.send_message(message)

                logger.info(f"EmailService.send_email: Sent email to {to_email}, subject: {subject}")
            except Exception as smtp_error:
                logger.error(f"EmailService.send_email: SMTP delivery failed: {str(smtp_error)}")

        threading.Thread(target = _deliver_smtp, daemon = True).start()
        return True


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
