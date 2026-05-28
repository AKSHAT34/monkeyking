"""MonkeyKing Web App — FastAPI Backend."""
import os
import json
import shutil
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from models import (
    init_db, User, UserProfile, UploadedCV, Job, Company,
    UserJob, UserJobMatch, SearchRun, ApplicationStatus, UserLLMSettings
)
from auth import (
    get_db, get_current_user, register_user, login_user,
    google_login_or_register, create_token,
    RegisterRequest, LoginRequest
)
from cv_parser import parse_cv, extract_text, score_job_match
from cv_generator import generate_tailored_cv
from companies import seed_companies

app = FastAPI(title="MonkeyKing", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(__file__).parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.on_event("startup")
async def startup():
    db = next(get_db())
    count = seed_companies(db)
    total = db.query(Company).count()
    print(f"🐵 MonkeyKing started — {total} companies ({count} new)")
    db.close()


# ─── AUTH ───────────────────────────────────────────────
@app.post("/api/auth/register")
async def api_register(req: RegisterRequest, db: Session = Depends(get_db)):
    user = register_user(db, req)
    token = create_token(user)
    return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name}}


@app.post("/api/auth/login")
async def api_login(req: LoginRequest, db: Session = Depends(get_db)):
    user, token = login_user(db, req)
    return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name}}


class GoogleAuthRequest(BaseModel):
    credential: str

@app.post("/api/auth/google")
async def api_google_auth(req: GoogleAuthRequest, db: Session = Depends(get_db)):
    from jose import jwt as jose_jwt
    try:
        payload = jose_jwt.decode(req.credential, options={"verify_signature": False})
        user, token = google_login_or_register(db, payload)
        return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name, "avatar": user.avatar_url}}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google auth failed: {str(e)}")


@app.get("/api/auth/me")
async def api_me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "avatar": user.avatar_url, "is_admin": bool(user.is_admin)}


# ─── CV UPLOAD & PARSING ───────────────────────────────
@app.post("/api/cv/upload")
async def api_upload_cv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if file.content_type not in ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
        raise HTTPException(400, "Only PDF and DOCX files are supported")

    ext = ".pdf" if "pdf" in file.content_type else ".docx"
    filename = f"user_{user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
    file_path = str(UPLOAD_DIR / filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    raw_text = extract_text(file_path)
    # Use user's LLM config
    from llm_engine import get_user_llm_config
    llm_provider, llm_key = get_user_llm_config(db, user.id)
    parsed = await parse_cv(file_path, provider=llm_provider, api_key=llm_key)

    cv = UploadedCV(
        user_id=user.id,
        filename=file.filename,
        file_path=file_path,
        file_type=ext.lstrip("."),
        raw_text=raw_text,
        parsed_data=parsed,
        is_primary=db.query(UploadedCV).filter_by(user_id=user.id).count() == 0,
    )
    db.add(cv)

    # Merge data from ALL uploaded CVs into unified profile
    profile = db.query(UserProfile).filter_by(user_id=user.id).first()
    if not profile:
        profile = UserProfile(user_id=user.id)
        db.add(profile)

    if not parsed.get("error"):
        # Get all CVs for this user to merge
        all_cvs = db.query(UploadedCV).filter_by(user_id=user.id).all()
        all_parsed = [c.parsed_data for c in all_cvs if c.parsed_data and not c.parsed_data.get("error")]
        if parsed not in all_parsed:
            all_parsed.append(parsed)

        # Merge skills from all CVs
        merged_skills = {}
        for p in all_parsed:
            for cat, skills in (p.get("skills") or {}).items():
                if cat not in merged_skills:
                    merged_skills[cat] = []
                for s in (skills or []):
                    if s not in merged_skills[cat]:
                        merged_skills[cat].append(s)

        # Merge experience (deduplicate by company+title)
        merged_exp = []
        seen_exp = set()
        for p in all_parsed:
            for exp in (p.get("experience") or []):
                key = f"{exp.get('company','')}-{exp.get('title','')}"
                if key not in seen_exp:
                    seen_exp.add(key)
                    merged_exp.append(exp)

        # Merge education, certs, projects (deduplicate)
        merged_edu = []
        seen_edu = set()
        for p in all_parsed:
            for edu in (p.get("education") or []):
                key = f"{edu.get('institution','')}-{edu.get('degree','')}"
                if key not in seen_edu:
                    seen_edu.add(key)
                    merged_edu.append(edu)

        merged_certs = list(set(c for p in all_parsed for c in (p.get("certifications") or [])))

        merged_projects = []
        seen_proj = set()
        for p in all_parsed:
            for proj in (p.get("projects") or []):
                key = proj.get("name", "")
                if key and key not in seen_proj:
                    seen_proj.add(key)
                    merged_projects.append(proj)

        # Merge suggested roles (union of all)
        merged_roles = list(set(r for p in all_parsed for r in (p.get("suggested_roles") or [])))

        # Use the latest/best summary
        best_summary = parsed.get("summary") or profile.extracted_summary or ""

        # Update profile with merged data
        profile.extracted_skills = merged_skills
        profile.extracted_experience = merged_exp
        profile.extracted_education = merged_edu
        profile.extracted_certifications = merged_certs
        profile.extracted_projects = merged_projects
        profile.extracted_summary = best_summary
        profile.suggested_roles = merged_roles
        profile.years_experience = max((p.get("years_experience") or 0) for p in all_parsed) if all_parsed else 0
        if parsed.get("phone") and not profile.phone:
            profile.phone = parsed["phone"]
        if parsed.get("location") and not profile.location:
            profile.location = parsed["location"]
        if parsed.get("linkedin") and not profile.linkedin:
            profile.linkedin = parsed["linkedin"]

    db.commit()
    return {"cv_id": cv.id, "parsed": parsed, "filename": file.filename, "total_cvs": db.query(UploadedCV).filter_by(user_id=user.id).count()}


@app.get("/api/cv/list")
async def api_list_cvs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    cvs = db.query(UploadedCV).filter_by(user_id=user.id).order_by(UploadedCV.uploaded_at.desc()).all()
    return [{"id": c.id, "filename": c.filename, "is_primary": c.is_primary,
             "uploaded_at": c.uploaded_at.isoformat(), "file_type": c.file_type} for c in cvs]


@app.get("/api/cv/view/{cv_id}", response_model=None)
async def api_view_cv(cv_id: int, token: str = None, db: Session = Depends(get_db)):
    """View CV — supports both header auth and query param token for iframe embedding."""
    user = None
    # Try query param token first (for iframe)
    if token:
        from jose import JWTError, jwt as jose_jwt
        from auth import SECRET_KEY, ALGORITHM
        try:
            payload = jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = int(payload.get("sub", 0))
            user = db.query(User).filter_by(id=user_id).first()
        except (JWTError, Exception):
            raise HTTPException(401, "Invalid token")
    if not user:
        raise HTTPException(401, "Not authenticated")

    cv = db.query(UploadedCV).filter_by(id=cv_id, user_id=user.id).first()
    if not cv or not cv.file_path:
        raise HTTPException(404, "CV not found")
    if not Path(cv.file_path).exists():
        raise HTTPException(404, "CV file missing")
    media_type = "application/pdf" if cv.file_type == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    from fastapi.responses import Response
    content = Path(cv.file_path).read_bytes()
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f"inline; filename={cv.filename}",
            "X-Frame-Options": "SAMEORIGIN",
        },
    )


