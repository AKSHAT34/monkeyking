# MonkeyKing Architecture Review

**Repo**: https://github.com/AKSHAT34/monkeyking  
**Review Date**: 2026-10-03  
**Scope**: System architecture, cohesion, structural integrity — not line-level bugs

---

## Executive Summary

**One-line verdict**: The legacy CLI stack is dead code; the deployed FastAPI/Next.js stack works but is fragile due to monolithic modules, configuration chaos, and an absent agent abstraction layer.

---

## Findings

### 1. Two-Stack Split — Blocker

**ID**: `two-stack-split`  
**Severity**: `blocker`  
**Where**: `docker-compose.yml:5-31`, `main.py:1-149`, `backend/app.py:1`  
**What is wrong**: The repo contains two entirely separate application stacks pushed as a single snapshot. `docker-compose.yml` builds only `backend/` (FastAPI) and `frontend/` (Next.js). The legacy stack — `main.py`, `orchestrator.py`, `agents/` (13 modules), `db/`, `config/` — is not built, not deployed, and not wired into any CI/CD. Three modules are duplicated across stacks with different APIs: `llm_engine.py` (78 vs 221 lines), `job_scanner.py` (128 vs 1361 lines), `cv_generator.py` (297 vs 328 lines).  
**Impact**: Confusion about which code runs in production. The legacy stack is unmaintained dead code that still clutters the repo and misleads contributors.  
**Fix**: Archive the legacy stack (`main.py`, `orchestrator.py`, `agents/`, `db/`, `config/`, root `requirements.txt`) into a `legacy/` subdirectory or delete it. Keep only the deployed stack. **Size**: M (cleanup + doc update).

---

### 2. Dual SQLAlchemy Models — Blocker

**ID**: `dual-sqlalchemy-models`  
**Severity**: `blocker`  
**Where**: `db/models.py:1-106`, `backend/models.py:1-265`  
**What is wrong**: Two completely different ORM model sets exist. Legacy (`db/models.py`): 5 tables (`Job`, `TailoredCV`, `Application`, `Account`, `RunLog`) with **no `user_id` on any table**. Deployed (`backend/models.py`): 15 tables (`User`, `UserProfile`, `UploadedCV`, `Job`, `Company`, `UserJob`, `UserJobMatch`, `SearchRun`, `UserLLMSettings`, `ScanHistory`, `VisionNavCache`, `UserPreferenceHistory`, `UserLearnedPreferences`) — **all user-scoped with `user_id` FKs**. They point at different SQLite files: legacy uses `data/monkeyking.db` (relative to root), deployed uses `MK_DB_PATH` env var (default `backend/data/monkeyking.db`).  
**Impact**: If both stacks ran simultaneously, they would create separate databases with incompatible schemas. The legacy models cannot support multi-user at all.  
**Fix**: Delete `db/models.py` and `db/` entirely. The deployed models are the correct, multi-user-ready schema. **Size**: XS (deletion only).

---

### 3. Multi-User Data Leaks (4× Blocker)

