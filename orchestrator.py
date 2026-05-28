"""
MonkeyKing Orchestrator — Coordinates all agents for the job application pipeline.

This is the brain that runs inside Kiro's agentic chat.
It coordinates: Scan → Match → Tailor CV → Create Account → Apply
"""
import json
import os
from datetime import datetime
from pathlib import Path

from config.loader import Config
from agents.job_scanner import JobScannerAgent
from agents.job_matcher import JobMatcherAgent
from agents.cv_tailor import CVTailorAgent
from agents.email_agent import EmailAgent
from agents.account_creator import AccountCreatorAgent
from agents.apply_agent import ApplyAgent
from agents.llm_engine import LLMEngine
from db.models import init_db, Job, TailoredCV, Application, Account, RunLog


class MonkeyKingOrchestrator:
    """Main orchestrator that drives the entire pipeline."""

    def __init__(self):
        self.config = Config()
        self.llm = LLMEngine(self.config.llm_config)
        self.scanner = JobScannerAgent(self.config.job_preferences)
        self.matcher = JobMatcherAgent(self.config.cv_data, self.llm)
        self.tailor = CVTailorAgent(self.config.cv_data, self.llm)
        self.email = EmailAgent(self.config.email_config)
        self.account_creator = AccountCreatorAgent(self.config.user, self.email)
        self.applier = ApplyAgent(self.config.user, self.config.cv_data)

        # Initialize database
        os.makedirs(str(Path(__file__).parent / "data"), exist_ok=True)
        self.Session = init_db()

    def run_full_pipeline(self) -> dict:
        """
        Execute the full pipeline. Returns a summary.
        In Kiro mode, this generates instructions for the agentic chat.
        """
        summary = {
            "started_at": datetime.utcnow().isoformat(),
            "companies_to_scan": len(self.config.target_companies),
            "phases": [],
        }

        # Phase 1: Generate scan instructions
        scan_plans = self._phase_scan()
        summary["phases"].append({"scan": f"{len(scan_plans)} search queries generated"})

        return summary

    def _phase_scan(self) -> list:
        """Phase 1: Generate scan plans for all target companies."""
        all_queries = []
        for company in self.config.target_companies:
            queries = self.scanner.build_search_queries(company)
            all_queries.extend(queries)
        return all_queries

    def process_scanned_job(self, title: str, company: str, url: str,
                             description: str, location: str = "",
                             requirements: str = "") -> dict:
        """Process a single scanned job — score it and store if relevant."""
        session = self.Session()
        try:
            # Check if already exists
            existing = session.query(Job).filter_by(url=url).first()
            if existing:
                return {"status": "duplicate", "job_id": existing.id}

            # Score the job
            score_result = self.matcher.score_job(title, description, requirements)

            # Store in database
            job = Job(
                title=title,
                company=company,
                location=location,
                url=url,
                description=description[:5000],
                requirements=requirements[:3000],
                match_score=score_result["score"],
                matched_skills=json.dumps(score_result["matched_skills"]),
                missing_skills=json.dumps(score_result["missing_skills"]),
                status="matched" if score_result["score"] >= self.config.job_preferences.get("min_match_score", 0.6) else "found",
            )
            session.add(job)
            session.commit()

            return {
                "status": "matched" if job.status == "matched" else "low_score",
                "job_id": job.id,
                "score": score_result["score"],
                "matched_skills": score_result["matched_skills"][:10],
            }
        finally:
            session.close()

    def get_top_matches(self, limit: int = 50) -> list[dict]:
        """Get top matching jobs that haven't been applied to yet."""
        session = self.Session()
        try:
            jobs = (
                session.query(Job)
                .filter(Job.status.in_(["matched", "cv_created"]))
                .filter(Job.match_score >= self.config.job_preferences.get("min_match_score", 0.6))
                .order_by(Job.match_score.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": j.id, "title": j.title, "company": j.company,
                    "location": j.location, "url": j.url, "score": j.match_score,
                    "status": j.status,
                }
                for j in jobs
            ]
        finally:
            session.close()

    def generate_tailored_cv(self, job_id: int) -> dict:
        """Generate a tailored CV for a specific job."""
        session = self.Session()
        try:
            job = session.query(Job).get(job_id)
            if not job:
                return {"error": "Job not found"}

            matched = json.loads(job.matched_skills) if job.matched_skills else []
            missing = json.loads(job.missing_skills) if job.missing_skills else []

            # Generate the tailoring prompt (to be sent to Kiro/LLM)
            prompt = self.tailor.generate_tailoring_prompt(
                job.title, job.description, job.company, matched, missing
            )

            # Also generate cover letter prompt
            cl_prompt = self.tailor.generate_cover_letter_prompt(
                job.title, job.company, job.description
            )

            job.status = "cv_created"
            session.commit()

            return {
                "job_id": job_id,
                "cv_prompt": prompt,
                "cover_letter_prompt": cl_prompt,
                "company": job.company,
                "title": job.title,
            }
        finally:
            session.close()

    def save_tailored_cv_result(self, job_id: int, cv_text: str) -> dict:
        """Save the LLM-generated tailored CV."""
        session = self.Session()
        try:
            job = session.query(Job).get(job_id)
            if not job:
                return {"error": "Job not found"}

            filepath = self.tailor.save_tailored_cv(cv_text, job.company, job.title)

            cv_record = TailoredCV(
                job_id=job_id,
                file_path=filepath,
                tailored_summary=cv_text[:500],
            )
            session.add(cv_record)
            session.commit()

            return {"job_id": job_id, "cv_path": filepath}
        finally:
            session.close()

    def generate_apply_instructions(self, job_id: int) -> dict:
        """Generate application instructions for a job."""
        session = self.Session()
        try:
            job = session.query(Job).get(job_id)
            if not job:
                return {"error": "Job not found"}

            cv_record = session.query(TailoredCV).filter_by(job_id=job_id).first()
            cv_path = cv_record.file_path if cv_record else ""

            job_dict = {
                "title": job.title, "company": job.company,
                "url": job.url, "location": job.location,
            }

            # Application instructions
            apply_instructions = self.applier.generate_application_instructions(
                job_dict, cv_path
            )

            # Account creation instructions (if needed)
            account_plan = self.account_creator.plan_account_creation(
                job.company, job.source_page or job.url
            )

            return {
                "job_id": job_id,
                "apply_instructions": apply_instructions,
                "account_instructions": account_plan.instructions,
                "verification_instructions": self.account_creator.get_verification_instructions(
                    job.company, job.source_page or job.url
                ),
            }
        finally:
            session.close()

    def record_application(self, job_id: int, status: str, error: str = "") -> dict:
        """Record the result of an application attempt."""
        session = self.Session()
        try:
            job = session.query(Job).get(job_id)
            if not job:
                return {"error": "Job not found"}

            app = Application(
                job_id=job_id,
                status=status,
                error_message=error,
                submitted_at=datetime.utcnow() if status == "submitted" else None,
            )
            session.add(app)

            job.status = "applied" if status == "submitted" else "error"
            job.applied_at = datetime.utcnow() if status == "submitted" else None
            session.commit()

            return {"job_id": job_id, "application_status": status}
        finally:
            session.close()

    def get_dashboard_stats(self) -> dict:
        """Get stats for the dashboard."""
        session = self.Session()
        try:
            total_jobs = session.query(Job).count()
            matched_jobs = session.query(Job).filter(Job.match_score >= 0.6).count()
            cvs_created = session.query(TailoredCV).count()
            applied = session.query(Application).filter_by(status="submitted").count()
            failed = session.query(Application).filter_by(status="failed").count()
            accounts = session.query(Account).count()

            return {
                "total_jobs_found": total_jobs,
                "matched_jobs": matched_jobs,
                "cvs_tailored": cvs_created,
                "applications_submitted": applied,
                "applications_failed": failed,
                "accounts_created": accounts,
            }
        finally:
            session.close()
