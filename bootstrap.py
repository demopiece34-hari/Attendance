from __future__ import annotations

import os
import sys
from typing import Optional

from auth import login_user
from google_sheets import (
    create_default_settings_if_missing,
    ensure_structure,
    upsert_staff,
    upsert_student,
)
from utils import hash_password, timestamp_str


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _maybe_seed_staff() -> None:
    staff_id = _env("SEED_STAFF_ID")
    name = _env("SEED_STAFF_NAME")
    department = _env("SEED_STAFF_DEPARTMENT")
    username = _env("SEED_STAFF_USERNAME")
    password = _env("SEED_STAFF_PASSWORD")
    role = _env("SEED_STAFF_ROLE", "admin")

    if not all([staff_id, name, department, username, password]):
        return

    upsert_staff(
        {
            "staff_id": staff_id,
            "name": name,
            "department": department,
            "username": username,
            "password_hash": hash_password(password),
            "role": role,
            "active": "TRUE",
            "created_at": timestamp_str(),
            "updated_at": timestamp_str(),
        }
    )
    print(f"Seeded staff: {username}")


def _maybe_seed_student() -> None:
    student_id = _env("SEED_STUDENT_ID")
    name = _env("SEED_STUDENT_NAME")
    department = _env("SEED_STUDENT_DEPARTMENT")
    username = _env("SEED_STUDENT_USERNAME")
    password = _env("SEED_STUDENT_PASSWORD")
    allowed_lat = _env("SEED_STUDENT_ALLOWED_LAT", "13.0827")
    allowed_lng = _env("SEED_STUDENT_ALLOWED_LNG", "80.2707")
    allowed_radius = _env("SEED_STUDENT_ALLOWED_RADIUS", "100")

    if not all([student_id, name, department, username, password]):
        return

    upsert_student(
        {
            "student_id": student_id,
            "name": name,
            "department": department,
            "username": username,
            "password_hash": hash_password(password),
            "face_embedding": "",
            "face_reference_updated_at": "",
            "active": "TRUE",
            "allowed_latitude": allowed_lat,
            "allowed_longitude": allowed_lng,
            "allowed_radius_m": allowed_radius,
            "created_at": timestamp_str(),
            "updated_at": timestamp_str(),
        }
    )
    print(f"Seeded student: {username}")


def main() -> int:
    try:
        ensure_structure()
        create_default_settings_if_missing()
        _maybe_seed_staff()
        _maybe_seed_student()
        print("Bootstrap completed.")
        return 0
    except Exception as exc:
        print(f"Bootstrap failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
