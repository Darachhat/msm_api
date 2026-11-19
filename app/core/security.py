import hashlib
import hmac
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing   import Any, Dict, Optional, Tuple
from uuid     import uuid4

import jwt
from argon2            import PasswordHasher, Type as Argon2Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.hazmat.primitives              import serialization
from cryptography.hazmat.primitives.asymmetric   import rsa
from passlib.context import CryptContext

from app.core.config import settings
from app.core.log    import logger

# Primary password hasher: Argon2id (OWASP recommended parameters)
_argon2_hasher = PasswordHasher(
    time_cost    = 3
    , memory_cost = 65536
    , parallelism = 4
    , hash_len    = 32
    , salt_len    = 16
    , type        = Argon2Type.ID
)

# Legacy fallback so existing bcrypt hashes still verify and auto-upgrade to Argon2id on login
_legacy_bcrypt_context = CryptContext(
    schemes      = ["bcrypt"]
    , deprecated = "auto"
)

_rsa_key_lock      = threading.Lock()
_cached_private_pem : Optional[str] = None
_cached_public_pem  : Optional[str] = None


def _normalize_pem(raw_value: str) -> str:
    return raw_value.replace("\\n", "\n").strip()


def _load_rsa_keypair() -> Tuple[str, str]:
    """Load RS256 private/public PEM keys from environment variables.

    In dev mode only, generates an ephemeral 2048-bit RSA keypair if keys are omitted.
    In non-dev environments, fails fast if JWT_PRIVATE_KEY or JWT_PUBLIC_KEY is missing.
    """
    global _cached_private_pem, _cached_public_pem

    if _cached_private_pem and _cached_public_pem:
        return _cached_private_pem, _cached_public_pem

    with _rsa_key_lock:
        if _cached_private_pem and _cached_public_pem:
            return _cached_private_pem, _cached_public_pem

        private_pem = _normalize_pem(settings.JWT_PRIVATE_KEY)
        public_pem  = _normalize_pem(settings.JWT_PUBLIC_KEY)

        if private_pem and public_pem:
            _cached_private_pem = private_pem
            _cached_public_pem  = public_pem
            return _cached_private_pem, _cached_public_pem

        if private_pem and not public_pem:
            private_key = serialization.load_pem_private_key(private_pem.encode("utf-8"), password=None)
            derived_pub = private_key.public_key().public_bytes(
                encoding = serialization.Encoding.PEM
                , format = serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode("utf-8")
            _cached_private_pem = private_pem
            _cached_public_pem  = derived_pub
            return _cached_private_pem, _cached_public_pem

        if settings.ENVIRONMENT.lower() != "dev":
            raise RuntimeError(
                "RS256 JWT keys are not configured. "
                "Set JWT_PRIVATE_KEY and JWT_PUBLIC_KEY environment variables."
            )

        logger.warn(
            "JWT_PRIVATE_KEY / JWT_PUBLIC_KEY not set in dev mode — "
            "generating an ephemeral RS256 keypair for this process."
        )
        ephemeral_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        _cached_private_pem = ephemeral_key.private_bytes(
            encoding                = serialization.Encoding.PEM
            , format                = serialization.PrivateFormat.PKCS8
            , encryption_algorithm  = serialization.NoEncryption()
        ).decode("utf-8")
        _cached_public_pem = ephemeral_key.public_key().public_bytes(
            encoding = serialization.Encoding.PEM
            , format = serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode("utf-8")
        return _cached_private_pem, _cached_public_pem


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _argon2_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against Argon2id (with legacy bcrypt fallback)."""
    if not hashed_password:
        return False

    if hashed_password.startswith("$argon2"):
        try:
            return _argon2_hasher.verify(hashed_password, plain_password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    # Legacy bcrypt fallback
    try:
        return _legacy_bcrypt_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def needs_password_rehash(hashed_password: str) -> bool:
    """Return True if a stored hash is legacy (non-Argon2id) or needs updated Argon2id params."""
    if not hashed_password or not hashed_password.startswith("$argon2id$"):
        return True
    try:
        return _argon2_hasher.check_needs_rehash(hashed_password)
    except Exception:
        return True


def hash_token(raw_token: str) -> str:
    """Return a SHA-256 hex digest of a token so raw secrets are never stored in DB."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_opaque_refresh_token() -> str:
    """Generate a cryptographically random opaque refresh token (512 bits of entropy)."""
    return secrets.token_urlsafe(64)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def verify_csrf_token(cookie_token: Optional[str], header_token: Optional[str]) -> bool:
    if not cookie_token or not header_token:
        return False
    return hmac.compare_digest(cookie_token, header_token)


def create_access_token(
    subject           : str
    , token_version   : int                      = 0
    , extra_claims    : Optional[Dict[str, Any]] = None
    , expires_minutes : Optional[int]            = None
) -> str:
    private_pem, _ = _load_rsa_keypair()
    now            = datetime.now(timezone.utc)
    expire         = now + timedelta(
        minutes = expires_minutes or settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload: Dict[str, Any] = {
        "sub"    : subject
        , "jti"  : str(uuid4())
        , "ver"  : token_version
        , "type" : "access"
        , "iss"  : settings.JWT_ISSUER
        , "aud"  : settings.JWT_AUDIENCE
        , "iat"  : now
        , "exp"  : expire
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, private_pem, algorithm = "RS256")


def decode_token(
    token           : str
    , expected_type : Optional[str] = "access"
) -> Dict[str, Any]:
    """Decode and strictly validate RS256 signature, issuer, audience, expiration, version, and type."""
    _, public_pem = _load_rsa_keypair()
    payload       = jwt.decode(
        token
        , public_pem
        , algorithms = ["RS256"]
        , issuer     = settings.JWT_ISSUER
        , audience   = settings.JWT_AUDIENCE
        , options    = {
            "require"      : ["exp", "iat", "sub", "jti", "ver", "iss", "aud", "type"]
            , "verify_exp" : True
            , "verify_iss" : True
            , "verify_aud" : True
        }
    )
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"Expected token type '{expected_type}'.")
    return payload