# ─── USER PROFILE ──────────────────────────────────────
class ProfileUpdate(BaseModel):
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin: Optional[str] = None
    notice_period: Optional[str] = None
    current_salary: Optional[str] = None
    expected_salary: Optional[str] = None
    preferred_locations: Optional[list] = None
    target_roles: Optional[list] = None
    work_authorization: Optional[str] = None
    willing_to_relocate: Optional[bool] = None
    years_experience: Optional[int] = None
    extracted_skills: Optional[dict] = None
    extracted_experience: Optional[list] = None
    extracted_education: Optional[list] = None
    extracted_certifications: Optional[list] = None
    extracted_projects: Optional[list] = None
    extracted_summary: Optional[str] = None


@app.get("/api/profile")
async def api_get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(UserProfile).filter_by(user_id=user.id).first()
    if not profile:
        return {}
    return {
        "phone": profile.phone, "location": profile.location, "linkedin": profile.linkedin,
        "notice_period": profile.notice_period, "current_salary": profile.current_salary,
        "expected_salary": profile.expected_salary, "preferred_locations": profile.preferred_locations,
        "target_roles": profile.target_roles, "work_authorization": profile.work_authorization,
        "willing_to_relocate": profile.willing_to_relocate, "years_experience": profile.years_experience,
        "extracted_skills": profile.extracted_skills, "extracted_experience": profile.extracted_experience,
        "extracted_education": profile.extracted_education, "extracted_certifications": profile.extracted_certifications,
        "extracted_projects": profile.extracted_projects, "extracted_summary": profile.extracted_summary,
        "suggested_roles": profile.suggested_roles,
    }


