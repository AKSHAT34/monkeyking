"""
Batch Scanner — Autonomous mass job scanning engine using Playwright.

Scans all target company career pages in parallel,
extracts job listings, scores them against CV, stores in DB.
"""
import asyncio
import json
import os
import re
import sys
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.loader import Config
from db.models import init_db, Job
from agents.job_matcher import JobMatcherAgent

REQUEST_DELAY = 2  # seconds between company scans (rate limiting)


class BatchScanner:
    """Autonomous batch job scanner."""

    def __init__(self, max_concurrent: int = 5, headless: bool = True):
        self.config = Config()
        self.max_concurrent = max_concurrent
        self.headless = headless
        self.Session = init_db()
        self.matcher = JobMatcherAgent(self.config.cv_data)
        self.target_roles = self.config.job_preferences.get("target_roles", [])
        self.min_score = self.config.job_preferences.get("min_match_score", 0.6)
        self.results = {"scanned": 0, "found": 0, "matched": 0, "errors": []}

    async def run(self):
        """Scan all target companies in parallel."""
        from playwright.async_api import async_playwright

        companies = self.config.target_companies
        print(f"\n🐵 MonkeyKing Batch Scanner")
        print(f"   Companies: {len(companies)}")
        print(f"   Target roles: {len(self.target_roles)}")
        print(f"   Concurrent: {self.max_concurrent}")
        print()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            semaphore = asyncio.Semaphore(self.max_concurrent)

            tasks = [
                self._scan_company(browser, semaphore, company)
                for company in companies
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
            await browser.close()

        print(f"\n--- Scan Results ---")
        print(f"  Companies scanned: {self.results['scanned']}")
        print(f"  Jobs found: {self.results['found']}")
        print(f"  Jobs matched (>={self.min_score:.0%}): {self.results['matched']}")
        if self.results['errors']:
            print(f"  Errors: {len(self.results['errors'])}")
            for err in self.results['errors'][:5]:
                print(f"    - {err}")

        return self.results

    async def _scan_company(self, browser, semaphore, company: dict):
        """Scan a single company's career page."""
        async with semaphore:
            name = company["name"]
            url = company["careers_url"]
            self.results["scanned"] += 1
            print(f"  🔍 Scanning: {name} ({url})")

            context = await browser.new_context()
            page = await context.new_page()

            try:
                for role in self.target_roles[:3]:  # Top 3 roles per company
                    jobs = await self._search_jobs(page, name, url, role)
                    for job in jobs:
                        self._store_job(job)
                    await asyncio.sleep(REQUEST_DELAY)  # Rate limit between searches

            except Exception as e:
                error = f"{name}: {str(e)[:200]}"
                print(f"  ❌ {name}: {str(e)[:100]}")
                self.results["errors"].append(error)
            finally:
                await context.close()

    async def _search_jobs(self, page, company: str, base_url: str, role: str) -> list:
        """Search for jobs on a company career page."""
        jobs = []

        # Strategy 1: URL-based search (most reliable)
        search_urls = [
            f"{base_url}?q={role.replace(' ', '+')}",
            f"{base_url}?query={role.replace(' ', '+')}",
            f"{base_url}?keyword={role.replace(' ', '+')}",
            f"{base_url}/search?q={role.replace(' ', '+')}",
            f"{base_url}#q={role.replace(' ', '+')}",
        ]

        for search_url in search_urls[:2]:  # Try first 2 URL patterns
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(3000)

                # Extract job links
                links = await page.evaluate("""() => {
                    const jobs = [];
                    const allLinks = document.querySelectorAll('a');
                    for (const link of allLinks) {
                        const href = link.getAttribute('href') || '';
                        const text = link.textContent.trim();
                        if (text.length > 10 && text.length < 200 &&
                            (href.includes('career') || href.includes('job') ||
                             href.includes('position') || href.includes('opening'))) {
                            if (!text.includes('Apply now') && !text.includes('Careers at')) {
                                jobs.push({title: text, url: link.href});
                            }
                        }
                    }
                    return jobs;
                }""")

                for link in links:
                    title = link["title"].strip()
                    # Quick relevance check
                    if self._is_relevant(title):
                        jobs.append({
                            "title": title,
                            "company": company,
                            "url": link["url"],
                            "location": "",
                            "description": title,
                        })

                if jobs:
                    break  # Found jobs, no need to try other URL patterns

            except Exception:
                continue

        return jobs

    def _is_relevant(self, title: str) -> bool:
        """Quick check if a job title is potentially relevant."""
        title_lower = title.lower()
        relevant_terms = [
            "product manager", "program manager", "project manager",
            "account manager", "product owner", "ai ", "artificial intelligence",
            "machine learning", "ml ", "platform manager", "delivery manager",
            "operations manager", "strategy manager",
        ]
        return any(term in title_lower for term in relevant_terms)

    def _store_job(self, job: dict):
        """Score and store a job in the database."""
        session = self.Session()
        try:
            # Check duplicate
            existing = session.query(Job).filter_by(url=job["url"]).first()
            if existing:
                return

            # Score
            score_result = self.matcher.score_job(
                job["title"], job.get("description", ""), job.get("requirements", "")
            )

            status = "matched" if score_result["score"] >= self.min_score else "found"

            db_job = Job(
                title=job["title"],
                company=job["company"],
                location=job.get("location", ""),
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
                print(f"    ✅ [{score_result['score']:.0%}] {job['title']} @ {job['company']}")

        except Exception as e:
            print(f"    DB error: {e}")
        finally:
            session.close()


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="MonkeyKing Batch Scanner")
    parser.add_argument("--concurrent", type=int, default=5, help="Concurrent browser sessions")
    parser.add_argument("--visible", action="store_true", help="Show browser windows")
    args = parser.parse_args()

    scanner = BatchScanner(max_concurrent=args.concurrent, headless=not args.visible)
    return await scanner.run()


if __name__ == "__main__":
    asyncio.run(main())
