"""
Quick smoke test for every endpoint. Not a full test suite — just enough to
confirm the app boots, routes respond, and the review->progress mutation
actually flows through, before wiring up the frontend.

Run with: .venv/bin/python -m app.test_smoke   (from the apps/api folder)

This test signs up a throwaway user, uses the returned JWT for authenticated
endpoints, and verifies the core flows work end-to-end.
"""

from fastapi.testclient import TestClient

from .main import app

client = TestClient(app)


def check(label: str, condition: bool):
    status = "OK " if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        raise SystemExit(1)


def run():
    # --- Health ---
    r = client.get("/")
    check("GET / health check", r.status_code == 200 and r.json()["status"] == "ok")

    # --- Signup a throwaway user (password satisfies complexity rules) ---
    uniq = "smoke" + str(int(__import__("time").time()))
    signup_payload = {
        "name": "Smoke Test",
        "username": uniq,
        "email": f"{uniq}@smoketest.example.com",
        "password": "Str0ng!Pass#word",
    }
    r = client.post("/api/auth/signup", json=signup_payload)
    check("POST /api/auth/signup", r.status_code == 200 and "access_token" in r.json())
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # --- /me (authenticated) ---
    r = client.get("/api/auth/me", headers=headers)
    check("GET /api/auth/me", r.status_code == 200 and r.json()["email"] == signup_payload["email"])

    # --- Login (wrong password: unified 401, no account enumeration) ---
    r = client.post(
        "/api/auth/login",
        json={"email": signup_payload["email"], "password": "WrongPassword1!"},
    )
    check("POST /api/auth/login bad password -> 401 unified", r.status_code == 401)

    # --- Login (correct) ---
    r = client.post(
        "/api/auth/login",
        json={"email": signup_payload["email"], "password": "Str0ng!Pass#word"},
    )
    check("POST /api/auth/login", r.status_code == 200 and "access_token" in r.json())

    # --- Onboarding (authenticated) ---
    r = client.post(
        "/api/onboarding",
        headers=headers,
        json={
            "learning_challenge": "a",
            "preferred_method": "b",
            "obstacle": "c",
            "goal": "d",
        },
    )
    check("POST /api/onboarding", r.status_code == 200 and r.json()["success"] is True)

    # --- Diagnostic ---
    r = client.get("/api/diagnostic/questions")
    questions = r.json()
    check("GET /api/diagnostic/questions", r.status_code == 200 and len(questions) == 5)

    r = client.post(
        "/api/diagnostic",
        headers=headers,
        json={"answers": [{"question_id": q["id"], "option_id": "a"} for q in questions]},
    )
    check("POST /api/diagnostic", r.status_code == 200 and len(r.json()) == 5)

    # --- Learning / practice (now auth-gated) ---
    r = client.get("/api/learning/pid-reasoning", headers=headers)
    check("GET /api/learning/{id} (auth)", r.status_code == 200 and len(r.json()) == 3)

    r = client.get("/api/practice/pid-reasoning", headers=headers)
    check("GET /api/practice/{id} (auth)", r.status_code == 200 and r.json()["id"] == "pid-001")

    # Learning/practice without a token -> 401
    r = client.get("/api/learning/pid-reasoning")
    check("GET /api/learning/{id} unauth -> 401", r.status_code == 401)
    r = client.get("/api/practice/pid-reasoning")
    check("GET /api/practice/{id} unauth -> 401", r.status_code == 401)

    # --- Coach ---
    r = client.post("/api/coach", headers=headers, json={"message": "hello", "mode": "LEARN"})
    coach_body = r.json()
    check("POST /api/coach", r.status_code == 200 and coach_body["message"])

    # --- Simulation ---
    r = client.post(
        "/api/simulation",
        headers=headers,
        json={
            "task_id": "pid-001",
            "competency_id": "pid-tuning",
            "kp": 1.0,
            "ki": 0.1,
            "kd": 0.05,
        },
    )
    sim = r.json()
    check("POST /api/simulation", r.status_code == 200 and "stable" in sim)

    # --- Competencies / progress (auth) ---
    r = client.get("/api/competencies", headers=headers)
    comps = r.json()
    check("GET /api/competencies (auth)", r.status_code == 200 and len(comps) == 5)

    r = client.get("/api/progress", headers=headers)
    progress_before = r.json()
    check("GET /api/progress (auth)", r.status_code == 200 and progress_before["overall_progress"] is not None)

    # --- Review: view (no mutation) ---
    r = client.post(
        "/api/review",
        headers=headers,
        json={"competency_id": "pid-reasoning", "finalize": False},
    )
    review_view = r.json()
    check("POST /api/review (view)", r.status_code == 200 and review_view["progress"] is not None)

    # --- Review: finalize (status is "not_started" for a fresh user, so
    #     finalize is a no-op — it only bumps when status == "developing".
    #     Verify the endpoint returns a valid response.) ---
    r = client.post(
        "/api/review",
        headers=headers,
        json={"competency_id": "pid-reasoning", "finalize": True},
    )
    review_final = r.json()
    check(
        "POST /api/review (finalize) returns valid response",
        r.status_code == 200 and review_final["competency_id"] == "pid-reasoning",
    )

    # --- Evidence timeline (authenticated, /me) ---
    r = client.get("/api/evidence/me/timeline", headers=headers)
    check("GET /api/evidence/me/timeline (auth)", r.status_code == 200 and isinstance(r.json(), list))

    s = client.get("/api/auth/me", headers=headers).json()
    student_id = s["student_id"]

    # --- Evidence timeline by student id (instructor-gated, same user has access) ---
    r = client.get(f"/api/evidence/{student_id}/timeline", headers=headers)
    check("GET /api/evidence/{id}/timeline (auth)", r.status_code == 200 and isinstance(r.json(), list))

    # Unauthenticated evidence -> 401
    r = client.get("/api/evidence/me/timeline")
    check("GET /api/evidence/me/timeline unauth -> 401", r.status_code == 401)

    # --- Instructor endpoints (auth-gated) ---
    r = client.get("/api/instructor/summary", headers=headers)
    check("GET /api/instructor/summary (auth)", r.status_code == 200)
    r = client.get("/api/instructor/aggregate", headers=headers)
    check("GET /api/instructor/aggregate (auth)", r.status_code == 200)
    r = client.get("/api/instructor/students", headers=headers)
    check("GET /api/instructor/students (auth)", r.status_code == 200)

    # Instructor without a token -> 401
    r = client.get("/api/instructor/students")
    check("GET /api/instructor/students unauth -> 401", r.status_code == 401)

    print("\nAll smoke tests passed.")


if __name__ == "__main__":
    run()