@app.put("/api/profile")
async def api_update_profile(
    update: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    import time
    from sqlalchemy.exc import OperationalError
    for attempt in range(5):
        try:
            profile = db.query(UserProfile).filter_by(user_id=user.id).first()
            if not profile:
                profile = UserProfile(user_id=user.id)
                db.add(profile)
            for field, value in update.dict(exclude_none=True).items():
                setattr(profile, field, value)
            db.commit()
            return {"status": "updated"}
        except OperationalError as e:
            db.rollback()
            if "database is locked" in str(e) and attempt < 4:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise HTTPException(500, "Database busy — please try again in a moment")


# ─── JOB SEARCH ────────────────────────────────────────
@app.post("/api/jobs/search")
async def api_search_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a batch job search (50 companies). Skips already-searched and current employer."""
    profile = db.query(UserProfile).filter_by(user_id=user.id).first()
    if not profile or not profile.target_roles:
        raise HTTPException(400, "Set your target roles first")

    user_profile = {
        "name": user.name, "email": user.email,
        "summary": profile.extracted_summary or "",
        "skills": profile.extracted_skills or {},
        "experience": profile.extracted_experience or [],
        "education": profile.extracted_education or [],
        "certifications": profile.extracted_certifications or [],
        "projects": profile.extracted_projects or [],
        "target_roles": profile.target_roles or [],
        "years_experience": profile.years_experience or 0,
        "preferred_locations": profile.preferred_locations or [],
    }

    # Extract ONLY current/most recent employer to exclude
    exclude_companies = set()
    experience_list = profile.extracted_experience or []
    if experience_list:
        # First entry is typically the current/most recent job
        current = experience_list[0]
        company_name = (current.get("company") or "").strip().lower()
        if company_name:
            exclude_companies.add(company_name)
            # Common variations
            for suffix in [" india", " inc", " inc.", " ltd", " limited", " pvt", " pvt."]:
                exclude_companies.add(company_name + suffix)
                if company_name.endswith(suffix.strip()):
                    exclude_companies.add(company_name.replace(suffix.strip(), "").strip())

    # Find companies already searched in the last 7 days
    from datetime import timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_runs = (
        db.query(SearchRun)
        .filter_by(user_id=user.id, status="completed")
        .filter(SearchRun.completed_at >= week_ago)
        .all()
    )
    already_searched_names = set()
    for run in recent_runs:
        for entry in (run.progress_log or []):
            if entry.get("status") == "done":
                already_searched_names.add(entry["company"].lower())

    # Get all companies, filter out searched + current employer
    # PRIORITIZE: user's preferred country first, then randomize
    import random
    pref_locs = [l.lower() for l in (profile.preferred_locations or [])]
    # Determine preferred countries from locations
    pref_countries = set()
    for loc in pref_locs:
        loc_clean = loc.replace("remote - ", "").replace("remote ", "").strip()
        if loc_clean in ("india", "us", "usa", "uk", "canada", "singapore", "uae", "germany", "australia"):
            pref_countries.add(loc_clean)
        # If they selected Indian cities, add India
        if loc_clean in ("bangalore", "bengaluru", "mumbai", "delhi", "delhi ncr", "hyderabad", "pune", "chennai", "gurgaon", "noida", "kolkata"):
            pref_countries.add("india")

    all_companies = db.query(Company).all()

    # Smart company ranking based on user's target roles
    # Map role keywords to company categories that typically hire those roles
    role_text = " ".join(profile.target_roles or []).lower()

    ROLE_CATEGORY_SCORES = {
        # If user wants account/sales roles → prioritize large enterprises, consulting, fintech
        "account": {"tech_giants": 3, "consulting": 3, "cloud_saas": 3, "fintech": 2, "banking": 2, "mnc_india": 2, "e-commerce": 2},
        "sales": {"tech_giants": 3, "consulting": 3, "cloud_saas": 3, "fintech": 2, "saas": 2, "e-commerce": 2},
        "product": {"tech_giants": 3, "ai_companies": 3, "cloud_saas": 3, "indian_startups": 2, "saas": 2, "fintech": 2, "e-commerce": 2},
        "project": {"tech_giants": 2, "consulting": 3, "it_services": 3, "mnc_india": 2, "banking": 2},
        "program": {"tech_giants": 3, "consulting": 2, "cloud_saas": 2, "mnc_india": 2},
        "strategy": {"consulting": 3, "tech_giants": 2, "fintech": 2, "banking": 2},
        "operations": {"e-commerce": 3, "indian_startups": 2, "fintech": 2, "logistics": 3, "healthcare": 2},
        "marketing": {"e-commerce": 3, "indian_startups": 2, "saas": 2, "cloud_saas": 2, "fintech": 2},
        "data": {"tech_giants": 3, "ai_companies": 3, "fintech": 2, "cloud_saas": 2},
        "engineer": {"tech_giants": 3, "ai_companies": 3, "indian_startups": 2, "saas": 2, "cloud_saas": 2},
        "delivery": {"consulting": 3, "it_services": 3, "tech_giants": 2, "mnc_india": 2},
        "growth": {"indian_startups": 3, "e-commerce": 3, "fintech": 2, "saas": 2},
    }

    # Known companies that are strong for specific role types
    ROLE_COMPANY_BOOST = {
        "account": ["salesforce", "oracle", "sap", "adobe", "microsoft", "google", "aws", "ibm",
                     "accenture", "deloitte", "wipro", "tcs", "infosys", "hcl", "cognizant"],
        "product": ["google", "microsoft", "meta", "flipkart", "swiggy", "zomato", "paytm",
                     "phonepe", "razorpay", "meesho", "cred", "groww", "dream11", "freshworks",
                     "postman", "notion", "atlassian", "stripe", "databricks"],
        "project": ["accenture", "deloitte", "tcs", "infosys", "wipro", "cognizant", "capgemini",
                     "ibm", "oracle", "sap", "microsoft"],
        "sales": ["salesforce", "oracle", "sap", "adobe", "hubspot", "freshworks", "zoho",
                   "paytm", "razorpay", "phonepe"],
        "ai": ["openai", "anthropic", "google", "microsoft", "nvidia", "databricks", "scale ai",
                "hugging face", "cohere", "mistral ai"],
    }

    def score_company(c):
        """Score a company based on how likely it has the user's target roles."""
        score = 0
        cat = (c.category or "").lower().replace(" ", "_")
        name_lower = c.name.lower()

        # Category match
        for keyword, cat_scores in ROLE_CATEGORY_SCORES.items():
            if keyword in role_text:
                score += cat_scores.get(cat, 0)

        # Direct company boost
        for keyword, companies in ROLE_COMPANY_BOOST.items():
            if keyword in role_text:
                if name_lower in companies:
                    score += 5

        # Preferred country boost
        country_lower = (c.country or "").lower()
        if pref_countries and (country_lower in pref_countries or any(pc in country_lower for pc in pref_countries)):
            score += 3

        return score

    # Score and sort all eligible companies
    scored = []
    for c in all_companies:
        name_lower = c.name.lower()
        if name_lower in already_searched_names:
            continue
        if name_lower in exclude_companies:
            continue
        s = score_company(c)
        scored.append((s, random.random(), {"name": c.name, "careers_url": c.careers_url}))

    # Sort by score descending, then random for ties
    scored.sort(key=lambda x: (-x[0], x[1]))
    eligible = [entry for _, _, entry in scored[:50]]

    if not eligible:
        raise HTTPException(400, "All companies have been searched in the last 7 days. Try again later or add new companies.")

    search_run = SearchRun(user_id=user.id, status="pending", progress_log=[])
    db.add(search_run)
    db.commit()
    db.refresh(search_run)

    run_id = search_run.id
    user_id = user.id
    target_roles = list(profile.target_roles or [])
    company_list = list(eligible)
    excluded_names = [n.title() for n in list(exclude_companies)[:5]]

    # Get user's LLM config for the background thread
    from llm_engine import get_user_llm_config
    llm_provider, llm_key = get_user_llm_config(db, user.id)

    import threading

    def _run_sync():
        import asyncio
        from job_scanner import run_search
        sdb = next(get_db())
        try:
            asyncio.run(run_search(sdb, run_id, user_id, user_profile, target_roles, company_list,
                                   llm_provider=llm_provider, llm_key=llm_key))
        except Exception as e:
            try:
                sr = sdb.query(SearchRun).get(run_id)
                sr.status = "failed"
                sdb.commit()
            except Exception:
                pass
            print(f"Search error: {e}", flush=True)
            import traceback
            traceback.print_exc()
        finally:
            sdb.close()

    thread = threading.Thread(target=_run_sync, daemon=True)
    thread.start()
    return {
        "search_run_id": search_run.id,
        "status": "started",
        "companies_count": len(eligible),
        "excluded_employers": excluded_names,
        "already_searched": len(already_searched_names),
    }


@app.get("/api/jobs/search/active")
async def api_active_search(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Check if there's a currently running search for this user."""
    sr = (db.query(SearchRun)
          .filter_by(user_id=user.id)
          .filter(SearchRun.status.in_(["running", "pending"]))
          .order_by(SearchRun.started_at.desc())
          .first())
    if not sr:
        return {"active": False}
    return {
        "active": True,
        "search_run_id": sr.id,
        "status": sr.status,
        "companies_searched": sr.companies_searched,
        "jobs_found": sr.jobs_found,
        "jobs_matched": sr.jobs_matched,
        "progress": sr.progress_log or [],
    }


@app.post("/api/jobs/search/stop/{run_id}")
async def api_stop_search(run_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sr = db.query(SearchRun).filter_by(id=run_id, user_id=user.id).first()
    if not sr:
        raise HTTPException(404, "Search run not found")
    sr.status = "stopped"
    sr.completed_at = datetime.utcnow()
    # Mark any scanning/pending entries as skipped
    log = list(sr.progress_log or [])
    for entry in log:
        if entry["status"] in ("scanning", "pending"):
            entry["status"] = "skipped"
    sr.progress_log = log
    db.commit()
    return {"status": "stopped"}


@app.get("/api/jobs/search/{run_id}")
async def api_search_status(run_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sr = db.query(SearchRun).filter_by(id=run_id, user_id=user.id).first()
    if not sr:
        raise HTTPException(404, "Search run not found")
    return {
        "id": sr.id, "status": sr.status,
        "companies_searched": sr.companies_searched,
        "jobs_found": sr.jobs_found, "jobs_matched": sr.jobs_matched,
        "started_at": sr.started_at.isoformat() if sr.started_at else None,
        "completed_at": sr.completed_at.isoformat() if sr.completed_at else None,
        "progress": sr.progress_log or [],
    }


@app.get("/api/jobs/matches")
async def api_get_matches(
    min_score: float = 0.0,
    limit: int = 1000,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all matched jobs for the user, sorted by score."""
    matches = (
        db.query(UserJobMatch, Job)
        .join(Job, UserJobMatch.job_id == Job.id)
        .filter(UserJobMatch.user_id == user.id)
        .filter(UserJobMatch.match_score >= min_score)
        .order_by(UserJobMatch.match_score.desc())
        .limit(limit)
        .all()
    )
    # Check which ones user has already saved
    saved_ids = set(
        uj.job_id for uj in db.query(UserJob).filter_by(user_id=user.id).all()
    )
    return [{
        "match_id": m.id,
        "job_id": j.id,
        "title": j.title,
        "company": j.company,
        "location": j.location or "",
        "url": j.url,
        "match_score": m.match_score,
        "match_reason": m.match_reason,
        "matched_skills": m.matched_skills or [],
        "missing_skills": m.missing_skills or [],
        "relevance_summary": m.relevance_summary,
        "is_saved": j.id in saved_ids,
        "discovered_at": j.discovered_at.isoformat() if j.discovered_at else None,
    } for m, j in matches]


# ─── USER JOBS (TRACKING) ──────────────────────────────
class SaveJobsRequest(BaseModel):
    job_ids: list[int]

@app.post("/api/jobs/save")
async def api_save_jobs(req: SaveJobsRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Save selected jobs to user's tracking list."""
    import time
    from sqlalchemy.exc import OperationalError
    for attempt in range(5):
        try:
            added = 0
            for jid in req.job_ids:
                existing = db.query(UserJob).filter_by(user_id=user.id, job_id=jid).first()
                if not existing:
                    db.add(UserJob(user_id=user.id, job_id=jid))
                    added += 1
            db.commit()
            # Record positive feedback for preference learning
            try:
                from models import UserPreferenceHistory, UserJobMatch
                from preference_engine import recompute_preferences
                for jid in req.job_ids:
                    job = db.query(Job).get(jid)
                    if not job:
                        continue
                    match = db.query(UserJobMatch).filter_by(user_id=user.id, job_id=jid).first()
                    matched_skills = match.matched_skills if match else []
                    db.add(UserPreferenceHistory(
                        user_id=user.id, job_id=jid, signal_type="positive",
                        job_title=job.title, job_company=job.company,
                        matched_skills=matched_skills
                    ))
                db.commit()
                # Recompute preferences for the last saved job (covers all keywords)
                if req.job_ids:
                    last_job = db.query(Job).get(req.job_ids[-1])
                    if last_job:
                        last_match = db.query(UserJobMatch).filter_by(user_id=user.id, job_id=last_job.id).first()
                        recompute_preferences(db, user.id, last_job.title, last_job.company,
                                            last_match.matched_skills if last_match else [])
            except Exception as e:
                try: db.rollback()
                except: pass
                print(f"  [learn] Feedback recording failed: {e}", flush=True)
            return {"added": added}
        except OperationalError as e:
            db.rollback()
            if "database is locked" in str(e) and attempt < 4:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise HTTPException(500, "Database busy — please try again in a moment")


@app.get("/api/jobs/saved")
async def api_get_saved_jobs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    saved = (
        db.query(UserJob, Job)
        .join(Job, UserJob.job_id == Job.id)
        .filter(UserJob.user_id == user.id)
        .order_by(UserJob.created_at.desc())
        .all()
    )
    return [{
        "user_job_id": uj.id,
        "job_id": j.id,
        "title": j.title,
        "company": j.company,
        "location": j.location or "",
        "url": j.url,
        "status": uj.status,
        "tailored_cv_path": uj.tailored_cv_path,
        "tailored_cv_docx_path": uj.tailored_cv_docx_path,
        "cover_letter_path": uj.cover_letter_path,
        "cover_letter_docx_path": uj.cover_letter_docx_path,
        "notes": uj.notes,
        "created_at": uj.created_at.isoformat(),
        "updated_at": uj.updated_at.isoformat() if uj.updated_at else None,
    } for uj, j in saved]


class UpdateJobStatus(BaseModel):
    status: str
    notes: Optional[str] = None

@app.put("/api/jobs/saved/{user_job_id}")
async def api_update_job_status(
    user_job_id: int,
    update: UpdateJobStatus,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    import time
    from sqlalchemy.exc import OperationalError
    for attempt in range(5):
        try:
            uj = db.query(UserJob).filter_by(id=user_job_id, user_id=user.id).first()
            if not uj:
                raise HTTPException(404, "Job not found")
            uj.status = update.status
            if update.notes is not None:
                uj.notes = update.notes
            db.commit()
            # Record feedback signal for preference learning
            try:
                from models import UserPreferenceHistory, UserJobMatch
                from preference_engine import recompute_preferences
                signal_map = {
                    "applied": "strong_positive",
                    "interview_scheduled": "strong_positive",
                    "offer_received": "strong_positive",
                    "rejected": "negative",
                }
                signal_type = signal_map.get(update.status)
                if signal_type:
                    job = db.query(Job).get(uj.job_id)
                    if job:
                        match = db.query(UserJobMatch).filter_by(user_id=user.id, job_id=uj.job_id).first()
                        matched_skills = match.matched_skills if match else []
                        db.add(UserPreferenceHistory(
                            user_id=user.id, job_id=uj.job_id, signal_type=signal_type,
                            job_title=job.title, job_company=job.company,
                            matched_skills=matched_skills
                        ))
                        db.commit()
                        recompute_preferences(db, user.id, job.title, job.company, matched_skills)
            except Exception as e:
                try: db.rollback()
                except: pass
                print(f"  [learn] Feedback recording failed: {e}", flush=True)
            return {"status": "updated"}
        except OperationalError as e:
            db.rollback()
            if "database is locked" in str(e) and attempt < 4:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise HTTPException(500, "Database busy — please try again in a moment")


# ─── CV GENERATION ─────────────────────────────────────
@app.post("/api/cv/generate/{job_id}")
async def api_generate_cv(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a tailored CV for a specific job."""
    job = db.query(Job).get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    profile = db.query(UserProfile).filter_by(user_id=user.id).first()
    if not profile:
        raise HTTPException(400, "Complete your profile first")

    user_profile = {
        "name": user.name, "email": user.email,
        "phone": profile.phone or "", "location": profile.location or "",
        "linkedin": profile.linkedin or "", "summary": profile.extracted_summary or "",
        "skills": profile.extracted_skills or {}, "experience": profile.extracted_experience or [],
        "education": profile.extracted_education or [], "certifications": profile.extracted_certifications or [],
        "projects": profile.extracted_projects or [],
    }

    from llm_engine import get_user_llm_config
    llm_provider, llm_key = get_user_llm_config(db, user.id)

    result = await generate_tailored_cv(user_profile, {
        "title": job.title, "company": job.company,
        "location": job.location, "description": job.description,
    }, provider=llm_provider, api_key=llm_key)

    if result.get("error"):
        raise HTTPException(500, result["error"])

    # Update user_job record
    uj = db.query(UserJob).filter_by(user_id=user.id, job_id=job_id).first()
    if not uj:
        uj = UserJob(user_id=user.id, job_id=job_id)
        db.add(uj)
    uj.tailored_cv_path = result["pdf_path"]
    uj.tailored_cv_docx_path = result["docx_path"]
    db.commit()

    return {"pdf_path": result["pdf_path"], "docx_path": result["docx_path"]}


@app.post("/api/cover-letter/generate/{job_id}")
async def api_generate_cover_letter(
    job_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a tailored cover letter for a specific job."""
    from cv_generator import generate_cover_letter

    job = db.query(Job).get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    profile = db.query(UserProfile).filter_by(user_id=user.id).first()
    if not profile:
        raise HTTPException(400, "Complete your profile first")

    user_profile = {
        "name": user.name, "email": user.email,
        "phone": profile.phone or "", "location": profile.location or "",
        "linkedin": profile.linkedin or "", "summary": profile.extracted_summary or "",
        "skills": profile.extracted_skills or {}, "experience": profile.extracted_experience or [],
        "education": profile.extracted_education or [], "certifications": profile.extracted_certifications or [],
    }

    from llm_engine import get_user_llm_config
    llm_provider, llm_key = get_user_llm_config(db, user.id)

    result = await generate_cover_letter(user_profile, {
        "title": job.title, "company": job.company,
        "location": job.location, "description": job.description,
    }, provider=llm_provider, api_key=llm_key)

    if result.get("error"):
        raise HTTPException(500, result["error"])

    uj = db.query(UserJob).filter_by(user_id=user.id, job_id=job_id).first()
    if not uj:
        uj = UserJob(user_id=user.id, job_id=job_id)
        db.add(uj)
    uj.cover_letter_path = result["pdf_path"]
    uj.cover_letter_docx_path = result["docx_path"]
    db.commit()

    return {"pdf_path": result["pdf_path"], "docx_path": result["docx_path"]}


@app.get("/api/cover-letter/download/{user_job_id}")
async def api_download_cover_letter(
    user_job_id: int,
    format: str = "pdf",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uj = db.query(UserJob).filter_by(id=user_job_id, user_id=user.id).first()
    if not uj:
        raise HTTPException(404, "Not found")
    path = uj.cover_letter_path if format == "pdf" else uj.cover_letter_docx_path
    if not path or not Path(path).exists():
        raise HTTPException(404, "Cover letter not generated yet")
    return FileResponse(path, filename=Path(path).name)


@app.get("/api/cv/download/{user_job_id}")
async def api_download_cv(
    user_job_id: int,
    format: str = "pdf",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uj = db.query(UserJob).filter_by(id=user_job_id, user_id=user.id).first()
    if not uj:
        raise HTTPException(404, "Not found")
    path = uj.tailored_cv_path if format == "pdf" else uj.tailored_cv_docx_path
    if not path or not Path(path).exists():
        raise HTTPException(404, "CV not generated yet")
    return FileResponse(path, filename=Path(path).name)


# ─── COMPANIES ─────────────────────────────────────────
@app.get("/api/companies")
async def api_list_companies(
    category: Optional[str] = None,
    country: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Company)
    if category:
        q = q.filter_by(category=category)
    if country:
        q = q.filter_by(country=country)
    if search:
        q = q.filter(Company.name.ilike(f"%{search}%"))
    companies = q.order_by(Company.name).all()
    return [{"id": c.id, "name": c.name, "careers_url": c.careers_url,
             "category": c.category, "country": c.country} for c in companies]


class AddCompanyRequest(BaseModel):
    name: str
    careers_url: str
    category: str = "other"
    country: str = "India"

@app.post("/api/companies")
async def api_add_company(
    req: AddCompanyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.query(Company).filter_by(careers_url=req.careers_url).first()
    if existing:
        return {"id": existing.id, "message": "Company already exists"}
    company = Company(
        name=req.name, careers_url=req.careers_url,
        category=req.category, country=req.country,
        added_by=user.id, is_verified=False,
    )
    db.add(company)
    db.commit()
    return {"id": company.id, "message": "Company added — available to all users"}


class UpdateCompanyRequest(BaseModel):
    name: Optional[str] = None
    careers_url: Optional[str] = None
    category: Optional[str] = None
    country: Optional[str] = None

@app.put("/api/companies/{company_id}")
async def api_update_company(
    company_id: int,
    req: UpdateCompanyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    company = db.query(Company).get(company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    if req.name is not None:
        company.name = req.name
    if req.careers_url is not None:
        company.careers_url = req.careers_url
    if req.category is not None:
        company.category = req.category
    if req.country is not None:
        company.country = req.country
    db.commit()
    return {"status": "updated"}

@app.delete("/api/companies/{company_id}")
async def api_delete_company(
    company_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    company = db.query(Company).get(company_id)
    if not company:
        raise HTTPException(404, "Company not found")
    db.delete(company)
    db.commit()
    return {"status": "deleted"}


@app.get("/api/jobs/by-company")
async def api_jobs_by_company(
    company: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all jobs found from a specific company, with match scores for this user."""
    jobs = db.query(Job).filter_by(company=company).order_by(Job.discovered_at.desc()).all()
    result = []
    for j in jobs:
        match = db.query(UserJobMatch).filter_by(user_id=user.id, job_id=j.id).first()
        result.append({
            "id": j.id,
            "title": j.title,
            "company": j.company,
            "location": j.location or "",
            "url": j.url,
            "description": (j.description or "")[:500],
            "match_score": match.match_score if match else None,
            "match_reason": match.match_reason if match else None,
            "matched_skills": match.matched_skills if match else [],
            "missing_skills": match.missing_skills if match else [],
        })
    return result


# ─── STATS ─────────────────────────────────────────────
@app.get("/api/stats")
async def api_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    matches = db.query(UserJobMatch).filter_by(user_id=user.id).count()
    saved = db.query(UserJob).filter_by(user_id=user.id).count()
    applied = db.query(UserJob).filter_by(user_id=user.id, status=ApplicationStatus.APPLIED.value).count()
    interviews = db.query(UserJob).filter_by(user_id=user.id, status=ApplicationStatus.INTERVIEW_SCHEDULED.value).count()
    offers = db.query(UserJob).filter_by(user_id=user.id, status=ApplicationStatus.OFFER_RECEIVED.value).count()
    companies = db.query(Company).count()
    return {
        "matches": matches, "saved": saved, "applied": applied,
        "interviews": interviews, "offers": offers, "total_companies": companies,
    }

# ─── LLM SETTINGS ──────────────────────────────────────
class LLMSettingsUpdate(BaseModel):
    active_provider: Optional[str] = None
    deepseek_key: Optional[str] = None
    openai_key: Optional[str] = None
    anthropic_key: Optional[str] = None
    google_key: Optional[str] = None
    groq_key: Optional[str] = None
    mistral_key: Optional[str] = None


@app.get("/api/settings/llm")
async def api_get_llm_settings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = db.query(UserLLMSettings).filter_by(user_id=user.id).first()
    if not settings:
        return {"active_provider": "deepseek", "providers": {}}

    def mask_key(key: str | None) -> str | None:
        if not key:
            return None
        if len(key) <= 8:
            return "****"
        return key[:4] + "..." + key[-4:]

    return {
        "active_provider": settings.active_provider or "deepseek",
        "providers": {
            "deepseek": {"has_key": bool(settings.deepseek_key), "masked_key": mask_key(settings.deepseek_key)},
            "openai": {"has_key": bool(settings.openai_key), "masked_key": mask_key(settings.openai_key)},
            "anthropic": {"has_key": bool(settings.anthropic_key), "masked_key": mask_key(settings.anthropic_key)},
            "google": {"has_key": bool(settings.google_key), "masked_key": mask_key(settings.google_key)},
            "groq": {"has_key": bool(settings.groq_key), "masked_key": mask_key(settings.groq_key)},
            "mistral": {"has_key": bool(settings.mistral_key), "masked_key": mask_key(settings.mistral_key)},
        },
    }


@app.put("/api/settings/llm")
async def api_update_llm_settings(
    update: LLMSettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    import time
    from sqlalchemy.exc import OperationalError
    for attempt in range(5):
        try:
            settings = db.query(UserLLMSettings).filter_by(user_id=user.id).first()
            if not settings:
                settings = UserLLMSettings(user_id=user.id)
                db.add(settings)
            if update.active_provider is not None:
                settings.active_provider = update.active_provider
            # Only update keys that are explicitly provided (not None)
            if update.deepseek_key is not None:
                settings.deepseek_key = update.deepseek_key or None
            if update.openai_key is not None:
                settings.openai_key = update.openai_key or None
            if update.anthropic_key is not None:
                settings.anthropic_key = update.anthropic_key or None
            if update.google_key is not None:
                settings.google_key = update.google_key or None
            if update.groq_key is not None:
                settings.groq_key = update.groq_key or None
            if update.mistral_key is not None:
                settings.mistral_key = update.mistral_key or None
            db.commit()
            return {"status": "updated"}
        except OperationalError as e:
            db.rollback()
            if "database is locked" in str(e) and attempt < 4:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise HTTPException(500, "Database busy — please try again")


@app.post("/api/settings/llm/test")
async def api_test_llm(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Test the user's active LLM configuration with a simple prompt."""
    from llm_engine import get_user_llm_config, call_llm
    provider, api_key = get_user_llm_config(db, user.id)
    if not api_key:
        raise HTTPException(400, "No API key configured")
    try:
        result = await call_llm(provider, api_key, "Say 'MonkeyKing LLM test successful!' in one line.", temperature=0.1)
        return {"provider": provider, "response": result.strip(), "status": "ok"}
    except Exception as e:
        raise HTTPException(400, f"LLM test failed: {str(e)[:200]}")


# ─── ADMIN: BULK COMPANY MANAGEMENT ────────────────────
@app.get("/api/companies/export/csv")
async def api_export_companies_csv(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export all companies as CSV (admin only)."""
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    import csv
    from io import StringIO
    from fastapi.responses import Response

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "careers_url", "category", "country"])
    for c in db.query(Company).order_by(Company.name).all():
        writer.writerow([c.id, c.name, c.careers_url, c.category, c.country])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=monkeyking_companies.csv"},
    )


@app.post("/api/companies/import/csv")
async def api_import_companies_csv(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Import/update companies from CSV (admin only). Updates existing by ID, adds new ones."""
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    import csv
    from io import StringIO

    content = await file.read()
    reader = csv.DictReader(StringIO(content.decode("utf-8")))

    updated = 0
    added = 0
    for row in reader:
        company_id = row.get("id", "").strip()
        name = row.get("name", "").strip()
        url = row.get("careers_url", "").strip()
        category = row.get("category", "other").strip()
        country = row.get("country", "India").strip()

        if not name or not url:
            continue

        if company_id and company_id.isdigit():
            existing = db.query(Company).get(int(company_id))
            if existing:
                existing.name = name
                existing.careers_url = url
                existing.category = category
                existing.country = country
                updated += 1
                continue

        # Check if company exists by name
        existing = db.query(Company).filter_by(name=name).first()
        if existing:
            existing.careers_url = url
            existing.category = category
            existing.country = country
            updated += 1
        else:
            db.add(Company(name=name, careers_url=url, category=category, country=country,
                           added_by=user.id, is_verified=False))
            added += 1

    db.commit()
    return {"updated": updated, "added": added, "total": db.query(Company).count()}


@app.post("/api/companies/{company_id}/test-url")
async def api_test_company_url(
    company_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Test if a company's careers URL is reachable (admin only)."""
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    company = db.query(Company).get(company_id)
    if not company:
        raise HTTPException(404, "Company not found")

    import httpx
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(company.careers_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            has_jobs_content = any(kw in r.text.lower() for kw in [
                "job", "career", "position", "opening", "opportunity", "hiring", "apply"
            ])
            return {
                "status": r.status_code,
                "reachable": r.status_code < 400,
                "has_jobs_content": has_jobs_content,
                "final_url": str(r.url),
                "redirect": str(r.url) != company.careers_url,
            }
    except Exception as e:
        return {
            "status": 0,
            "reachable": False,
            "has_jobs_content": False,
            "error": str(e)[:200],
        }


# ─── ADMIN: STALE JOB CLEANUP ─────────────────────────
@app.post("/api/admin/cleanup-stale-jobs")
async def api_cleanup_stale_jobs(
    days: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Archive jobs not seen for N days (admin only)."""
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
    stale = db.query(Job).filter(
        (Job.last_verified == None) | (Job.last_verified < cutoff)
    ).count()
    return {"stale_jobs": stale, "cutoff_days": days, "message": f"{stale} jobs not verified in {days} days"}


# ─── ADMIN: URL HEALTH CHECK ──────────────────────────
@app.post("/api/admin/check-urls")
async def api_check_urls(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check all company URLs and return broken ones (admin only)."""
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")

    import httpx as hx
    companies = db.query(Company).order_by(Company.name).all()
    broken = []
    checked = 0

    async with hx.AsyncClient(timeout=10, follow_redirects=True) as client:
        for c in companies[:50]:  # Check 50 at a time to avoid timeout
            checked += 1
            try:
                r = await client.get(c.careers_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                if r.status_code >= 400:
                    broken.append({"id": c.id, "name": c.name, "url": c.careers_url, "status": r.status_code})
            except Exception as e:
                broken.append({"id": c.id, "name": c.name, "url": c.careers_url, "error": str(e)[:100]})

    return {"checked": checked, "broken": len(broken), "broken_companies": broken}


# ─── EMAIL NOTIFICATIONS ──────────────────────────────
class NotificationUpdate(BaseModel):
    enabled: bool


@app.get("/api/settings/notifications")
async def api_get_notifications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current email notification preference."""
    profile = db.query(UserProfile).filter_by(user_id=user.id).first()
    if not profile:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        db.commit()
    return {"enabled": bool(profile.notifications_enabled)}


@app.post("/api/settings/notifications")
async def api_update_notifications(
    update: NotificationUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle email notifications for search results."""
    import time
    from sqlalchemy.exc import OperationalError
    for attempt in range(5):
        try:
            profile = db.query(UserProfile).filter_by(user_id=user.id).first()
            if not profile:
                profile = UserProfile(user_id=user.id)
                db.add(profile)
            profile.notifications_enabled = update.enabled
            db.commit()
            return {"status": "updated", "enabled": profile.notifications_enabled}
        except OperationalError as e:
            db.rollback()
            if "database is locked" in str(e) and attempt < 4:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise HTTPException(500, "Database busy — please try again")


# ─── AUTO-SEARCH SCHEDULING ───────────────────────────
VALID_FREQUENCIES = {"daily", "every_3_days", "weekly", "off"}


class ScheduleUpdate(BaseModel):
    frequency: str


@app.get("/api/settings/schedule")
async def api_get_schedule(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current auto-search schedule frequency."""
    profile = db.query(UserProfile).filter_by(user_id=user.id).first()
    if not profile:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        db.commit()
    return {"frequency": profile.schedule_frequency or "off"}


@app.put("/api/settings/schedule")
async def api_update_schedule(
    update: ScheduleUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set auto-search schedule frequency."""
    if update.frequency not in VALID_FREQUENCIES:
        raise HTTPException(400, f"Invalid frequency. Must be one of: {', '.join(sorted(VALID_FREQUENCIES))}")
    import time
    from sqlalchemy.exc import OperationalError
    for attempt in range(5):
        try:
            profile = db.query(UserProfile).filter_by(user_id=user.id).first()
            if not profile:
                profile = UserProfile(user_id=user.id)
                db.add(profile)
            profile.schedule_frequency = update.frequency
            db.commit()
            return {"status": "updated", "frequency": profile.schedule_frequency}
        except OperationalError as e:
            db.rollback()
            if "database is locked" in str(e) and attempt < 4:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise HTTPException(500, "Database busy — please try again")


# ─── LINKEDIN SETTINGS ────────────────────────────────
class LinkedInUpdate(BaseModel):
    url: str
    scraping_enabled: bool


@app.get("/api/settings/linkedin")
async def api_get_linkedin(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current LinkedIn settings."""
    profile = db.query(UserProfile).filter_by(user_id=user.id).first()
    if not profile:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
        db.commit()
    return {"url": profile.linkedin or "", "scraping_enabled": bool(profile.linkedin_scraping_enabled)}


@app.put("/api/settings/linkedin")
async def api_update_linkedin(
    update: LinkedInUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update LinkedIn URL and scraping preference."""
    import time
    from sqlalchemy.exc import OperationalError
    for attempt in range(5):
        try:
            profile = db.query(UserProfile).filter_by(user_id=user.id).first()
            if not profile:
                profile = UserProfile(user_id=user.id)
                db.add(profile)
            profile.linkedin = update.url
            profile.linkedin_scraping_enabled = update.scraping_enabled
            db.commit()
            return {"status": "updated"}
        except OperationalError as e:
            db.rollback()
            if "database is locked" in str(e) and attempt < 4:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise HTTPException(500, "Database busy — please try again")


# ─── LEARNING STATS ────────────────────────────────────
@app.get("/api/learning/stats")
async def api_learning_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return scan learning statistics."""
    from models import ScanHistory, VisionNavCache

    scan_history_count = db.query(ScanHistory).distinct(ScanHistory.company_id).count()
    nav_cache_count = db.query(VisionNavCache).count()

    if scan_history_count == 0 and nav_cache_count == 0:
        return {
            "companies_with_history": 0,
            "cached_nav_paths": 0,
            "message": "Learning begins after your first scan run"
        }

    return {
        "companies_with_history": scan_history_count,
        "cached_nav_paths": nav_cache_count,
        "message": f"MonkeyKing has learned scan patterns for {scan_history_count} companies"
    }


@app.get("/api/learning/preferences")
async def api_learning_preferences(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the user's learned preference affinities."""
    from models import UserPreferenceHistory, UserLearnedPreferences

    signal_count = db.query(UserPreferenceHistory).filter_by(user_id=user.id).count()
    if signal_count == 0:
        return {
            "signal_count": 0,
            "title_affinities": {"positive": [], "negative": []},
            "company_affinities": {"positive": [], "negative": []},
            "skill_affinities": {"positive": [], "negative": []},
            "message": "Save or reject jobs to teach MonkeyKing your preferences"
        }

    prefs = db.query(UserLearnedPreferences).filter_by(user_id=user.id).all()

    def top_n(pref_type: str, positive: bool, n: int = 5):
        filtered = [p for p in prefs if p.preference_type == pref_type]
        if positive:
            filtered = [p for p in filtered if p.affinity_score > 0]
            filtered.sort(key=lambda p: -p.affinity_score)
        else:
            filtered = [p for p in filtered if p.affinity_score < 0]
            filtered.sort(key=lambda p: p.affinity_score)
        return [{"key": p.preference_key, "score": round(p.affinity_score, 2),
                 "positive": p.positive_count, "negative": p.negative_count}
                for p in filtered[:n]]

    return {
        "signal_count": signal_count,
        "title_affinities": {
            "positive": top_n("title", True),
            "negative": top_n("title", False),
        },
        "company_affinities": {
            "positive": top_n("company", True),
            "negative": top_n("company", False),
        },
        "skill_affinities": {
            "positive": top_n("skill", True),
            "negative": top_n("skill", False),
        },
        "message": f"Learned from {signal_count} feedback signals"
    }


# ─── RESET SEARCH BATCHES ─────────────────────────────
@app.post("/api/jobs/search/reset")
async def api_reset_search(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reset all search runs so the next search starts from batch 1."""
    deleted = db.query(SearchRun).filter_by(user_id=user.id).delete()
    db.commit()
    return {"status": "reset", "deleted_runs": deleted, "message": "Search history cleared — next search starts from batch 1"}
