"""Provision an administrator account directly against the app database.

Useful for the very first bootstrap (there is no self-serve super-admin
signup — by design). Runs on the same DATABASE_URL the app uses.

Usage::

    EMAIL=ops@unilead.edu.eg USERNAME=chief NAME="Chief Ops" \
    PASSWORD='s3cret!' ROLE=super_admin \
        python -m scripts.create_admin

    ROLE=university_admin UNIVERSITY_CODE=UNILEAD \
        ... python -m scripts.create_admin

Roles: ``super_admin`` (global) or ``university_admin`` (requires
UNIVERSITY_CODE; bound to that tenant).

Provisioned admins are created ``email_verified=True`` — the operator
vouches for them, so no email round-trip is needed to log in.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.service import hash_password  # noqa: E402
from app.db import crud  # noqa: E402
from app.db.database import SessionLocal, create_all_tables  # noqa: E402

ALLOWED_ROLES = {"super_admin", "university_admin"}


def main() -> int:
    email = os.environ.get("EMAIL", "").strip().lower()
    username = os.environ.get("USERNAME", "").strip().lower()
    name = os.environ.get("NAME", "").strip()
    password = os.environ.get("PASSWORD", "")
    role = os.environ.get("ROLE", "").strip().lower()
    university_code = os.environ.get("UNIVERSITY_CODE", "").strip().upper()

    if not all([email, username, name, password]):
        print("EMAIL, USERNAME, NAME, and PASSWORD env vars are required.")
        return 2
    if role not in ALLOWED_ROLES:
        print(f"ROLE must be one of: {', '.join(sorted(ALLOWED_ROLES))}.")
        return 2
    if len(password) < 8:
        print("PASSWORD must be at least 8 characters.")
        return 2

    # Ensure tables exist + default org bootstrap already ran.
    create_all_tables()

    with SessionLocal() as db:
        if crud.get_user_by_email(db, email) is not None or crud.get_user_by_username(db, username):
            print(f"An account with email '{email}' or username '{username}' already exists.")
            return 1

        university_id = None
        if role == "university_admin":
            if not university_code:
                print("UNIVERSITY_CODE is required when ROLE=university_admin.")
                return 2
            university = crud.get_university_by_code(db, university_code)
            if university is None:
                print(
                    f"University '{university_code}' not found. Create it first via the super-admin API."
                )
                return 1
            university_id = university.id

        user = crud.create_user(
            db,
            email=email,
            username=username,
            name=name,
            password_hash=hash_password(password),
            role=role,
            university_id=university_id,
            email_verified=True,
        )
        db.commit()

    scope = university_code if role == "university_admin" else "(global)"
    print(f"Created {role} '{username}' [{scope}] (user_id={user.id}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
