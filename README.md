# 🐵 MonkeyKing — AI Job Application Bot

Agentic job application bot that scans company career pages, tailors a CV per job for ATS, creates accounts on portals, validates via Gmail, fills application forms with computer vision, and applies to hundreds of jobs automatically.

> Educational / research project. Use responsibly. Many ATS providers and career portals prohibit automated submissions in their Terms of Service. Run this against your own portals and on a low rate, and ensure you have permission before scaling. **Do not commit your real CV, screenshots or `.env`.**

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  Orchestrator (FastAPI backend)                                       │
└─────────────────────────────┬────────────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Agents                                                               │
│   Job Scanner   →  Scrapes career pages via Browser MCP / Playwright  │
│   Job Matcher   →  Scores roles against your CV using LLM (DeepSeek)  │
│   CV Tailor     →  Rewrites CV per job for ATS optimisation           │
│   Account Maker →  Creates accounts on company portals                │
│   Email Agent   →  IMAP — pulls verification links from Gmail         │
│   Apply Agent   →  Vision-driven form filler + submitter              │
│   ATS Learner   →  Stores form patterns per company for replay        │
└─────────────────────────────┬────────────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Storage + UI                                                         │
│   SQLite (jobs, runs, applications)                                   │
│   Local FS (tailored CVs, screenshots)                                │
│   Next.js dashboard on port 3000                                      │
└──────────────────────────────────────────────────────────────────────┘
```

Top-level layout:

| Path | Purpose |
| --- | --- |
| `main.py` | Entry point — starts the FastAPI backend |
| `orchestrator.py` | Agent orchestration loop |
| `agents/` | Individual agent modules (scanner, matcher, tailor, apply, etc.) |
| `backend/` | FastAPI app, database models, AI browser, CV parser/generator |
| `dashboard/` | Lightweight HTML dashboard served by FastAPI |
| `frontend/` | Next.js React dashboard |
| `db/` | SQLAlchemy models |
| `config/` | `cv_data.yaml` (your CV as YAML), `settings.yaml`, ATS profiles |
| `data/ats_patterns/` | Learned ATS form patterns per company (Greenhouse, Workday, etc.) |

---

## Quickstart

### 1. Configure

```bash
git clone https://github.com/AKSHAT34/monkeyking.git
cd monkeyking
cp .env.example .env
# Edit .env — set DEEPSEEK_API_KEY, MK_SECRET_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
```

Then put a CV PDF in `config/base_cv.pdf` (not committed) and edit `config/cv_data.yaml` and `config/settings.yaml` with your real details.

### 2. Run with Docker

```bash
export DEEPSEEK_API_KEY=...
export MK_SECRET_KEY=...
export GOOGLE_AI_KEY=...
docker compose up -d --build
```

Frontend: <http://localhost:8021>  
Backend API: <http://localhost:8080>

### 3. Run locally with Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Dashboard: <http://localhost:8501>

---

## Configuration

| File | What goes in it |
| --- | --- |
| `.env` | DeepSeek key, Google AI key, Gmail app password, Google OAuth client |
| `config/cv_data.yaml` | Structured CV used by the CV Tailor (replace placeholders with your data) |
| `config/settings.yaml` | Job preferences, target companies, locations, match thresholds |
| `config/base_cv.pdf` | Your raw CV PDF (used as a fallback by the parser; gitignored) |
| `data/ats_patterns/*.json` | Pre-learned form fingerprints per company (Greenhouse, Workday, Lever, etc.) |

---

## Disclaimer

This project is **for educational and research purposes only**. Many job portals' Terms of Service prohibit automated submissions. Always check the ToS for each site, respect `robots.txt`, throttle aggressively, and only target portals where you have a legitimate reason to apply. The authors accept no responsibility for misuse.

## License

MIT — see [LICENSE](LICENSE).
