"""
Quick smoke test for every endpoint. Not a full test suite — just enough to
confirm the app boots, routes respond, and the review->progress mutation
actually flows through, before wiring up the frontend.

Run with: .venv/bin/python -m app.test_smoke   (from the backend/ folder)
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
    r = client.get("/")
    check("GET / health check", r.status_code == 200 and r.json()["status"] == "ok")

    r = client.post(
        "/api/onboarding",
        json={
            "learning_challenge": "a",
            "preferred_method": "b",
            "obstacle": "c",
            "goal": "d",
        },
    )
    check("POST /api/onboarding", r.status_code == 200 and r.json()["success"] is True)

    r = client.get("/api/diagnostic/questions")
    questions = r.json()
    check("GET /api/diagnostic/questions", r.status_code == 200 and len(questions) == 5)

    r = client.post(
        "/api/diagnostic",
        json={"answers": [{"question_id": q["id"], "option_id": "a"} for q in questions]},
    )
    check("POST /api/diagnostic", r.status_code == 200 and len(r.json()) == 5)

    r = client.get("/api/learning/pid-reasoning")
    check("GET /api/learning/{id}", r.status_code == 200 and len(r.json()) == 3)

    r = client.get("/api/practice/pid-reasoning")
    check("GET /api/practice/{id}", r.status_code == 200 and r.json()["id"] == "pid-001")

    r = client.post("/api/coach", json={"turn_index": 0})
    coach_body = r.json()
    check(
        "POST /api/coach (turn 0)",
        r.status_code == 200 and coach_body["finished"] is False and coach_body["total_turns"] == 5,
    )

    r = client.post("/api/coach", json={"turn_index": 4})
    check("POST /api/coach (final turn)", r.status_code == 200 and r.json()["finished"] is True)

    r = client.post("/api/simulation", json={"task_id": "pid-001"})
    sim = r.json()
    check(
        "POST /api/simulation",
        r.status_code == 200 and sim["stable"] is True and sim["overshoot"] == 8.4,
    )

    r = client.get("/api/competencies")
    comps = r.json()
    check("GET /api/competencies", r.status_code == 200 and len(comps) == 5)
    reasoning_before = next(c for c in comps if c["id"] == "pid-reasoning")
    check("pid-reasoning starts DEVELOPING", reasoning_before["status"] == "developing")

    r = client.get("/api/progress")
    progress_before = r.json()
    check(
        "GET /api/progress",
        r.status_code == 200 and progress_before["recommended_next_activity"] == "PID Reasoning Practice",
    )

    # Review: view (no mutation)
    r = client.post("/api/review", json={"competency_id": "pid-reasoning", "finalize": False})
    review_view = r.json()
    check(
        "POST /api/review (view)",
        r.status_code == 200 and review_view["progress"] == reasoning_before["progress"],
    )

    # Review: finalize (should bump progress + overall)
    r = client.post("/api/review", json={"competency_id": "pid-reasoning", "finalize": True})
    review_final = r.json()
    check(
        "POST /api/review (finalize) bumps competency progress",
        review_final["progress"] > reasoning_before["progress"],
    )
    check(
        "POST /api/review (finalize) bumps overall progress",
        review_final["overall_progress"] > progress_before["overall_progress"],
    )
    check("status stays DEVELOPING (capped below DEMONSTRATED)", review_final["status"] == "developing")

    # Confirm the mutation is now visible via GET /api/competencies too
    r = client.get("/api/competencies")
    reasoning_after = next(c for c in r.json() if c["id"] == "pid-reasoning")
    check(
        "GET /api/competencies reflects the review mutation",
        reasoning_after["progress"] == review_final["progress"],
    )

    print("\nAll smoke tests passed.")


if __name__ == "__main__":
    run()
