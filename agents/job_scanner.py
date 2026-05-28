"""Job Scanner Agent — Discovers jobs from company career pages."""
import json
import re
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class ScannedJob:
    title: str
    company: str
    url: str
    location: str = ""
    description: str = ""
    requirements: str = ""
    salary_range: str = ""
    job_type: str = ""
    source_page: str = ""


class JobScannerAgent:
    """
    Scans company career pages to find relevant job listings.
    
    In Kiro mode: Uses Browser MCP to navigate career pages.
    Generates search URLs and extraction instructions for the orchestrator.
    """

    def __init__(self, config: dict):
        self.target_roles = config.get("target_roles", [])
        self.keywords = config.get("keywords", [])
        self.location_pref = config.get("location_preference", "any")
        self.preferred_locations = config.get("preferred_locations", [])

    def build_search_queries(self, company: dict) -> list[dict]:
        """Build search URLs/queries for a company's career page."""
        queries = []
        base_url = company["careers_url"]
        name = company["name"]

        for role in self.target_roles:
            queries.append({
                "company": name,
                "role": role,
                "base_url": base_url,
                "search_term": role,
                "instructions": self._get_scan_instructions(name, base_url, role),
            })
        return queries

    def _get_scan_instructions(self, company: str, url: str, role: str) -> str:
        """Generate Browser MCP instructions for scanning a career page."""
        return f"""
SCAN INSTRUCTIONS for {company}:
1. Navigate to: {url}
2. Look for a search/filter input on the careers page
3. Search for: "{role}"
4. If location filter exists, set to: Any/All or Remote
5. For each job listing found:
   - Extract: job title, location, job URL, brief description
   - Only include jobs that match these keywords: {', '.join(self.keywords[:5])}
6. Click into each relevant job to get the full description
7. Return structured data for each job found
"""

    def parse_job_from_page(self, raw_text: str, company: str, url: str) -> Optional[ScannedJob]:
        """Parse job details from raw page text extracted by Browser MCP."""
        if not raw_text or len(raw_text) < 50:
            return None

        return ScannedJob(
            title=self._extract_title(raw_text),
            company=company,
            url=url,
            location=self._extract_location(raw_text),
            description=raw_text[:5000],
            requirements=self._extract_requirements(raw_text),
            job_type=self._detect_job_type(raw_text),
            source_page=url,
        )

    def _extract_title(self, text: str) -> str:
        lines = text.strip().split("\n")
        return lines[0][:200] if lines else "Unknown"

    def _extract_location(self, text: str) -> str:
        location_patterns = [
            r"(?:location|office|based in)[:\s]+([^\n,]+)",
            r"(remote|hybrid|on-?site)",
        ]
        for pattern in location_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return "Not specified"

    def _extract_requirements(self, text: str) -> str:
        req_patterns = [
            r"(?:requirements?|qualifications?|what you.?ll need|must have)[:\s]*\n([\s\S]{100,2000}?)(?:\n\n|\Z)",
            r"(?:skills?|experience)[:\s]*\n([\s\S]{100,1500}?)(?:\n\n|\Z)",
        ]
        for pattern in req_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _detect_job_type(self, text: str) -> str:
        text_lower = text.lower()
        if "remote" in text_lower:
            return "remote"
        if "hybrid" in text_lower:
            return "hybrid"
        if "on-site" in text_lower or "onsite" in text_lower:
            return "onsite"
        return "unknown"

    def is_relevant(self, title: str) -> bool:
        """Quick check if a job title is potentially relevant."""
        title_lower = title.lower()
        relevant_terms = [
            "product manager", "program manager", "project manager",
            "account manager", "product owner", "ai ", "artificial intelligence",
            "machine learning", "ml ", "platform manager", "delivery manager",
            "operations manager", "strategy manager",
        ]
        return any(term in title_lower for term in relevant_terms)
