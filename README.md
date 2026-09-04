# Unilead

**Unilead is a unified educational platform for competency-based learning, AI coaching, and team project work.**

It is the merge of three previously separate repositories into a single monorepo:

1. **AI Education** — domain engine for the AI Competency Coach (Pydantic v2 + pytest).
2. **Robotics** — a near-identical copy of AI Education (kept for reference; not active).
3. **Platform** — MEC271 Automatic Control learning platform (React/TS frontend + FastAPI backend).

The UI preserved is the **Platform UI** (`edu-platform`, React + TypeScript + Vite + Tailwind). All three backends (Platform's Compass API + AI Education's gateway) are merged into a single FastAPI app under `apps/api`.

---

## Repository Layout

```
unilead/
├── apps/
│   ├── api/                       # Unified FastAPI gateway
│   │   ├── app/
│   │   │   ├── main.py            # Mounts Compass routes + AI Education routes
│   │   │   ├── config.py          # Merged Settings (CORS + LLM)
│   │   │   ├── routers/           # Compass MVP routes (competencies, progress, ...)
│   │   │   ├── schemas/           # Pydantic schemas (Compass MVP)
│   │   │   └── services/          # Compass MVP services (mock data, student state, ...)
│   │   ├── pyproject.toml
│   │   ├── requirements.txt
│   │   ├── .env.example
│   │   └── README.md
│   └── web/                       # React + TypeScript + Vite frontend
│       ├── src/
│       │   ├── App.tsx            # Top-level router
│       │   ├── components/        # UI primitives + domain cards
│       │   ├── pages/             # AICoach, CompetencyProfile, Diagnostic, ...
│       │   ├── data/              # apiClient + mockApi
│       │   ├── state/             # AppContext
│       │   └── types/             # shared TypeScript types
│       ├── package.json
│       ├── vite.config.ts
│       └── tsconfig.json
├── packages/
│   └── contracts/                 # Shared TypeScript types / OpenAPI schemas (placeholder)
├── services/
│   └── ai_education/              # AI Coach domain engine (Pydantic v2 + pytest)
│       ├── ai_education/
│       │   ├── domain/            # competency graph, student model, evidence
│       │   ├── coach/             # orchestrator + 6 modes (hint, learn, ...)
│       │   ├── llm/               # Mock / Ollama / OpenAI providers
│       │   ├── api/               # gateway router (mounted under /api/ai-education)
│       │   ├── mastery/ reasoning/ remediation/ strategy/ transfer/ fluency/ fallbacks/
│       │   ├── robotics/          # telemetry ingestor
│       │   └── simulation/        # PID plant + simulator
│       ├── tests/                 # 284 pytest tests (all passing)
│       └── pyproject.toml
├── docs/                          # Architecture docs + ADRs
├── .github/                       # PR template, issue templates
├── README.md
├── CONTRIBUTING.md
└── LICENSE                        # MIT
```

---

## Quickstart

### Prerequisites

| Tool | Version |
|---|---|
| Python | 3.11+ |
| Node.js | 20+ (tested with v24) |
| npm | 10+ (tested with v11) |

### 1. Backend (FastAPI unified gateway)

```bash
cd apps/api

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate

# Install dependencies (FastAPI + ai_education package)
pip install -e ".[dev]"
pip install -e ../../services/ai_education

# Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at <http://localhost:8000>.
Interactive docs at <http://localhost:8000/docs>.

#### Key endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Liveness probe (returns modules + LLM provider) |
| `GET` | `/api/competencies` | List the 5 MEC271 competencies |
| `GET` | `/api/progress` | Overall + per-competency progress |
| `GET` | `/api/diagnostic/questions` | Diagnostic quiz items |
| `POST` | `/api/coach` | (Compass MVP) coach endpoint |
| `POST` | `/api/simulation` | Run a PID simulation |
| `POST` | `/api/ai-education/coach/chat` | (AI Education) one coach turn |
| `POST` | `/api/ai-education/evidence/telemetry` | Submit a telemetry run |
| `POST` | `/api/ai-education/evidence/simulate` | Built-in PID simulator |
| `GET` | `/api/ai-education/student/{id}/profile` | Learner progress profile |

### 2. Frontend (React/TS)

```bash
cd apps/web
npm install
npm run dev          # Vite dev server on http://localhost:5173
```

The dev server proxies API calls to `http://localhost:8000/api` by default (see `.env`).

### 3. Run tests

```bash
# AI Education engine tests (284 tests)
cd services/ai_education
pytest
```

---

## Configuration

All runtime configuration is read from environment variables (or an `.env` file next to `apps/api/main.py`).

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Server bind host |
| `PORT` | `8000` | Server bind port |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated CORS allow-list |
| `LLM_PROVIDER_TYPE` | `mock` | One of `mock` / `ollama` / `openai` |
| `LLM_MODEL` | *(provider-specific)* | Override the default model name |
| `OPENAI_API_KEY` | *(none)* | Required when `LLM_PROVIDER_TYPE=openai` |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible base URL |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama server URL |
| `STUDENT_ID` | `api-gateway-student` | Default student session |
| `COURSE_ID` | `MEC271` | Course identifier |

For the frontend:

