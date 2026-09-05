"""
Sprint 3 — university identity & multi-tenant foundation tests.

Covers the ADMIN router (RBAC matrix), org tree CRUD, student enrollment,
cross-university isolation, section-scoped instructor views, and the
org-scoped audit trail.

Users are created directly against the DB (there is no self-serve super-admin
signup by design) and authenticated with real JWTs minted via
``create_access_token`` — the same path the app uses.

Run with: python -m pytest tests/test_admin.py -v  (from the apps/api folder)
"""

from __future__ import annotations

import re
import time

import pytest
from fastapi.testclient import TestClient

from app.auth.service import create_access_token, hash_password
from app.db import SessionLocal, crud
from app.db.bootstrap import get_default_section_id
from app.main import app

# --- helpers ----------------------------------------------------------------


def _make_user(
    uniq: str,
    role: str,
    university_id: int | None = None,
    with_student: bool = False,
) -> dict:
    """Create a verified user (+ optionally a student record) directly.

    Returns plain primitives (detached-safe) for building JWTs later.
    """
    db = SessionLocal()
    try:
        user = crud.create_user(
            db,
            email=f"{uniq}@unilead.edu.eg",
            username=uniq,
            name=uniq.title(),
            password_hash=hash_password("Str0ng!Pass#word"),
            role=role,
            university_id=university_id,
            email_verified=True,
        )
        db.commit()
        payload = {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "university_id": user.university_id,
            "token_version": user.token_version,
        }
        if with_student:
            student = crud.create_student(
                db,
                student_id=f"u{user.id}-student",
                user_id=user.id,
                display_name=user.name,
                university_id=university_id,
            )
            db.commit()
            payload["student_id"] = student.student_id
            payload["student_user_id"] = user.id
        return payload
    finally:
        db.close()


def _headers(actor: dict) -> dict[str, str]:
    token = create_access_token(
        subject=str(actor["id"]), token_version=actor.get("token_version", 0)
    )
    return {"Authorization": f"Bearer {token}"}


def _student_headers(student: dict) -> dict[str, str]:
    token = create_access_token(subject=str(student["student_user_id"]))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def org_fixtures(client):
    """Actors needed across the module's tests:
    - ``super``        SUPER_ADMIN (global)
    - ``uni_admin``    UNIVERSITY_ADMIN bound to the seeded UNILEAD org
    - ``instructor``   instructor bound to UNILEAD (no sections yet)
    - ``student_a``    student in UNILEAD, enrolled in the default section
    - ``student_b``    student in UNILEAD, NOT enrolled anywhere
    - ``default_section_id``, ``default_univ_id``
    """
    db = SessionLocal()
    try:
        default_univ = crud.get_university_by_code(db, "UNILEAD")
        assert default_univ is not None, "default org not bootstrapped"
    finally:
        db.close()

    stamp = str(int(time.time()))
    default_univ_id = crud.get_university_by_code(SessionLocal(), "UNILEAD").id
    super_ = _make_user(f"superadmin{stamp}", "super_admin", None)
    uni = _make_user(f"uniadmin{stamp}", "university_admin", default_univ_id)
    instr = _make_user(f"instr{stamp}", "instructor", default_univ_id)
    sa = _make_user(f"studenta{stamp}", "student", default_univ_id, with_student=True)
    sb = _make_user(f"studentb{stamp}", "student", default_univ_id, with_student=True)

    db = SessionLocal()
    try:
        default_section_id = get_default_section_id(db)
        assert default_section_id is not None
        crud.enroll_student_in_section(
            db, student_id=sa["student_id"], section_id=default_section_id
        )
        db.commit()
    finally:
        db.close()

    return {
        "super": super_,
        "uni_admin": uni,
        "instructor": instr,
        "student_a": sa,
        "student_b": sb,
        "default_section_id": default_section_id,
        "default_univ_id": default_univ_id,
    }


# --- RBAC matrix ------------------------------------------------------------


