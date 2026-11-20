"""
scripts/create_admin.py
=======================
Create (or reset password for) an ADMIN user in data."user".

Usage:
  python scripts/create_admin.py admin
  python scripts/create_admin.py admin --password YourStrongPassword --full-name "System Admin"
"""

import argparse
import getpass
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path     = [p for p in sys.path if "khmer" not in p.lower()]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.constants     import utc_now_naive
from app.core.db            import getStaticSession
from app.core.enum          import ROLE_CODE_ENUM, STATUS_CODE_ENUM
from app.core.security      import hash_password
from app.models.data_model  import USER_MODEL


def main() -> None:
    parser = argparse.ArgumentParser(description = "Create or reset an ADMIN user account.")
    parser.add_argument("username", type = str, help = "Admin username (lowercase)")
    parser.add_argument("--password", type = str, default = None, help = "Password (min 8 chars; prompts if omitted)")
    parser.add_argument("--full-name", dest = "full_name", type = str, default = "Administrator", help = "Full name")
    parser.add_argument("--email", type = str, default = None, help = "Optional email")
    parser.add_argument("--department", type = str, default = "SURGICAL_ICU", help = "Department code")
    args = parser.parse_args()

    username = args.username.strip().lower()
    password = args.password
    if not password:
        password = getpass.getpass(f"Password for '{username}' (min 8 chars): ")
        confirm  = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Error: Passwords do not match.")
            sys.exit(1)

    if len(password) < 8:
        print("Error: Password must be at least 8 characters.")
        sys.exit(1)

    session = getStaticSession()
    try:
        user = session.query(USER_MODEL).filter(USER_MODEL.username == username).first()
        if user:
            user.password_hash    = hash_password(password)
            user.role_code        = ROLE_CODE_ENUM.ADMIN.value
            user.is_active        = True
            user.status_code      = STATUS_CODE_ENUM.ACTIVE.value
            user.deleted_datetime = None
            user.token_version    = (user.token_version or 0) + 1
            user.updated_by       = "CLI"
            user.updated_datetime = utc_now_naive()
            session.commit()
            print(f"Updated existing ADMIN user '{username}' (id={user.id}).")
        else:
            user = USER_MODEL(
                username          = username
                , email           = args.email
                , full_name       = args.full_name
                , password_hash   = hash_password(password)
                , role_code       = ROLE_CODE_ENUM.ADMIN.value
                , department_code = args.department
                , is_active       = True
                , token_version   = 0
                , status_code     = STATUS_CODE_ENUM.ACTIVE.value
                , created_by      = "CLI"
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            print(f"Created ADMIN user '{username}' (id={user.id}).")
    finally:
        session.close()


if __name__ == "__main__":
    main()