| Variable | Default | Description |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api` | Backend API base URL |

---

## AI Coach LLM Providers

The AI Coach supports three LLM providers — switch between them via the
`LLM_PROVIDER_TYPE` env var. **No code changes required.**

| Provider | `LLM_PROVIDER_TYPE` | Cost | Privacy | Setup |
|---|---|---|---|---|
| **Mock** | `mock` | Free | Offline | None |
| **Ollama** | `ollama` | Free | Local | Install Ollama + pull a model |
| **OpenAI** | `openai` | Paid | Cloud | Get an API key |

### Using Ollama (recommended for local dev)

[Ollama](https://ollama.com) runs an LLM locally on your laptop — no API
key, no network calls to a third party. The default config uses
`llama3.2:3b` (3B parameters, ~2 GB) — a good balance of quality and speed
for the AI Coach's guided-question style.

```bash
# 1. Install Ollama (macOS / Linux / Windows)
#    See https://ollama.com/download
curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull the model (~2 GB, one-time)
ollama pull llama3.2:3b

# 3. Verify Ollama is running and the model is available
ollama list
# Should show: llama3.2:3b   2.0 GB   ...

# 4. Test the model directly
ollama run llama3.2:3b "What is a PID controller in one sentence?"
# Should print a real LLM response.

# 5. Configure the API (the .env already ships with these defaults)
cd apps/api
cp .env.example .env   # if not already done
# .env should contain:
#   LLM_PROVIDER_TYPE=ollama
#   LLM_MODEL=llama3.2:3b
#   OLLAMA_BASE_URL=http://localhost:11434

# 6. Restart uvicorn — the coach now answers via Llama 3.2 3B locally
uvicorn app.main:app --reload
```

**Other Ollama models** you can swap to (just edit `.env` and restart):

| Model | Size | Good for |
|---|---|---|
| `llama3.2:1b` | ~1 GB | Smallest, fastest — for old laptops / CPU-only |
| `llama3.2:3b` | ~2 GB | **Default** — good balance of quality + speed |
| `qwen2.5:3b` | ~2 GB | Strong reasoning, supports JSON output |
| `phi3:mini` | ~2.3 GB | Best quality in this range (3.8B params) |
| `mistral:7b` | ~4 GB | Best overall, needs 8 GB+ RAM |

> **Tip:** you can swap models at any time — just edit `.env`, restart
> `uvicorn`, and the next coach turn uses the new model. No code changes.

### Fallback behaviour

If `LLM_PROVIDER_TYPE=ollama` but Ollama isn't running (or the model is
missing), the orchestrator falls back to a **deterministic script** — the
coach still replies, just with less rich text. No 500 errors. This keeps
the UI usable while you start Ollama.

### Switching providers at runtime

Just change `.env` and restart uvicorn. The coach picks up the new
provider on next request:

```bash
# Today: local Ollama
LLM_PROVIDER_TYPE=ollama

# Tomorrow: OpenAI
LLM_PROVIDER_TYPE=openai
OPENAI_API_KEY=sk-...
```

The coach modes, prompt engineering, anti-cheating guardrails, simulation,
remediation, transfer, and mastery engines all stay identical — only the
text generation layer swaps out.

---

## Architecture (one FastAPI app, two halves)

```
                              ┌─────────────────────────────────┐
                              │     apps/api (FastAPI app)       │
                              │                                 │
   React frontend ──HTTP──▶   │  Compass MVP routes (/api/*)    │
                              │   • /api/competencies            │
                              │   • /api/progress                │
                              │   • /api/coach, /api/diagnostic  │
                              │   • /api/learning, /api/practice  │
                              │   • /api/review, /api/simulation │
                              │   • /api/onboarding              │
                              │                                 │
                              │  AI Education routes             │
                              │  (/api/ai-education/*)           │
                              │   • /coach/chat                  │
                              │   • /evidence/telemetry          │
                              │   • /evidence/simulate           │
                              │   • /student/{id}/profile        │
                              └────────┬────────────────────────┘
                                       │ imports
                                       ▼
                              ┌─────────────────────────────────┐
                              │  services/ai_education          │
                              │   (Pydantic v2 + pytest)         │
                              │   • domain/ (graph, student)     │
                              │   • coach/ (orchestrator+modes)  │
                              │   • llm/ (mock/ollama/openai)    │
                              │   • reasoning/ mastery/ etc.     │
                              └─────────────────────────────────┘
```

The path bootstrap lives in `apps/api/app/config.py` — it inserts `services/ai_education/` onto `sys.path` so the `ai_education` package is importable without being pip-installed. (You can still pip-install it editable for IDE support: `pip install -e services/ai_education`.)

---

## Merging notes (what changed vs. the originals)

- **AI Education** and **Robotics** were nearly identical (same README, same code). Only one copy was kept (`services/ai_education/`), with `Robotics/` removed.
- **Platform/backend/app/** was moved into `apps/api/app/` unchanged (all routers, schemas, services preserved).
- **Platform/edu-platform/** was moved into `apps/web/` unchanged (all components, pages, styles preserved).
- **AI Education apps/api/main.py** was merged into `apps/api/app/main.py` — its `build_provider` and `build_singletons` logic was preserved verbatim, and the AI Education router is now mounted under `/api/ai-education/*` instead of being a standalone app.
- **AI Education apps/api/config.py** (pydantic-settings `Settings`) was merged into `apps/api/app/config.py` alongside the original Platform/backend config.
- **AI Education apps/api/tests/test_server_boot.py** was preserved as `apps/api/tests/test_server_boot.py` (still passes against the merged app).

---

## License

MIT — see [LICENSE](LICENSE).