def test_rbac_super_admin_can_list_universities(client, org_fixtures):
    r = client.get("/api/admin/universities", headers=_headers(org_fixtures["super"]))
    assert r.status_code == 200
    codes = {u["code"] for u in r.json()}
    assert "UNILEAD" in codes


def test_rbac_university_admin_cannot_list_all(client, org_fixtures):
    r = client.get("/api/admin/universities", headers=_headers(org_fixtures["uni_admin"]))
    assert r.status_code == 403


def test_rbac_instructor_forbidden(client, org_fixtures):
    r = client.get("/api/admin/org", headers=_headers(org_fixtures["instructor"]))
    assert r.status_code == 403


def test_rbac_student_forbidden(client, org_fixtures):
    r = client.get("/api/admin/org", headers=_student_headers(org_fixtures["student_a"]))
    assert r.status_code == 403


def test_rbac_anonymous_unauthorized(client, org_fixtures):
    r = client.get("/api/admin/org")
    assert r.status_code == 401


# --- SUPER_ADMIN university lifecycle ----------------------------------------


def test_super_create_university_then_duplicate(client, org_fixtures):
    stamp = str(int(time.time()))
    code = f"TST{stamp[-6:]}"
    r = client.post(
        "/api/admin/universities",
        headers=_headers(org_fixtures["super"]),
        json={"code": code, "name": "Test University", "email_domains": ["test.edu.eg"]},
    )
    assert r.status_code == 201
    assert r.json()["code"] == code

    r2 = client.post(
        "/api/admin/universities",
        headers=_headers(org_fixtures["super"]),
        json={"code": code, "name": "Duplicate"},
    )
    assert r2.status_code == 409


def test_super_provision_university_admin_then_duplicate(client, org_fixtures):
    stamp = str(int(time.time()))
    payload = {
        "email": f"ops{stamp}@unilead.edu.eg",
        "username": f"ops{stamp}",
        "name": "Ops Person",
        "password": "Str0ng!Pass#word",
        "university_code": "UNILEAD",
    }
    r = client.post(
        "/api/admin/users/university-admins",
        headers=_headers(org_fixtures["super"]),
        json=payload,
    )
    assert r.status_code == 201

    r2 = client.post(
        "/api/admin/users/university-admins",
        headers=_headers(org_fixtures["super"]),
        json=payload,
    )
    assert r2.status_code == 409


def test_super_deactivate_university(client, org_fixtures):
    stamp = str(int(time.time()))
    code = f"OFF{stamp[-6:]}"
    client.post(
        "/api/admin/universities",
        headers=_headers(org_fixtures["super"]),
        json={"code": code, "name": "Offline Univ"},
    )
    r = client.delete(f"/api/admin/universities/{code}", headers=_headers(org_fixtures["super"]))
    assert r.status_code == 200
    assert "deactivated" in r.json()["message"]


# --- UNIVERSITY_ADMIN org tree ----------------------------------------------


def test_org_tree_default_university(client, org_fixtures):
    r = client.get("/api/admin/org", headers=_headers(org_fixtures["uni_admin"]))
    assert r.status_code == 200
    body = r.json()
    assert body["university_code"] == "UNILEAD"
    eng = next(f for f in body["faculties"] if f["code"] == "ENG")
    mec = next(d for d in eng["departments"] if d["code"] == "MEC")
    mec271 = next(c for c in mec["courses"] if c["code"] == "MEC271")
    assert any(s["code"] == "01" for s in mec271["sections"])


