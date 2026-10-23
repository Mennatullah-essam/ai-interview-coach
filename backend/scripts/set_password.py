"""Set a password for an existing account (for example one created before
Milestone 3, which has no password and therefore cannot log in).

Usage (from the backend folder, virtual environment active):
    python scripts/set_password.py someone@example.com
The password is asked for interactively and is never echoed or logged.
"""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.security import hash_password  # noqa: E402
from app.db.session import get_session_factory  # noqa: E402
from app.services.auth_service import find_user_by_email, revoke_all_sessions  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    email = sys.argv[1]
    with get_session_factory()() as db:
        user = find_user_by_email(db, email)
        if user is None:
            print("No account with that email.")
            return 1
        password = getpass.getpass("New password (min 8 characters): ")
        if len(password) < 8 or password != getpass.getpass("Repeat password: "):
            print("Passwords must match and be at least 8 characters.")
            return 1
        user.password_hash = hash_password(password)
        revoke_all_sessions(db, user.id)
        db.commit()
    print("Password updated; existing sessions were signed out.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
