"""CV Tailor Agent — Rewrites CV for ATS optimization per job."""
import json
import os
from datetime import datetime
from pathlib import Path


class CVTailorAgent:
    """
    Takes base CV data + job description → generates ATS-optimized CV.
    
    ATS Strategy:
    - Mirror exact keywords from job description
    - Front-load relevant experience
    - Quantify achievements with metrics
    - Use standard section headers (Experience, Education, Skills)
    - No tables, columns, images, or fancy formatting
    - Clean plain-text friendly structure
    """

    def __init__(self, cv_data: dict, llm_engine=None):
        self.cv_data = cv_data
        self.llm = llm_engine
        self.output_dir = Path(__file__).parent.parent / "data" / "tailored_cvs"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_tailoring_prompt(self, job_title: str, job_description: str,
                                   company: str, matched_skills: list,
                                   missing_skills: list) -> str:
        """Generate the LLM prompt to tailor the CV."""
        cv = self.cv_data
        experience_text = self._format_experience()
        projects_text = self._format_projects()
        education_text = self._format_education()
        skills_text = self._format_skills()
        certs_text = ", ".join(cv.get("certificates", []))

        return f"""You are an expert ATS resume optimizer. Rewrite this CV to maximize 
ATS score for the target job. Follow these rules STRICTLY:

TARGET JOB: {job_title} at {company}
JOB DESCRIPTION:
{job_description[:4000]}

KEYWORDS TO INCLUDE (from job posting): {', '.join(matched_skills[:15])}
SKILLS TO ADDRESS (currently missing): {', '.join(missing_skills[:10])}

CANDIDATE DATA:
Name: {cv['personal']['name']}
Current Title: {cv['personal']['title']}
Email: {cv['personal']['email']}
Phone: {cv['personal']['phone']}
Location: {cv['personal']['location']}
LinkedIn: {cv['personal'].get('linkedin', '')}

SUMMARY: {cv.get('summary', '')}

EXPERIENCE:
{experience_text}

PROJECTS:
{projects_text}

EDUCATION:
{education_text}

SKILLS:
{skills_text}

CERTIFICATES: {certs_text}

LANGUAGES: {', '.join(cv.get('languages', []))}

ATS OPTIMIZATION RULES:
1. Rewrite the summary to mirror the job description language exactly
2. Reorder experience bullets to prioritize relevance to THIS job
3. Add keywords from the job posting naturally into experience descriptions
4. Use standard headers: SUMMARY, EXPERIENCE, PROJECTS, EDUCATION, SKILLS, CERTIFICATIONS
5. Keep all metrics and numbers from original CV
6. NO tables, NO columns, NO images, NO icons
7. Use simple bullet points (-)
8. Keep it to 2 pages max
9. For missing skills, weave them in where the candidate has adjacent experience
10. Make the title line match or closely mirror the job title

Return the COMPLETE tailored CV as clean plain text, ready to be converted to PDF.
Start with the candidate name, then contact info, then sections.
"""

    def _format_experience(self) -> str:
        lines = []
        for exp in self.cv_data.get("experience", []):
            lines.append(f"{exp['title']} | {exp['company']} | {exp['location']} | {exp['period']}")
            for h in exp.get("highlights", []):
                lines.append(f"  - {h}")
            lines.append("")
        return "\n".join(lines)

    def _format_projects(self) -> str:
        lines = []
        for proj in self.cv_data.get("projects", []):
            lines.append(f"{proj['name']} | {proj.get('role', '')} | {proj.get('company', '')}")
            lines.append(f"  {proj.get('description', '')}")
            lines.append("")
        return "\n".join(lines)

    def _format_education(self) -> str:
        lines = []
        for edu in self.cv_data.get("education", []):
            lines.append(f"{edu['degree']} | {edu['institution']} | {edu['period']}")
        return "\n".join(lines)

    def _format_skills(self) -> str:
        lines = []
        for cat, items in self.cv_data.get("skills", {}).items():
            label = cat.replace("_", " ").title()
            lines.append(f"{label}: {', '.join(items)}")
        return "\n".join(lines)

    def save_tailored_cv(self, cv_text: str, company: str, job_title: str) -> str:
        """Save tailored CV as a text file. Returns file path."""
        safe_company = "".join(c if c.isalnum() else "_" for c in company)
        safe_title = "".join(c if c.isalnum() else "_" for c in job_title)[:50]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"CV_{safe_company}_{safe_title}_{timestamp}.txt"
        filepath = self.output_dir / filename

        with open(filepath, "w") as f:
            f.write(cv_text)

        return str(filepath)

    def generate_cover_letter_prompt(self, job_title: str, company: str,
                                      job_description: str) -> str:
        """Generate prompt for a tailored cover letter."""
        cv = self.cv_data
        return f"""Write a concise, professional cover letter for:

POSITION: {job_title} at {company}
JOB DESCRIPTION: {job_description[:2000]}

CANDIDATE: {cv['personal']['name']}
CURRENT ROLE: {cv.get('experience', [{}])[0].get('title', '')} at {cv.get('experience', [{}])[0].get('company', '')}
KEY ACHIEVEMENTS:
- Owned $40M+ GMV portfolio at Amazon with 127% YoY growth
- Built AI platforms with 2,200+ users and 100,000+ logins
- Designed AI agents automating queries across 47 internal tools
- Led delivery of AI-driven automation saving 60-80 hours per manager

RULES:
1. Max 300 words
2. Open with a specific hook about the company
3. Connect candidate's AI + product experience to the role
4. Include 2-3 quantified achievements
5. Close with enthusiasm and call to action
6. Professional but not generic — show personality
"""