def test_org_tree_write_flow(client, org_fixtures):
    stamp = str(int(time.time()))
    headers = _headers(org_fixtures["uni_admin"])

    r = client.post(
        "/api/admin/org/faculties",
        headers=headers,
        json={"code": f"F{stamp[-4:]}", "name": "New Faculty"},
    )
    assert r.status_code == 201
    faculty_id = r.json()["id"]

    r = client.post(
        "/api/admin/org/departments",
        headers=headers,
        json={"faculty_id": faculty_id, "code": "CS", "name": "Computer Science"},
    )
    assert r.status_code == 201
    dept_id = r.json()["id"]

    r = client.post(
        "/api/admin/org/courses",
        headers=headers,
        json={"department_id": dept_id, "code": "CS101", "title": "Intro to CS", "credits": 3},
    )
    assert r.status_code == 201
    course_id = r.json()["id"]

    r = client.post(
        "/api/admin/org/sections",
        headers=headers,
        json={"course_id": course_id, "term": "2026-S1", "code": "02"},
    )
    assert r.status_code == 201
    assert r.json()["term"] == "2026-S1"


def test_provision_instructor(client, org_fixtures):
    stamp = str(int(time.time()))
    r = client.post(
        "/api/admin/org/instructors",
        headers=_headers(org_fixtures["uni_admin"]),
        json={
            "email": f"teach{stamp}@unilead.edu.eg",
            "username": f"teach{stamp}",
            "name": "New Teacher",
            "password": "Str0ng!Pass#word",
        },
    )
    assert r.status_code == 201


def test_provision_student_and_enroll(client, org_fixtures):
    stamp = str(int(time.time()))
    r = client.post(
        "/api/admin/org/students",
        headers=_headers(org_fixtures["uni_admin"]),
        json={
            "email": f"learner{stamp}@unilead.edu.eg",
            "username": f"learner{stamp}",
            "name": "New Learner",
            "password": "Str0ng!Pass#word",
        },
    )
    assert r.status_code == 201
    m = re.search(r"id '([^']+)'", r.json()["message"])
    assert m, f"unexpected message: {r.json()['message']}"
    student_id = m.group(1)

    r = client.post(
        "/api/admin/org/enroll",
        headers=_headers(org_fixtures["uni_admin"]),
        json={"student_id": student_id, "section_id": org_fixtures["default_section_id"]},
    )
    assert r.status_code == 201

    # Idempotent re-enroll.
    r2 = client.post(
        "/api/admin/org/enroll",
        headers=_headers(org_fixtures["uni_admin"]),
        json={"student_id": student_id, "section_id": org_fixtures["default_section_id"]},
    )
    assert r2.status_code == 201

    # Roster includes the student.
    r3 = client.get(
        f"/api/admin/org/sections/{org_fixtures['default_section_id']}/students",
        headers=_headers(org_fixtures["uni_admin"]),
    )
    assert r3.status_code == 200
    assert any(s["student_id"] == student_id for s in r3.json())

    # Unenroll, then a second unenroll 404s.
    r4 = client.delete(
        f"/api/admin/org/sections/{org_fixtures['default_section_id']}/students/{student_id}",
        headers=_headers(org_fixtures["uni_admin"]),
    )
    assert r4.status_code == 200
    r5 = client.delete(
        f"/api/admin/org/sections/{org_fixtures['default_section_id']}/students/{student_id}",
        headers=_headers(org_fixtures["uni_admin"]),
    )
    assert r5.status_code == 404


# --- cross-university isolation ----------------------------------------------


def test_cross_university_department_creation_blocked(client, org_fixtures):
    stamp = str(int(time.time()))
    code = f"ISO{stamp[-5:]}"

    r = client.post(
        "/api/admin/universities",
        headers=_headers(org_fixtures["super"]),
        json={"code": code, "name": "Isolated University"},
    )
    assert r.status_code == 201

    # Provision an admin for the isolated university, then create a faculty there.
    r = client.post(
        "/api/admin/users/university-admins",
        headers=_headers(org_fixtures["super"]),
        json={
            "email": f"isoop{stamp}@iso.edu.eg",
            "username": f"isoop{stamp}",
            "name": "Iso Ops",
            "password": "Str0ng!Pass#word",
            "university_code": code,
        },
    )
    assert r.status_code == 201

    db = SessionLocal()
    try:
        iso_admin = crud.get_user_by_email(db, f"isoop{stamp}@iso.edu.eg")
        assert iso_admin is not None
        iso_admin_headers = {
            "Authorization": f"Bearer {create_access_token(subject=str(iso_admin.id), token_version=iso_admin.token_version)}"
        }
    finally:
        db.close()

    r = client.post(
        "/api/admin/org/faculties",
        headers=iso_admin_headers,
        json={"code": f"IF{stamp[-4:]}", "name": "Iso Faculty"},
    )
    assert r.status_code == 201
    iso_faculty_id = r.json()["id"]

    # The UNILEAD admin must NOT be able to create a department under it.
    r = client.post(
        "/api/admin/org/departments",
        headers=_headers(org_fixtures["uni_admin"]),
        json={"faculty_id": iso_faculty_id, "code": "X", "name": "Intruder Dept"},
    )
    assert r.status_code == 403


