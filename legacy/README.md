# Legacy Apply Pipeline

This folder contains the original apply-side implementation — the only code that implements the product's headline feature (autonomous job application).

## Why this folder exists

- **Docker does not build this folder.** `docker-compose.yml` builds only `Dockerfile.backend` → `backend/` and `Dockerfile.frontend` → `frontend/`. This folder is never included in any container image.
- **It does not run as-is.** `config/profile_loader.py:get_active_profile()` raises `ValueError` because `config/profiles/` is gitignored (`.gitignore:11`) and absent, and its schema is documented nowhere.
- **It is kept as the reference implementation** for the apply pipeline — portal account creation, Gmail verification, CAPTCHA handling, form fill and submit, ATS pattern replay — none of which exists in `backend/`.
- **Port target:** a future `/api/jobs/apply` endpoint on the `User` / `UserJob` schema.

## Contents

- `agents/` — apply driver (`batch_applier.py`), CV generator, ATS learner, apply agent, email agent (Gmail IMAP), CAPTCHA solver
- `config/` — configuration loader, profile loader, settings.yaml, cv_data.yaml
- `db/` — SQLAlchemy models for Job, TailoredCV, Application, Account

## Import paths

All intra-package imports have been rewritten to use `legacy.` prefix (e.g., `from legacy.config.loader import Config`). This folder is internally consistent and passes `python3 -m compileall legacy/`.