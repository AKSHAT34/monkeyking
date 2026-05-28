"""Test why Postman Strategic Account Director scores only 0.35."""
import asyncio
from models import init_db, Job, UserProfile
from cv_parser import score_job_match
from llm_engine import get_user_llm_config

Session = init_db()
db = Session()

profile = db.query(UserProfile).filter_by(user_id=1).first()
user_profile = {
    "summary": profile.extracted_summary or "",
    "skills": profile.extracted_skills or {},
    "experience": (profile.extracted_experience or [])[:5],
    "education": profile.extracted_education or [],
    "target_roles": profile.target_roles or [],
    "years_experience": profile.years_experience or 0,
    "preferred_locations": profile.preferred_locations or [],
}

provider, api_key = get_user_llm_config(db, 1)

# Find the Postman Strategic Account Director job
job = db.query(Job).filter(Job.company == "Postman", Job.title.ilike("%Strategic Account%")).first()
if not job:
    print("Postman Strategic Account job not found, trying any Postman job...")
    job = db.query(Job).filter(Job.company == "Postman", Job.title.ilike("%Account%")).first()

if job:
    desc = job.description or ""
    print(f"Job: {job.title}")
    print(f"Company: {job.company}")
    print(f"Location: {job.location}")
    print(f"Description: {len(desc)} chars")
    print(f"Desc preview: {desc[:300]}...")
    print()

    result = asyncio.run(score_job_match(user_profile, {
        "title": job.title, "company": job.company,
        "location": job.location, "description": desc[:3000],
    }, provider=provider, api_key=api_key))

    print(f"SCORE: {result.get('score')}")
    print(f"REASON: {result.get('match_reason')}")
    print(f"MATCHED: {result.get('matched_skills', [])}")
    print(f"MISSING: {result.get('missing_skills', [])}")
else:
    print("No Postman Account job found in DB")

db.close()
