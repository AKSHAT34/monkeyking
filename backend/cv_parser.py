"""CV Parser — Extract structured data from PDF/DOCX using LLM."""
import json
import os
import httpx
import pdfplumber
from docx import Document
from pathlib import Path
from llm_engine import call_llm, get_user_llm_config, SYSTEM_DEEPSEEK_KEY


def extract_text_from_pdf(file_path: str) -> str:
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text.strip()


def extract_text_from_docx(file_path: str) -> str:
    doc = Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext in (".docx", ".doc"):
        return extract_text_from_docx(file_path)
    raise ValueError(f"Unsupported file type: {ext}")


async def call_deepseek(prompt: str, system: str = "", temperature: float = 0.2,
                        provider: str = "deepseek", api_key: str = "") -> str:
    """Backward-compatible wrapper — routes to the multi-provider engine."""
    if not api_key:
        api_key = SYSTEM_DEEPSEEK_KEY
        provider = "deepseek"
    return await call_llm(provider, api_key, prompt, system, temperature)


async def parse_cv(file_path: str, provider: str = "deepseek", api_key: str = "") -> dict:
    """Parse a CV file and extract structured data using DeepSeek."""
    raw_text = extract_text(file_path)
    if not raw_text or len(raw_text) < 50:
        return {"error": "Could not extract text from CV", "raw_text": raw_text}

    prompt = f"""Analyze this CV/resume and extract structured data. Return ONLY valid JSON.

CV TEXT:
{raw_text[:8000]}

Return this exact JSON structure:
{{
  "name": "Full Name",
  "email": "email@example.com",
  "phone": "+91...",
  "location": "City, Country",
  "linkedin": "linkedin.com/in/...",
  "summary": "2-3 sentence professional summary",
  "years_experience": 5,
  "skills": {{
    "technical": ["skill1", "skill2"],
    "tools": ["tool1", "tool2"],
    "soft_skills": ["skill1"],
    "languages": ["English", "Hindi"]
  }},
  "experience": [
    {{
      "title": "Job Title",
      "company": "Company Name",
      "location": "City",
      "period": "Jan 2020 - Present",
      "highlights": ["achievement 1", "achievement 2"]
    }}
  ],
  "education": [
    {{
      "degree": "MBA in Finance",
      "institution": "University Name",
      "period": "2018 - 2020"
    }}
  ],
  "certifications": ["Cert 1", "Cert 2"],
  "projects": [
    {{
      "name": "Project Name",
      "description": "Brief description",
      "technologies": ["tech1", "tech2"]
    }}
  ],
  "suggested_roles": [
    "Role Title 1",
    "Role Title 2",
    "Role Title 3",
    "Role Title 4",
    "Role Title 5",
    "Role Title 6",
    "Role Title 7",
    "Role Title 8"
  ]
}}

For suggested_roles: Based on the candidate's skills, experience, and education, suggest 8-12 job titles they would be a strong fit for. Be specific (e.g., "AI Product Manager" not just "Manager").
"""

    result = await call_deepseek(prompt, system="You are an expert CV parser. Return only valid JSON, no markdown.",
                                provider=provider, api_key=api_key)

    # Clean and parse JSON
    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1] if "\n" in result else result[3:]
    if result.endswith("```"):
        result = result[:-3]
    result = result.strip()

    try:
        return json.loads(result)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        start = result.find("{")
        end = result.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(result[start:end])
            except json.JSONDecodeError:
                pass
        return {"error": "Failed to parse CV", "raw_response": result[:500], "raw_text": raw_text[:2000]}


async def score_job_match(user_profile: dict, job: dict, provider: str = "deepseek", api_key: str = "") -> dict:
    """Use LLM to deeply score a job match against user profile."""
    pref_locs = user_profile.get('preferred_locations', [])
    years_exp = user_profile.get('years_experience', 0)

    # Strip HTML from job description
    import re as _re
    raw_desc = (job.get('description', '') or '')[:3000]
    clean_desc = _re.sub(r'<[^>]+>', ' ', raw_desc)
    clean_desc = _re.sub(r'&[a-z]+;', ' ', clean_desc)
    clean_desc = _re.sub(r'\s+', ' ', clean_desc).strip()

    prompt = f"""Score how well this candidate matches this job. Be realistic but fair.

CANDIDATE PROFILE:
- Summary: {user_profile.get('summary', '')}
- Skills: {json.dumps(user_profile.get('skills', {}))}
- TOTAL YEARS OF EXPERIENCE: {years_exp} years (this is the candidate's TOTAL career experience, NOT the duration of any single role)
- Recent Experience: {json.dumps(user_profile.get('experience', [])[:5])}
- Education: {json.dumps(user_profile.get('education', []))}
- Target Roles: {json.dumps(user_profile.get('target_roles', []))}
- Preferred Locations: {json.dumps(pref_locs)}

JOB:
- Title: {job.get('title', '')}
- Company: {job.get('company', '')}
- Location: {job.get('location', '')}
- Description: {clean_desc}

SCORING RULES:

1. EXPERIENCE FIT:
   - The candidate has {years_exp} TOTAL years of experience across all roles combined.
   - Do NOT confuse individual role duration with total experience.
   - If the job needs 5-10 years and candidate has {years_exp} years → good fit.
   - Only penalize if the job clearly needs much more experience than {years_exp} years.
   - "Director" level with {years_exp} years is reasonable. "VP" level might need more.

2. LOCATION FIT:
   - Candidate prefers: {json.dumps(pref_locs)}
   - If job location matches any preferred location → no penalty.
   - If job is Remote → acceptable.
   - If job is in a completely different country and not remote → reduce score by 0.2.

3. ROLE & SKILLS FIT:
   - Compare the candidate's skills and experience to the job requirements.
   - Value transferable skills (e.g., account management experience transfers to sales roles).
   - The candidate's target roles are: {json.dumps(user_profile.get('target_roles', [])[:5])}

4. SCORE RANGES:
   - 0.8-1.0: Near-perfect match (right level, right location, strong skill overlap)
   - 0.6-0.8: Good match (location OK, most skills match, experience level reasonable)
   - 0.4-0.6: Decent match (some gaps but candidate could grow into the role)
   - 0.2-0.4: Weak match (significant gaps in skills or experience)
   - 0.0-0.2: No match (completely different field or wrong location)

Return ONLY valid JSON:
{{
  "score": 0.85,
  "match_reason": "2-3 sentences explaining the match, mentioning experience fit and location fit explicitly",
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill1"],
  "relevance_summary": "1 paragraph on why the candidate should or should not apply"
}}
"""
    result = await call_deepseek(prompt, system="You are an expert recruiter. Return only valid JSON.",
                                provider=provider, api_key=api_key)
    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1] if "\n" in result else result[3:]
    if result.endswith("```"):
        result = result[:-3]
    try:
        return json.loads(result.strip())
    except json.JSONDecodeError:
        start = result.find("{")
        end = result.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(result[start:end])
            except Exception:
                pass
        return {"score": 0.0, "match_reason": "Could not analyze", "matched_skills": [], "missing_skills": []}
