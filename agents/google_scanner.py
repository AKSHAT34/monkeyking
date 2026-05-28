"""
Google Search Scanner — Finds jobs via Google search instead of crawling career pages.

Much faster and more reliable than crawling individual career sites.
Uses Google search queries like: "AI Product Manager" site:company.com/careers
"""
import asyncio
import json
import re
import sys
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.loader import Config
from config.profile_loader import ProfileLoader
from db.models import init_db, Job
from agents.job_matcher import JobMatcherAgent


class GoogleScanner:
    """Finds jobs via Google search — faster than crawling each career page."""

    def __init__(self, max_concurrent: int = 5, headless: bool = True):
        self.config = Config()
        self.profile = ProfileLoader.get_active_profile()
        self.max_concurrent = max_concurrent
        self.headless = headless
        self.Session = init_db()
        self.matcher = JobMatcherAgent(self.profile)
        self.roles = self.profile["job_preferences"]["target_roles"]
        self.min_score = self.profile["job_preferences"].get("min_match_score", 0.6)
        self.results = {"searched": 0, "found": 0, "matched": 0, "errors": 0}

    def _build_google_queries(self) -> list[dict]:
        """Build Google search queries for job discovery."""
        queries = []
        # Direct job search queries
        role_queries = [
            "AI Product Manager India",
            "AI Program Manager India",
            "AI Project Manager India",
            "Product Manager AI ML India",
            "Technical Program Manager AI India",
            "Strategic Account Manager AI India",
            "Product Owner AI platforms India",
            "Senior Product Manager India",
            "Product Manager enterprise India",
            "AI Operations Manager India",
            "Product Manager data India remote",
            "Program Manager technology India Bangalore",
            "AI Product Manager Bangalore",
            "AI Product Manager Mumbai",
            "AI Product Manager Hyderabad",
            "Product Manager AI startup India",
            "Product Manager machine learning India",
            "AI Product Manager GCC India",
        ]

        for rq in role_queries:
            # Google Jobs search
            queries.append({
                "query": rq,
                "url": f"https://www.google.com/search?q={quote_plus(rq + ' jobs apply')}&ibp=htl;jobs",
                "type": "google_jobs",
            })
            # Regular Google search for career pages
            queries.append({
                "query": rq,
                "url": f"https://www.google.com/search?q={quote_plus(rq + ' careers apply 2025 2026')}",
                "type": "google_web",
            })

        # Company-specific searches
        companies = self.config.target_companies
        for company in companies[:100]:  # Top 100 companies
            name = company["name"]
            for role in self.roles[:3]:  # Top 3 roles per company
                queries.append({
                    "query": f"{role} {name}",
                    "url": f"https://www.google.com/search?q={quote_plus(f'{role} {name} careers apply')}",
                    "type": "company_search",
                    "company": name,
                })

        return queries

    async def run(self):
        """Run the Google-powered job scanner."""
        from playwright.async_api import async_playwright

        queries = self._build_google_queries()
        print(f"\n🐵 MonkeyKing Google Scanner")
        print(f"   Search queries: {len(queries)}")
        print(f"   Concurrent: {self.max_concurrent}")
        print()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            semaphore = asyncio.Semaphore(self.max_concurrent)

            # Process in batches to avoid Google rate limiting
            batch_size = 10
            for i in range(0, len(queries), batch_size):
                batch = queries[i:i + batch_size]
                tasks = [
                    self._search(browser, semaphore, q)
                    for q in batch
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
                # Small delay between batches to avoid rate limiting
                await asyncio.sleep(2)

                # Progress update
                print(f"   Progress: {min(i+batch_size, len(queries))}/{len(queries)} queries | "
                      f"Found: {self.results['found']} | Matched: {self.results['matched']}")

            await browser.close()

        print(f"\n--- Google Scan Results ---")
        print(f"  Queries searched: {self.results['searched']}")
        print(f"  Jobs found: {self.results['found']}")
        print(f"  Jobs matched: {self.results['matched']}")
        print(f"  Errors: {self.results['errors']}")
        return self.results

    async def _search(self, browser, semaphore, query: dict):
        """Execute a single Google search and extract job links."""
        async with semaphore:
            self.results["searched"] += 1
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                await page.goto(query["url"], wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(1500)

                # Extract job links from Google results
                links = await page.evaluate("""() => {
                    const results = [];
                    // Google search result links
                    const anchors = document.querySelectorAll('a[href]');
                    for (const a of anchors) {
                        const href = a.href || '';
                        const text = a.textContent?.trim() || '';
                        // Filter for job-related links
                        if (text.length > 15 && text.length < 300 &&
                            !href.includes('google.com') &&
                            !href.includes('youtube.com') &&
                            !href.includes('wikipedia.org') &&
                            (href.includes('career') || href.includes('job') ||
                             href.includes('lever.co') || href.includes('greenhouse') ||
                             href.includes('ashby') || href.includes('workday') ||
                             href.includes('smartrecruiters') || href.includes('apply') ||
                             href.includes('position') || href.includes('opening'))) {
                            results.push({title: text.substring(0, 200), url: href});
                        }
                    }
                    return results;
                }""")

                company = query.get("company", "")
                for link in links:
                    title = self._clean_title(link["title"])
                    if not title or len(title) < 10:
                        continue

                    # Detect company from URL if not specified
                    if not company:
                        company = self._detect_company(link["url"])

                    if company and self._is_relevant(title):
                        self._store_job({
                            "title": title,
                            "company": company,
                            "url": link["url"],
                            "location": "India",
                            "description": title,
                        })

            except Exception as e:
                self.results["errors"] += 1
            finally:
                await context.close()

    def _clean_title(self, raw: str) -> str:
        """Clean up a job title extracted from Google results."""
        # Remove common suffixes
        for suffix in ["| LinkedIn", "| Indeed", "| Glassdoor", "| Naukri",
                       "- LinkedIn", "- Indeed", "- Glassdoor", "- Naukri",
                       "Apply now", "Apply Now"]:
            raw = raw.replace(suffix, "")
        return raw.strip()[:200]

    def _detect_company(self, url: str) -> str:
        """Try to detect company name from URL."""
        url_lower = url.lower()
        # Map of URL patterns to company names
        known = {
            "google.com/about/careers": "Google",
            "careers.microsoft.com": "Microsoft",
            "amazon.jobs": "Amazon",
            "metacareers.com": "Meta",
            "jobs.apple.com": "Apple",
            "careers.salesforce.com": "Salesforce",
            "openai.com/careers": "OpenAI",
            "anthropic.com/careers": "Anthropic",
            "flipkartcareers": "Flipkart",
            "careers.swiggy": "Swiggy",
            "zomato.com/careers": "Zomato",
            "phonepe.com/careers": "PhonePe",
            "careers.cred": "CRED",
            "razorpay.com/careers": "Razorpay",
            "freshworks.com": "Freshworks",
            "zoho.com/careers": "Zoho",
            "postman.com": "Postman",
            "lever.co": "",  # Need to extract from URL path
            "greenhouse.io": "",
            "ashbyhq.com": "",
        }
        for pattern, name in known.items():
            if pattern in url_lower:
                return name
        # Try to extract from domain
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.replace("www.", "")
            parts = domain.split(".")
            if parts:
                return parts[0].title()
        except Exception:
            pass
        return ""

    def _is_relevant(self, title: str) -> bool:
        """Quick relevance check."""
        t = title.lower()
        terms = ["product manager", "program manager", "project manager",
                 "account manager", "product owner", "ai ", "artificial intelligence",
                 "machine learning", "ml ", "platform manager", "delivery manager",
                 "operations manager", "strategy manager", "data manager"]
        return any(term in t for term in terms)

    def _store_job(self, job: dict):
        """Score and store a job."""
        session = self.Session()
        try:
            existing = session.query(Job).filter_by(url=job["url"]).first()
            if existing:
                return

            score_result = self.matcher.score_job(
                job["title"], job.get("description", ""), ""
            )
            status = "matched" if score_result["score"] >= self.min_score else "found"

            db_job = Job(
                title=job["title"],
                company=job["company"],
                location=job.get("location", "India"),
                url=job["url"],
                description=job.get("description", "")[:5000],
                match_score=score_result["score"],
                matched_skills=json.dumps(score_result["matched_skills"]),
                missing_skills=json.dumps(score_result["missing_skills"]),
                status=status,
            )
            session.add(db_job)
            session.commit()

            self.results["found"] += 1
            if status == "matched":
                self.results["matched"] += 1

        except Exception:
            pass
        finally:
            session.close()


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrent", type=int, default=5)
    parser.add_argument("--visible", action="store_true")
    args = parser.parse_args()
    scanner = GoogleScanner(max_concurrent=args.concurrent, headless=not args.visible)
    return await scanner.run()

if __name__ == "__main__":
    asyncio.run(main())
