from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DATE_FORMAT       = '%Y-%m-%d'
CONTENT_TYPE_JSON = 'application/json'

PHNOM_PENH_TZ : ZoneInfo = ZoneInfo('Asia/Phnom_Penh')
UTC_TZ                   = timezone.utc


def utc_now_naive() -> datetime:
    """Return current UTC timestamp (naive, matching PostgreSQL timestamp without time zone)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


REDACTED_HEADER_KEYS = frozenset({
    'authorization'
    , 'proxy-authorization'
    , 'cookie'
    , 'set-cookie'
    , 'x-api-key'
    , 'x-secret'
    , 'token'
})

REDACTED_BODY_KEYS = frozenset({
    'password'
    , 'current_password'
    , 'new_password'
    , 'password_hash'
    , 'secret'
    , 'access_token'
    , 'refresh_token'
})

ALLOWED_SIGNATURE_MIMES = frozenset({
    'image/png'
    , 'image/jpeg'
    , 'image/webp'
})

ALLOWED_SIGNATURE_EXTS = frozenset({
    '.png'
    , '.jpg'
    , '.jpeg'
    , '.webp'
})
