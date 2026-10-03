# MonkeyKing — AI Job Discovery & CV Tool

Job discovery across **500+ companies** via 10+ ATS APIs, LLM-powered job-to-CV scoring, learned preferences, per-job tailored CV/cover letter generation, and a **manual** application tracking board.

> Educational / research project. Use responsibly. Many ATS providers and career portals prohibit automated submissions in their Terms of Service. Run this against your own portals and on a low rate, and ensure you have permission before scaling. **Do not commit your real CV, screenshots or `.env`.**

---

## Architecture

The live system is two services orchestrated by `docker-compose.yml`:

```
┌────────────────────────────────────────────────────────────────────┐
│  docker-compose.yml — single entry point                            │
│    ├── backend  (FastAPI, port 8080)  ──► 11 modules, 45 endpoints │
│    └── frontend (Next.js 14, port 8021) ──► 12 routes, 47 components│
└────────────────────────────────────────────────────────────────────┘
```

| Path | Purpose |
| --- | --- |
| `backend/` | FastAPI app — auth, job search, CV parsing/generation, tracking, admin |
| `frontend/` | Next.js App Router dashboard — matches, search, CVs, tracking, settings |
| `docker-compose.yml` | One command to run the full stack (backend + frontend) |
| `legacy/` | Quarantined apply pipeline — reference implementation for future auto-apply port |
| `backend/data/ats_patterns/` | Learned ATS form fingerprints (empty at install; populated at runtime) |

**No `main.py`, `orchestrator.py`, `agents/`, `dashboard/`, or root `config/` — these were removed.**

### Backend (FastAPI — 11 modules, 45 endpoints)

| Module | Responsibility |
| --- | --- |
| `app.py` | FastAPI application, all 45 routes, startup seeding (500+ companies) |
| `auth.py` | JWT auth, Google OAuth, password hashing |
| `companies.py` | 500+ seeded companies with ATS detection mappings |
| `models.py` | SQLAlchemy models (User, Job, Company, UserJob, matches, preferences) |
| `cv_parser.py` | PDF/DOCX → structured profile via LLM |
| `cv_generator.py` | Tailored CV + cover letter (PDF + DOCX) per job |
| `job_scanner.py` | Hybrid scanner: 10+ ATS APIs → Playwright → HTML parse → vision fallback |
| `llm_engine.py` | Multi-provider LLM client (DeepSeek, OpenAI, Anthropic, Google, Groq, Mistral, Ollama) |
| `preference_engine.py` | Learns weights from positive/negative feedback on saved jobs |
| `location_data.py` | Country/city normalization for search filtering |
| `requirements.txt` | Python dependencies |

**Key endpoint groups:**  
`/api/auth/*` (register, login, Google, me) • `/api/cv/*` (upload, parse, list, view, generate, download) • `/api/profile` (GET/PUT) • `/api/jobs/search` (batch 50 companies, background) • `/api/jobs/matches` (scored results) • `/api/jobs/saved` (manual tracking board with status workflow) • `/api/cover-letter/*` • `/api/companies/*` (CRUD + admin import/export) • `/api/settings/llm` (multi-provider keys) • `/api/admin/*` (cleanup, URL health, CSV import/export)

### Frontend (Next.js 14 — App Router)

12 pages under `frontend/src/app/`:
- `(auth)/login`, `(auth)/register`
- `(app)/dashboard`, `(app)/search`, `(app)/matches`, `(app)/tracking`, `(app)/cvs`, `(app)/profile`, `(app)/settings`, `(app)/companies`, `(app)/onboarding`
- Root landing page

47 React components under `frontend/src/components/` covering tracking (status dropdown, kanban), CV upload/generation, job cards, search progress, company tables, settings forms.

---

## What This Ships

