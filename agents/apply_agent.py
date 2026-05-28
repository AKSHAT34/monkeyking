"""Apply Agent — Fills forms and submits job applications via Browser MCP."""
import json
from typing import Optional


class ApplyAgent:
    """
    Generates Browser MCP instructions for filling out and submitting
    job applications on company career portals.
    """

    def __init__(self, user_config: dict, cv_data: dict):
        self.user = user_config
        self.cv_data = cv_data

    def generate_application_instructions(self, job: dict, cv_file_path: str,
                                           cover_letter: str = "") -> str:
        """Generate step-by-step Browser MCP instructions for applying."""
        name = self.user.get("name", "")
        email = self.user.get("email", "")
        phone = self.user.get("phone", "")

        return f"""
JOB APPLICATION INSTRUCTIONS:

TARGET: {job.get('title', '')} at {job.get('company', '')}
URL: {job.get('url', '')}

STEP 1 — Navigate to the job page:
- Go to: {job.get('url', '')}
- Look for "Apply", "Apply Now", "Submit Application" button
- Click it

STEP 2 — Login/Account check:
- If prompted to login, use email: {email}
- If no account exists, follow account creation flow first

STEP 3 — Fill the application form:
Personal Information:
  - Full Name: {name}
  - Email: {email}
  - Phone: {phone}
  - Location: {self.user.get('location', '')}
  - LinkedIn: {self.user.get('linkedin', '')}

STEP 4 — Upload Resume/CV:
  - Upload file: {cv_file_path}
  - This is the ATS-tailored CV for this specific job

STEP 5 — Cover Letter (if field exists):
  - Paste this cover letter:
{cover_letter[:2000] if cover_letter else '[Generate using CV Tailor Agent]'}

STEP 6 — Answer screening questions:
  - Use the SCREENING QUESTION HANDLER below for common questions
  - For unknown questions, use LLM to generate answers based on CV data

STEP 7 — Review and Submit:
  - Review all filled fields
  - Take a screenshot before submitting
  - Click Submit/Apply
  - Confirm submission (look for confirmation message/page)
  - Take a screenshot of confirmation

STEP 8 — Report result:
  - Return: submitted, failed, or needs_manual
  - Include any error messages
"""

    def answer_screening_question(self, question: str) -> str:
        """Answer common screening questions using CV data."""
        q = question.lower()
        cv = self.cv_data

        # Years of experience
        if "years" in q and "experience" in q:
            return "9"

        # Work authorization
        if "authorized" in q or "work authorization" in q or "visa" in q:
            return "Yes"  # Adjust based on actual status

        # Willing to relocate
        if "relocate" in q:
            return "Yes"

        # Remote work
        if "remote" in q:
            return "Yes"

        # Salary expectations
        if "salary" in q or "compensation" in q or "pay" in q:
            return "Open to discussion based on the total compensation package"

        # Start date
        if "start" in q and "date" in q:
            return "Available to start within 2-4 weeks of offer"

        # Education
        if "degree" in q or "education" in q:
            return "MBA in Finance (<University-1> University), BSc Business Administration (<University-2>), BSc Computer Science (<University-3>)"

        # Languages
        if "language" in q:
            return "English (Native), French (Native), Hindi (Native), German (Basic)"

        # Sponsorship
        if "sponsor" in q:
            return "Open to discuss"

        # Current company
        if "current" in q and ("company" in q or "employer" in q):
            return "Amazon"

        # Notice period
        if "notice" in q:
            return "30 days"

        # LinkedIn
        if "linkedin" in q:
            return cv.get("personal", {}).get("linkedin", "")

        # Default — needs LLM
        return f"[NEEDS_LLM_ANSWER]{question}[/NEEDS_LLM_ANSWER]"

    def get_screening_answer_prompt(self, question: str) -> str:
        """Generate LLM prompt for answering a screening question."""
        cv = self.cv_data
        return f"""Answer this job application screening question based on the candidate's profile.
Be concise, professional, and honest. Max 200 words.

QUESTION: {question}

CANDIDATE PROFILE:
- Name: {cv['personal']['name']}
- Current Role: Strategic Account Manager at Amazon
- Experience: 9+ years in AI platforms, account management, revenue growth
- Education: MBA Finance, BSc Business Admin, BSc Computer Science
- Key Skills: AI Agent design, Product Management, Agile/Scrum, Data Analysis
- Languages: English, French, Hindi (all native), German (basic)
- Location: Bangalore, India (open to relocate)

Answer:"""