**ID**: `legacy-missing-user-id-jobs`  
**Severity**: `blocker`  
**Where**: `db/models.py:13-35` (`Job` table)  
**What is wrong**: `Job` table has no `user_id` column. All jobs are global.  
**Impact**: Any user sees all jobs from all users.  
**Fix**: N/A — legacy stack is dead (see #1).

**ID**: `legacy-missing-user-id-tailored-cvs`  
**Severity**: `blocker`  
**Where**: `db/models.py:37-49` (`TailoredCV` table)  
**What is wrong**: `TailoredCV` links only to `Job` via `job_id`, no `user_id`.  
**Impact**: Users can access each other's tailored CVs by guessing job IDs.  
**Fix**: N/A — legacy stack is dead.

**ID**: `legacy-missing-user-id-applications`  
**Severity**: `blocker`  
**Where**: `db/models.py:51-67` (`Application` table)  
**What is wrong**: `Application` has `account_id` but no `user_id`. `Account` table also lacks `user_id`.  
**Impact**: Application records leak across users.  
**Fix**: N/A — legacy stack is dead.

**ID**: `legacy-missing-user-id-runlogs`  
**Severity**: `blocker`  
**Where**: `db/models.py:83-97` (`RunLog` table)  
**What is wrong**: `RunLog` has no `user_id`.  
**Impact**: Run history leaks across users.  
**Fix**: N/A — legacy stack is dead.

> **Note**: The deployed stack (`backend/models.py`) correctly scopes every table to `user_id`. The data leaks exist only in the legacy stack, which is not deployed.

---

### 4. Configuration Chaos — High

**ID**: `config-chaos`  
**Severity**: `high`  
**Where**: `config/loader.py:1-94`, `config/profile_loader.py:1-63`, `config/settings.yaml`, `config/cv_data.yaml`, `backend/auth.py:15`, `backend/models.py:13`  
**What is wrong**: Four configuration mechanisms coexist with no documented precedence:
1. `config/settings.yaml` → loaded by `Config` class (`config/loader.py`)
2. `config/cv_data.yaml` → loaded by `ProfileLoader` (`config/profile_loader.py`)
3. `.env` file → loaded by `Config._load_env()`, overrides settings
4. Environment variables → read directly by `backend/auth.py` (SECRET_KEY), `backend/models.py` (DB_PATH), `backend/llm_engine.py` (SYSTEM_DEEPSEEK_KEY)
5. Per-user LLM keys → stored in `UserLLMSettings` DB table (deployed stack only)

The legacy stack reads a single CV from `config/cv_data.yaml` and a single profile from `config/profile_loader.py` (active profile). The deployed stack uses per-user DB records (`UserProfile`, `UploadedCV`, `UserLLMSettings`).  
**Impact**: Unpredictable behavior. Secrets management is inconsistent (`.env` vs DB). No single source of truth.  
**Fix**: Consolidate to one mechanism: environment variables for secrets, DB for per-user settings, drop YAML files. Document precedence explicitly. **Size**: M.

---

### 5. Monolithic Modules — High

**ID**: `app-py-monolith`  
**Severity**: `high`  
**Where**: `backend/app.py:1-1471`  
**What is wrong**: Single 1471-line file handles: auth (register/login/Google), CV upload/parse/list/view, user profile CRUD, job search (start/status/stop), match retrieval, job saving/status updates, CV generation, cover letter generation, company CRUD/import/export/test, stats, LLM settings (get/update/test), admin cleanup/URL checks, notifications.  
**Impact**: Impossible to test in isolation. Any change risks unrelated endpoints. Violates single responsibility. Deployment requires full redeploy.  
**Fix**: Split into routers/modules:
- `auth.py` → `/api/auth/*` (already partially separate in `auth.py`)
- `cv.py` → `/api/cv/*` (upload, list, view, generate, download)
- `profile.py` → `/api/profile/*` (get, update)
- `jobs.py` → `/api/jobs/*` (search, matches, save, status, by-company)
- `companies.py` → `/api/companies/*` (list, add, update, delete, export, import, test)
- `settings.py` → `/api/settings/*` (llm, notifications)
- `admin.py` → `/api/admin/*` (cleanup, check-urls)
**Size**: L (1471 lines → ~7 files, ~200 lines each).

**ID**: `job-scanner-py-monolith`  
**Severity**: `high`  
**Where**: `backend/job_scanner.py:1-1361`  
**What is wrong**: Single 1361-line file handles: garbage title filtering (78 patterns), adaptive learning (scan history prioritization), ATS pattern caching, Workday configs (11 companies), 10 ATS API fetchers (Lever, Greenhouse, Ashby, Workday, TurboHire, SmartRecruiters, Workable, Recruitee, Breezy, HireHive), LinkedIn fetcher, Google/HTML parser, JSON-LD extractor, embedded JSON finder, company-specific search URL patterns (54 companies), Playwright browser scanner (fallback), vision-based AI browser agent (Gemini).  
**Impact**: Untestable. Adding a new ATS requires editing this massive file. Browser logic, API logic, and learning logic are tangled.  
**Fix**: Split into:
- `scanner/garbage.py` — `is_garbage_title()`, `GARBAGE_PATTERNS`
- `scanner/learning.py` — `_record_scan_outcome()`, `_get_prioritized_methods()`, `ScanHistory` model
- `scanner/ats_api.py` — all `_fetch_*_jobs()` functions, `detect_ats()`, slug mappings
- `scanner/browser.py` — `scan_company_browser()`, `fetch_job_description()`
- `scanner/vision.py` — `vision_scan_company()` integration
- `scanner/search_urls.py` — `get_search_url()`, `COMPANY_SEARCH_PATTERNS`
- `scanner/hybrid.py` — `scan_company_hybrid()` orchestration
- `scanner/__init__.py` — public API
**Size**: L (1361 lines → ~8 files).

---

### 6. Agent Layer — Medium

**ID**: `agent-layer-no-abstraction`  
**Severity**: `medium`  
**Where**: `agents/__init__.py:1`, `agents/*.py` (13 modules)  
**What is wrong**: The `agents/` directory contains 13 modules with **no shared base class, no common interface, no registry**. Each is an ad-hoc script:
- `job_scanner.py` — `JobScannerAgent` with `build_search_queries()`, `parse_job_from_page()`
- `job_matcher.py` — `JobMatcherAgent` with `score_job()`
- `cv_tailor.py` — `CVTailorAgent` with `generate_tailoring_prompt()`, `save_tailored_cv()`
- `cv_generator.py` — `CVGenerator` class (297 lines, PDF/DOCX generation)
- `llm_engine.py` — `LLMEngine` (78 lines, Kiro/DeepSeek)
- `email_agent.py` — `EmailAgent` (IMAP/SMTP)
- `account_creator.py` — `AccountCreatorAgent`
- `apply_agent.py` — `ApplyAgent`
- `batch_scanner.py` — `BatchScanner`
- `batch_applier.py` — `BatchApplier` (29KB!)
- `google_scanner.py` — `GoogleScanner`
- `captcha_solver.py` — `CaptchaSolver`
- `ats_learner.py` — `ATSLearner`

No `BaseAgent` abstract class. No `Agent` protocol. No dependency injection. The orchestrator (`orchestrator.py:23-35`) instantiates each directly with different constructor signatures.  
**Impact**: Cannot swap implementations. Cannot test agents in isolation. No plugin architecture. Duplicated logic with deployed stack (see #1).  
**Fix**: Define `BaseAgent` abstract class with `run()`, `health_check()`. Create agent registry. Migrate to dependency injection. **Size**: M.

---

### 7. Legacy Stack Uses Single-User Config — Medium

**ID**: `legacy-single-user-config`  
**Severity**: `medium`  
**Where**: `config/loader.py:53-90`, `config/profile_loader.py:36-42`, `orchestrator.py:27-34`  
**What is wrong**: `Config.cv_data` returns a single dict from `config/cv_data.yaml`. `ProfileLoader.get_active_profile()` returns the one YAML with `active: true`. `Orchestrator.__init__` reads `self.config.cv_data` and `self.config.user` once at startup.  
**Impact**: The legacy pipeline can only ever serve one user. Hardcoded to the single active profile.  
**Fix**: N/A — legacy stack is dead (see #1).

---

### 8. Duplicated Modules with Different APIs — Medium

**ID**: `llm-engine-duplication`  
**Severity**: `medium`  
**Where**: `agents/llm_engine.py:1-78`, `backend/llm_engine.py:1-221`  
**What is wrong**: Two completely different implementations. Legacy: single-class `LLMEngine` with Kiro primary, DeepSeek fallback. Deployed: multi-provider router (`call_llm()`) supporting DeepSeek, OpenAI, Anthropic, Google, Groq, Mistral, Ollama with per-user keys from DB.  
**Impact**: Inconsistent LLM behavior. Bug fixes must be applied twice.  
**Fix**: Delete legacy `agents/llm_engine.py`. **Size**: XS.

**ID**: `job-scanner-duplication`  
**Severity**: `medium`  
**Where**: `agents/job_scanner.py:1-128`, `backend/job_scanner.py:1-1361`  
**What is wrong**: Legacy is a thin instruction generator for Browser MCP (128 lines). Deployed is a full hybrid scanner with 10 ATS APIs, Playwright, HTML parsing, LinkedIn, vision agent (1361 lines). Different APIs, different capabilities.  
**Fix**: Delete legacy `agents/job_scanner.py`. **Size**: XS.

**ID**: `cv-generator-duplication`  
**Severity**: `medium`  
**Where**: `agents/cv_tailor.py` + `agents/cv_generator.py` (297 lines), `backend/cv_generator.py` (328 lines)  
**What is wrong**: Legacy has two classes: `CVTailorAgent` (prompt generation) and `CVGenerator` (PDF/DOCX). Deployed has `generate_tailored_cv()` + `generate_cover_letter()` functions. Different prompts, different output formats.  
**Fix**: Delete legacy `agents/cv_tailor.py` and `agents/cv_generator.py`. **Size**: XS.

---

### 9. Database Path Divergence — Low

**ID**: `db-path-divergence`  
**Severity**: `low`  
**Where**: `db/models.py:101-102`, `backend/models.py:13`, `docker-compose.yml:14`  
**What is wrong**: Legacy: `Path(__file__).parent.parent / "data" / "monkeyking.db"` → `monkeyking/data/monkeyking.db`. Deployed: `MK_DB_PATH` env var, default `backend/data/monkeyking.db`. Docker mounts `mk_data:/app/data` so container path is `/app/data/monkeyking.db`.  
**Impact**: If legacy code ever ran in container, it would write to wrong path.  
**Fix**: N/A — legacy stack is dead.

---

### 10. No Shared Kernel Between Stacks — Low

**ID**: `no-shared-kernel`  
**Severity**: `low`  
**Where**: Entire repo  
**What is wrong**: Zero shared code between legacy and deployed stacks. Not even a common `models.py` or `config.py`. The only overlap is the three duplicated modules (which have different implementations).  
**Impact**: Confirms these are two separate products accidentally in one repo.  
**Fix**: N/A — legacy stack is dead.

---

## Top 5 (Worst First)

| Rank | ID | Severity | Summary |
|------|-----|----------|---------|
| 1 | `two-stack-split` | blocker | Two parallel stacks; legacy is dead code cluttering the repo |
| 2 | `dual-sqlalchemy-models` | blocker | Two incompatible ORM schemas; legacy has no user scoping |
| 3 | `legacy-missing-user-id-*` (4×) | blocker | All 5 legacy tables lack `user_id` — multi-user data leaks |
| 4 | `app-py-monolith` | high | 1471-line God class handling 12+ concerns |
| 5 | `job-scanner-py-monolith` | high | 1361-line scanner mixing 10 ATS APIs, browser, vision, learning |

---

## Three Structural Changes

### 1. Delete the Legacy Stack Entirely
**What**: Remove `main.py`, `orchestrator.py`, `agents/`, `db/`, `config/`, root `requirements.txt`. Keep only `backend/`, `frontend/`, `docker-compose.yml`, `Dockerfile.*`.  
**Size**: M (~50 files, ~15k lines removed).  
**Breaks**: Nothing — the legacy stack is not built, not deployed, not used. The only "breakage" is removing dead code that confuses contributors.

### 2. Split `backend/app.py` into Router Modules
**What**: Extract 7 focused routers (auth, cv, profile, jobs, companies, settings, admin) registered via `include_router()`. Keep `app.py` as a thin composition root (<100 lines).  
**Size**: L (1471 lines → 7 files + composition root).  
**Breaks**: All import paths for `backend.app` internals. Tests need updating. Requires careful route prefix preservation (`/api/auth`, `/api/cv`, etc.).

### 3. Split `backend/job_scanner.py` into Scanner Package
**What**: Create `backend/scanner/` package with 8 modules (garbage, learning, ats_api, browser, vision, search_urls, hybrid, `__init__`).  
**Size**: L (1361 lines → 8 files).  
**Breaks**: `backend/app.py` imports (`from job_scanner import run_search`). Update to `from scanner.hybrid import run_search` or re-export from `scanner/__init__.py`.

---

## What Works Well

- **Deployed data model** (`backend/models.py`) is sound: proper multi-user scoping, cascade deletes, indexes, WAL mode, per-user LLM settings, preference learning tables.
- **Auth design** (`backend/auth.py`) is clean: JWT + Google OAuth, proper password hashing, token refresh not needed (72h expiry).
- **CV generation** (`backend/cv_generator.py`) produces both PDF and DOCX with ATS-safe formatting.
- **Job scanner hybrid strategy** (ATS API → browser → HTML → LinkedIn → vision) is architecturally correct for reliability.
- **Adaptive learning** (`ScanHistory` + prioritized methods) is a strong pattern for evolving scraper reliability.

---

## What Does Not Work

- **Legacy stack** — not deployed, not maintained, multi-user broken, duplicated modules.
- **Configuration** — four mechanisms, no precedence, YAML + env + DB mixed.
- **Module boundaries** — two God classes (`app.py`, `job_scanner.py`) doing everything.
- **Agent layer** — 13 ad-hoc scripts, no abstraction, duplicated with deployed stack.

---

## Final Verdict

**Does this part of the app work as written?**  
**No** — the legacy stack (50% of the repo) is dead code that doesn't work for multi-user. The deployed stack works but is fragile due to monolithic modules and configuration chaos. **Immediate action**: delete the legacy stack, then split the two monoliths.