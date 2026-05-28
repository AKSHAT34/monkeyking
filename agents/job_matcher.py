"""Job Matcher Agent — Scores jobs against CV using keyword + semantic matching."""
import json
import re
from typing import Optional


class JobMatcherAgent:
    """
    Scores job listings against the user's CV data.
    Uses keyword overlap + LLM-based semantic scoring.
    """

    def __init__(self, cv_data: dict, llm_engine=None):
        self.cv_data = cv_data
        self.llm = llm_engine
        self._build_skill_index()

    def _build_skill_index(self):
        """Flatten all skills from CV into a searchable set."""
        self.all_skills = set()
        skills = self.cv_data.get("skills", {})
        for category, skill_list in skills.items():
            for skill in skill_list:
                self.all_skills.add(skill.lower())
                # Also add individual words for partial matching
                for word in skill.lower().split():
                    if len(word) > 3:
                        self.all_skills.add(word)

        # Add experience keywords
        for exp in self.cv_data.get("experience", []):
            for h in exp.get("highlights", []):
                for word in re.findall(r'\b[a-zA-Z]{4,}\b', h.lower()):
                    self.all_skills.add(word)

        # Add project keywords
        for proj in self.cv_data.get("projects", []):
            desc = proj.get("description", "")
            for word in re.findall(r'\b[a-zA-Z]{4,}\b', desc.lower()):
                self.all_skills.add(word)

    def score_job(self, job_title: str, job_description: str, requirements: str = "") -> dict:
        """Score a job against the CV. Returns score 0-1 and details."""
        full_text = f"{job_title} {job_description} {requirements}".lower()
        job_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', full_text))

        # Keyword overlap score
        matched = self.all_skills & job_words
        if not job_words:
            return {"score": 0, "matched_skills": [], "missing_skills": []}

        keyword_score = min(len(matched) / max(len(job_words) * 0.3, 1), 1.0)

        # Title relevance boost
        title_boost = self._title_relevance(job_title)

        # Combined score
        score = round(min(keyword_score * 0.7 + title_boost * 0.3, 1.0), 3)

        # Identify missing skills from requirements
        req_words = set(re.findall(r'\b[a-zA-Z]{4,}\b', requirements.lower()))
        missing = req_words - self.all_skills
        # Filter to meaningful missing skills
        stop_words = {"with", "that", "this", "from", "have", "will", "your", "about",
                       "work", "team", "role", "able", "must", "years", "experience",
                       "strong", "good", "excellent", "required", "preferred"}
        missing = [s for s in missing if s not in stop_words][:15]

        return {
            "score": score,
            "matched_skills": sorted(list(matched))[:20],
            "missing_skills": missing,
        }

    def _title_relevance(self, title: str) -> float:
        """Score how relevant a job title is to target roles."""
        title_lower = title.lower()
        high_match = ["ai product manager", "ai program manager", "ai project manager",
                      "ai account manager", "ai platform manager"]
        medium_match = ["product manager", "program manager", "project manager",
                        "account manager", "product owner", "delivery manager"]
        low_match = ["ai ", "machine learning", "artificial intelligence",
                     "strategy manager", "operations manager"]

        for term in high_match:
            if term in title_lower:
                return 1.0
        for term in medium_match:
            if term in title_lower:
                return 0.7
        for term in low_match:
            if term in title_lower:
                return 0.4
        return 0.1

    def get_llm_scoring_prompt(self, job_title: str, job_description: str) -> str:
        """Generate a prompt for LLM-based deep scoring (used via Kiro)."""
        cv_summary = self.cv_data.get("summary", "")
        skills_flat = []
        for cat, items in self.cv_data.get("skills", {}).items():
            skills_flat.extend(items)

        return f"""Score this job match from 0.0 to 1.0 for this candidate.

CANDIDATE SUMMARY:
{cv_summary}

KEY SKILLS: {', '.join(skills_flat)}

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description[:3000]}

Return ONLY a JSON object:
{{"score": 0.X, "reasoning": "brief explanation", "matched_skills": ["skill1", "skill2"], "missing_skills": ["skill1"]}}
"""