- **Job discovery** — scans 500+ company career pages via 10+ ATS APIs (Greenhouse, Lever, Workday, Ashby, SmartRecruiters, Recruitee, Workable, TurboHire, Breezy, HireHive) with Playwright/vision fallbacks.
- **LLM job-to-CV scoring** — every discovered job is scored against your parsed CV; matched/missing skills and a relevance summary are stored.
- **Learned preferences** — saving a job records a positive signal; updating status to *Applied/Interview/Offer* records strong positive; *Rejected* records negative. Weights are recomputed per keyword.
- **Per-job tailored CV & cover letter** — one click generates a PDF + DOCX tailored to the job description using your merged profile.
- **Manual application tracker** — `UserJob` board with statuses: `not_started → started → in_process → document_missing → applied → interview_scheduled → offer_received / rejected`. You set the status; nothing submits automatically.

---

## What This Does Not Do (Yet)

**No automatic apply.** None of the 45 backend routes submits an application. The `ApplicationStatus` enum and `UserJob` board are a manual tracking tool — you pick the status in the frontend (`StatusDropdown.tsx`).

The original apply pipeline (portal account creation, Gmail IMAP verification, CAPTCHA solving, vision-driven form fill, ATS pattern replay) is preserved in [`legacy/`](legacy/README.md) as the reference implementation for a future `/api/jobs/apply` port.

---

## Quickstart

### 1. Configure environment

```bash
git clone https://github.com/AKSHAT34/monkeyking.git
cd monkeyking
cp .env.example .env
# Edit .env with the required keys below
```

### 2. Required environment variables

| Variable | Source | Required | Default | Notes |
| --- | --- | :---: | --- | --- |
| `DEEPSEEK_API_KEY` | `docker-compose.yml`, `backend/llm_engine.py` | ✅ | — | Primary LLM for scoring & generation |
| `MK_SECRET_KEY` | `docker-compose.yml`, `backend/auth.py` | ✅ | — | JWT signing secret (generate a long random string) |
| `GOOGLE_CLIENT_ID` | `docker-compose.yml` (not used by backend), `backend/auth.py` | ✅ | — | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | `docker-compose.yml` (not used by backend), `backend/auth.py` | ✅ | — | Google OAuth client secret |
| `GOOGLE_AI_KEY` | `docker-compose.yml`, `backend/job_scanner.py` | ✅ | — | Google Custom Search / AI key for search fallback |
| `MK_DB_PATH` | `docker-compose.yml`, `backend/models.py` | | `/app/data/monkeyking.db` | SQLite path inside container |
| `OLLAMA_BASE_URL` | `docker-compose.yml`, `backend/llm_engine.py` | | `http://host.docker.internal:11434` | Local Ollama endpoint |
| `OLLAMA_MODEL` | `docker-compose.yml`, `backend/llm_engine.py` | | `qwen2.5:3b` | Ollama model tag |

> **Note:** `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` are read by `backend/auth.py` for Google OAuth but are **not** passed via `docker-compose.yml` — they must be set in the container environment (add them to `docker-compose.yml` or your orchestrator if you use Google login).

### 3. Run with Docker (recommended)

```bash
docker compose up -d --build
```

- Frontend: <http://localhost:8021>
- Backend API: <http://localhost:8080>
- API docs: <http://localhost:8080/docs>

### 4. Run locally (Python)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Frontend (separate terminal):

```bash
cd frontend
npm install
npm run dev
```

- Frontend: <http://localhost:3000>
- Backend API: <http://localhost:8000>

---

## Configuration Files

| File | Purpose |
| --- | --- |
| `.env` | All runtime secrets (see table above) |
| `backend/data/ats_patterns/*.json` | Learned ATS form fingerprints per company (created at runtime; gitignored) |

No `config/cv_data.yaml`, `config/settings.yaml`, or `config/base_cv.pdf` — CV data is uploaded via the UI (`/api/cv/upload`) and stored in the database.

---

## Legacy Apply Pipeline

See [`legacy/README.md`](legacy/README.md). That folder contains the original autonomous apply implementation (account creation, Gmail verification, CAPTCHA, form fill, ATS replay). It is **not built by Docker**, does not run as-is, and is kept solely as the reference for a future apply endpoint.

---

## Disclaimer

This project is **for educational and research purposes only**. Many job portals' Terms of Service prohibit automated submissions. Always check the ToS for each site, respect `robots.txt`, throttle aggressively, and only target portals where you have a legitimate reason to apply. The authors accept no responsibility for misuse.

---

## License

MIT — see [LICENSE](LICENSE).