"""Dashboard API — FastAPI backend for MonkeyKing dashboard."""
import json
import sys
import os
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path

from db.models import init_db, Job, TailoredCV, Application, Account, RunLog

app = FastAPI(title="MonkeyKing Dashboard", version="1.0.0")

# Database session
Session = init_db()


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard HTML."""
    html_path = Path(__file__).parent / "index.html"
    return html_path.read_text()


@app.get("/api/stats")
async def get_stats():
    """Get overall pipeline statistics."""
    session = Session()
    try:
        total = session.query(Job).count()
        matched = session.query(Job).filter(Job.match_score >= 0.6).count()
        cvs = session.query(TailoredCV).count()
        applied = session.query(Application).filter_by(status="submitted").count()
        dry_run = session.query(Application).filter_by(status="dry_run").count()
        failed = session.query(Application).filter_by(status="failed").count()
        skipped = session.query(Application).filter_by(status="skipped").count()
        accounts = session.query(Account).count()
        pending = (session.query(Job)
                   .filter(Job.status.in_(["matched", "cv_created"]))
                   .filter(Job.match_score >= 0.6).count())

        return {
            "total_jobs_found": total,
            "matched_jobs": matched,
            "cvs_tailored": cvs,
            "applications_submitted": applied,
            "applications_dry_run": dry_run,
            "applications_failed": failed,
            "applications_skipped": skipped,
            "accounts_created": accounts,
            "pending_apply": pending,
            "last_updated": datetime.utcnow().isoformat(),
        }
    finally:
        session.close()


@app.get("/api/activity")
async def get_activity(limit: int = 20):
    """Get recent activity feed — latest applications and job discoveries."""
    session = Session()
    try:
        # Recent applications
        recent_apps = (
            session.query(Application, Job)
            .join(Job)
            .order_by(Application.created_at.desc())
            .limit(limit)
            .all()
        )
        activities = []
        for a, j in recent_apps:
            activities.append({
                "type": "application",
                "title": j.title,
                "company": j.company,
                "status": a.status,
                "error": a.error_message,
                "time": (a.submitted_at or a.created_at).isoformat() if (a.submitted_at or a.created_at) else None,
            })

        # Recent job discoveries
        recent_jobs = (
            session.query(Job)
            .order_by(Job.discovered_at.desc())
            .limit(10)
            .all()
        )
        for j in recent_jobs:
            activities.append({
                "type": "discovery",
                "title": j.title,
                "company": j.company,
                "status": j.status,
                "score": j.match_score,
                "time": j.discovered_at.isoformat() if j.discovered_at else None,
            })

        # Sort by time descending
        activities.sort(key=lambda x: x.get("time") or "", reverse=True)
        return activities[:limit]
    finally:
        session.close()


@app.get("/api/emails")
async def check_emails():
    """Check Gmail for application confirmation emails."""
    try:
        from config.loader import Config
        from agents.email_agent import EmailAgent
        config = Config()
        email_agent = EmailAgent(config.email_config)
        if not email_agent.connect():
            return {"status": "error", "message": "Could not connect to Gmail"}
        emails = email_agent.get_recent_emails(count=20)
        email_agent.disconnect()

        # Filter for job-related emails
        job_keywords = ["application", "applied", "received", "thank you for applying",
                        "confirmation", "candidate", "position", "interview", "resume"]
        job_emails = []
        for e in emails:
            subject_lower = (e.get("subject") or "").lower()
            if any(kw in subject_lower for kw in job_keywords):
                e["is_job_related"] = True
                job_emails.append(e)
            else:
                e["is_job_related"] = False

        return {
            "status": "ok",
            "total_recent": len(emails),
            "job_related": len(job_emails),
            "emails": emails,
            "job_emails": job_emails,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/jobs")
async def get_jobs(status: str = None, limit: int = 100):
    """Get job listings with optional status filter."""
    session = Session()
    try:
        query = session.query(Job).order_by(Job.match_score.desc())
        if status:
            query = query.filter_by(status=status)
        jobs = query.limit(limit).all()
        return [
            {
                "id": j.id,
                "title": j.title,
                "company": j.company,
                "location": j.location,
                "url": j.url,
                "match_score": j.match_score,
                "matched_skills": json.loads(j.matched_skills) if j.matched_skills else [],
                "missing_skills": json.loads(j.missing_skills) if j.missing_skills else [],
                "status": j.status,
                "discovered_at": j.discovered_at.isoformat() if j.discovered_at else None,
                "applied_at": j.applied_at.isoformat() if j.applied_at else None,
            }
            for j in jobs
        ]
    finally:
        session.close()


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: int):
    """Get a single job with full details."""
    session = Session()
    try:
        job = session.query(Job).get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "url": job.url,
            "description": job.description,
            "requirements": job.requirements,
            "match_score": job.match_score,
            "matched_skills": json.loads(job.matched_skills) if job.matched_skills else [],
            "missing_skills": json.loads(job.missing_skills) if job.missing_skills else [],
            "status": job.status,
        }
    finally:
        session.close()


@app.get("/api/applications")
async def get_applications(limit: int = 100):
    """Get application history."""
    session = Session()
    try:
        apps = (
            session.query(Application, Job)
            .join(Job)
            .order_by(Application.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": a.id,
                "job_title": j.title,
                "company": j.company,
                "status": a.status,
                "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
                "error": a.error_message,
            }
            for a, j in apps
        ]
    finally:
        session.close()


@app.get("/api/cvs")
async def get_tailored_cvs(limit: int = 50):
    """Get list of tailored CVs."""
    session = Session()
    try:
        cvs = (
            session.query(TailoredCV, Job)
            .join(Job)
            .order_by(TailoredCV.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": cv.id,
                "job_title": j.title,
                "company": j.company,
                "file_path": cv.file_path,
                "ats_score": cv.ats_score,
                "created_at": cv.created_at.isoformat() if cv.created_at else None,
            }
            for cv, j in cvs
        ]
    finally:
        session.close()
