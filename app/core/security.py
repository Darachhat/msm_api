from datetime import datetime, timedelta, timezone
from typing   import Any, Dict, Optional

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(
    schemes      = ["bcrypt"]
    , deprecated = "auto"
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject            : str
    , extra_claims     : Optional[Dict[str, Any]] = None
    , expires_minutes  : Optional[int] = None
) -> str:
    now    = datetime.now(timezone.utc)
    expire = now + timedelta(
        minutes = expires_minutes or settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload: Dict[str, Any] = {
        "sub"    : subject
        , "type" : "access"
        , "iat"  : now
        , "exp"  : expire
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm = settings.JWT_ALGORITHM)


def create_refresh_token(
    subject        : str
    , jti          : str
    , expires_days : Optional[int] = None
) -> str:
    now    = datetime.now(timezone.utc)
    expire = now + timedelta(
        days = expires_days or settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload: Dict[str, Any] = {
        "sub"    : subject
        , "jti"  : jti
        , "type" : "refresh"
        , "iat"  : now
        , "exp"  : expire
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm = settings.JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(
        token
        , settings.JWT_SECRET_KEY
        , algorithms = [settings.JWT_ALGORITHM]
    )
