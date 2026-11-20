from dataclasses import dataclass, field
from typing      import Any, Optional
from uuid        import UUID


@dataclass
class AuthContext:
    """Resolved authentication context attached to request.state.auth_context by AuthMiddleware."""

    system_code     : str
    auth_type       : str
    channel         : str            = "API"
    user_id         : Optional[UUID] = None
    username        : Optional[str]  = None
    role_code       : Optional[str]  = None
    department_code : Optional[str]  = None
    user            : Any            = field(default = None, repr = False)
    system          : Any            = field(default = None, repr = False)
    credential      : Any            = field(default = None, repr = False)
