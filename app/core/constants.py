from datetime import timezone
from zoneinfo import ZoneInfo

DATE_FORMAT       = '%Y-%m-%d'
CONTENT_TYPE_JSON = 'application/json'

PHNOM_PENH_TZ : ZoneInfo = ZoneInfo('Asia/Phnom_Penh')
UTC_TZ                   = timezone.utc

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