# --- instructor section scoping ---------------------------------------------


def test_instructor_sees_only_own_sections(client, org_fixtures):
    stamp = str(int(time.time()))
    headers = _headers(org_fixtures["uni_admin"])
    instructor = org_fixtures["instructor"]

    # Fresh instructor (no sections) sees an empty roster.
    r = client.get("/api/instructor/students", headers=_headers(instructor))
    assert r.status_code == 200
    assert r.json() == []

    # Create a section taught by this instructor.
    r = client.post(
        "/api/admin/org/faculties",
        headers=headers,
        json={"code": f"SF{stamp[-4:]}", "name": "Scoped Faculty"},
    )
    faculty_id = r.json()["id"]
    r = client.post(
        "/api/admin/org/departments",
        headers=headers,
        json={"faculty_id": faculty_id, "code": f"SD{stamp[-4:]}", "name": "Scoped Dept"},
    )
    dept_id = r.json()["id"]
    r = client.post(
        "/api/admin/org/courses",
        headers=headers,
        json={"department_id": dept_id, "code": "SC101", "title": "Scoped Course"},
    )
    course_id = r.json()["id"]
    r = client.post(
        "/api/admin/org/sections",
        headers=headers,
        json={
            "course_id": course_id,
            "term": "2026-S1",
            "code": "03",
            "instructor_user_id": instructor["id"],
        },
    )
    assert r.status_code == 201
    section_id = r.json()["id"]

    # Enroll student_a there; student_b remains outside.
    db = SessionLocal()
    try:
        crud.enroll_student_in_section(
            db, student_id=org_fixtures["student_a"]["student_id"], section_id=section_id
        )
        db.commit()
    finally:
        db.close()

    roster = client.get("/api/instructor/students", headers=_headers(instructor)).json()
    ids = {s["student_id"] for s in roster}
    assert org_fixtures["student_a"]["student_id"] in ids
    assert org_fixtures["student_b"]["student_id"] not in ids

    detail = client.get(
        f"/api/instructor/students/{org_fixtures['student_a']['student_id']}",
        headers=_headers(instructor),
    )
    assert detail.status_code == 200

    outside = client.get(
        f"/api/instructor/students/{org_fixtures['student_b']['student_id']}",
        headers=_headers(instructor),
    )
    assert outside.status_code == 404

    timeline = client.get(
        f"/api/evidence/{org_fixtures['student_b']['student_id']}/timeline",
        headers=_headers(instructor),
    )
    assert timeline.status_code == 404


# --- audit scoping -----------------------------------------------------------


def test_audit_scoped_to_own_university(client, org_fixtures):
    tension = org_fixtures["uni_admin"]["university_id"]
    assert tension is not None

    r = client.get("/api/admin/audit", headers=_headers(org_fixtures["uni_admin"]))
    assert r.status_code == 200
    entries = r.json()
    assert isinstance(entries, list)
    for e in entries:
        assert e["university_id"] == tension

    r = client.get("/api/admin/audit", headers=_headers(org_fixtures["super"]))
    assert r.status_code == 200
    assert len(r.json()) >= len(entries)
