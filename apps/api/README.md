# Unilead API (apps/api)

Unified FastAPI gateway for the Unilead platform. Combines:

- The **Compass MVP** API (competencies, progress, diagnostic, learning, practice,
  coach, review, simulation, onboarding) — original Platform backend routes
  mounted under `/api/*`.
- The **AI Education** gateway (coach chat, evidence telemetry, simulate,
  student profile) — mounted under `/api/ai-education/*`, backed by the
  `ai_education` package at `services/ai_education/`.

## Run

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pip install -e ../../services/ai_education
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive docs at <http://localhost:8000/docs>.

## Test

```bash
cd apps/api
pytest
```

## Configuration

See `.env.example` for the full list of environment variables. Defaults are
safe for local development (`mock` LLM provider, port 8000, CORS for
`localhost:5173`).
