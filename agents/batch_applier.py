"""
Batch Applier — Autonomous mass job application engine using Playwright.

Handles:
- Parallel browser sessions for simultaneous applications
- Programmatic file uploads (no OS dialog needed)
- Form detection and auto-filling
- Screening question answering
- Screenshot capture for audit trail
- Error recovery and retry logic
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config.loader import Config
from config.profile_loader import ProfileLoader
from db.models import init_db, Job, TailoredCV, Application, Account
from agents.cv_generator import CVGenerator
from agents.apply_agent import ApplyAgent
from agents.ats_learner import ATSLearner
from agents.captcha_solver import CaptchaSolver

MAX_RETRIES = 2
RETRY_DELAY = 5  # seconds between retries
REQUEST_DELAY = 3  # seconds between applications (rate limiting)


class BatchApplier:
    """Autonomous batch job application engine."""

    def __init__(self, max_concurrent: int = 3, headless: bool = True, dry_run: bool = True):
        self.config = Config()
        self.profile = ProfileLoader.get_active_profile()
        self.profile_id = self.profile["profile"]["id"]
        self.max_concurrent = max_concurrent
        self.headless = headless
        self.dry_run = dry_run
        self.Session = init_db()
        self.cv_path = str((Path(__file__).parent.parent / "config" / "base_cv.pdf").absolute())
        self.screenshot_dir = Path(__file__).parent.parent / "data" / "screenshots"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.user_data = ProfileLoader.get_user_data(self.profile)
        self.applier = ApplyAgent(self.user_data, self.profile)
        self.cv_gen = CVGenerator()
        self.ats_learner = ATSLearner()
        self.captcha_solver = CaptchaSolver()
        self.results = {"submitted": 0, "failed": 0, "skipped": 0, "errors": []}

    async def run(self, job_ids: list[int] = None, limit: int = 100):
        """Run batch applications for matched jobs."""
        from playwright.async_api import async_playwright

        session = self.Session()
        try:
            if job_ids:
                jobs = session.query(Job).filter(Job.id.in_(job_ids)).all()
            else:
                jobs = (
                    session.query(Job)
                    .filter(Job.status.in_(["matched", "cv_created"]))
                    .filter(Job.match_score >= 0.6)
                    .order_by(Job.match_score.desc())
                    .limit(limit)
                    .all()
                )

            job_data = [
                {
                    "id": j.id, "title": j.title, "company": j.company,
                    "url": j.url, "location": j.location,
                    "description": j.description or "",
                    "match_score": j.match_score,
                }
                for j in jobs
            ]
        finally:
            session.close()

        if not job_data:
            print("[BatchApplier] No matched jobs to apply to.")
            return self.results

        print(f"\n🐵 MonkeyKing Batch Applier")
        print(f"   Jobs to process: {len(job_data)}")
        print(f"   Concurrent sessions: {self.max_concurrent}")
        print(f"   CV file: {self.cv_path}")
        print(f"   Mode: {'headless' if self.headless else 'visible'}")
        print(f"   Dry run: {self.dry_run}")
        print()

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            semaphore = asyncio.Semaphore(self.max_concurrent)

            tasks = [
                self._apply_to_job(browser, semaphore, job)
                for job in job_data
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
            await browser.close()

        print(f"\n--- Batch Results ---")
        print(f"  Submitted: {self.results['submitted']}")
        print(f"  Failed: {self.results['failed']}")
        print(f"  Skipped: {self.results['skipped']}")
        if self.results['errors']:
            print(f"  Errors:")
            for err in self.results['errors'][:10]:
                print(f"    - {err}")

        return self.results

    async def _apply_to_job(self, browser, semaphore, job: dict):
        """Apply to a single job with concurrency control and retry."""
        for attempt in range(1, MAX_RETRIES + 1):
            success = await self._try_apply(browser, semaphore, job, attempt)
            if success:
                return
            if attempt < MAX_RETRIES:
                print(f"  [{job['id']}] 🔄 Retrying in {RETRY_DELAY}s (attempt {attempt + 1}/{MAX_RETRIES})...")
                await asyncio.sleep(RETRY_DELAY)

        # Rate limit between applications
        await asyncio.sleep(REQUEST_DELAY)

    async def _try_apply(self, browser, semaphore, job: dict, attempt: int) -> bool:
        """Single attempt to apply to a job. Returns True on success."""
        async with semaphore:
            job_id = job["id"]
            company = job["company"]
            title = job["title"]
            url = job["url"]

            print(f"  [{job_id}] Starting: {title} @ {company}")

            # Generate tailored PDF CV for this job
            try:
                pdf_path = self.cv_gen.generate_pdf(
                    profile=self.profile,
                    job_title=title,
                    company=company,
                )
                print(f"  [{job_id}] 📄 CV generated: {Path(pdf_path).name}")
            except Exception as e:
                pdf_path = self.cv_path  # Fallback to base CV
                print(f"  [{job_id}] ⚠ CV gen failed, using base: {e}")

            # Check if we have saved ATS pattern for this company
            ats_pattern = self.ats_learner.get_pattern(company)
            if ats_pattern:
                print(f"  [{job_id}] 🧠 Using saved ATS pattern ({ats_pattern.get('ats_type', 'unknown')})")

            # Check for saved credentials
            creds = self.ats_learner.get_account_credentials(company, self.profile_id)
            if creds:
                print(f"  [{job_id}] 🔑 Found saved credentials for {company}")

            context = await browser.new_context()
            page = await context.new_page()

            try:
                # Step 1: Navigate to job page
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)

                # Step 2: Find and click Apply button
                apply_link = await self._find_apply_link(page)
                if not apply_link:
                    print(f"  [{job_id}] ⚠ No apply link found, skipping")
                    self.results["skipped"] += 1
                    self._record_application(job_id, "skipped", "No apply link found")
                    return True  # Don't retry skipped jobs

                # Navigate to application form (only if it's a different URL)
                if apply_link != page.url:
                    try:
                        # Use domcontentloaded for Lever/heavy SPAs (networkidle hangs)
                        await page.goto(apply_link, wait_until="domcontentloaded", timeout=45000)
                    except Exception:
                        # Fallback: try with longer timeout and no wait condition
                        try:
                            await page.goto(apply_link, timeout=60000)
                        except Exception as nav_err:
                            print(f"  [{job_id}] ⚠ Navigation failed: {str(nav_err)[:80]}")
                            self.results["failed"] += 1
                            self._record_application(job_id, "failed", f"Navigation: {str(nav_err)[:200]}")
                            return False
                # Wait for JS to render the form
                await page.wait_for_timeout(3000)

                # Step 3: Learn ATS pattern from this page
                pattern = await self.ats_learner.learn_from_page(page, company, apply_link)
                print(f"  [{job_id}] 🧠 Learned ATS: {pattern.get('ats_type', 'unknown')} ({len(pattern.get('form_fields',[]))} fields)")

                # Step 4: Check for CAPTCHA
                captcha_type = await self.captcha_solver.detect_captcha(page)
                if captcha_type:
                    await self.captcha_solver.solve(page, captcha_type)

                # Step 5: Take screenshot of form
                await page.screenshot(
                    path=str(self.screenshot_dir / f"form_{job_id}_{company}.png")
                )

                # Step 6: Fill the application form
                filled = await self._fill_application_form(page, job, pdf_path)
                if not filled:
                    print(f"  [{job_id}] ⚠ Could not fill form, skipping")
                    self.results["failed"] += 1
                    self._record_application(job_id, "failed", "Could not fill form")
                    return False

                # Step 7: Take screenshot before submit
                await page.screenshot(
                    path=str(self.screenshot_dir / f"filled_{job_id}_{company}.png")
                )

                # Step 8: Submit or dry-run
                if self.dry_run:
                    print(f"  [{job_id}] ✅ Form filled: {title} @ {company} [DRY RUN - not submitting]")
                    self.results["submitted"] += 1
                    self._record_application(job_id, "dry_run")
                else:
                    submitted = await self._submit_form(page, company)
                    if submitted:
                        print(f"  [{job_id}] ✅ Submitted: {title} @ {company}")
                        self.results["submitted"] += 1
                        self._record_application(job_id, "submitted")
                        # Screenshot confirmation
                        try:
                            await page.wait_for_timeout(3000)
                            await page.screenshot(
                                path=str(self.screenshot_dir / f"confirmed_{job_id}_{company}.png")
                            )
                        except Exception:
                            pass
                    else:
                        print(f"  [{job_id}] ⚠ Submit button not found or failed")
                        self.results["failed"] += 1
                        self._record_application(job_id, "failed", "Submit failed")
                        return False

                return True

            except Exception as e:
                error_msg = f"{title} @ {company}: {str(e)[:200]}"
                print(f"  [{job_id}] ❌ Error: {str(e)[:100]}")
                if attempt >= MAX_RETRIES:
                    self.results["failed"] += 1
                    self.results["errors"].append(error_msg)
                    self._record_application(job_id, "failed", str(e)[:500])
                try:
                    await page.screenshot(
                        path=str(self.screenshot_dir / f"error_{job_id}_{company}.png")
                    )
                except Exception:
                    pass
                return False
            finally:
                await context.close()

    async def _find_apply_link(self, page) -> Optional[str]:
        """Find the apply/application link on a job page.
        
        Handles: regular links, anchor-only hrefs, JS buttons, iframes (Workday),
        and Lever/Greenhouse ATS patterns.
        """
        current_url = page.url

        # Strategy 1: Detect known ATS and build apply URL directly
        url_lower = current_url.lower()
        if "lever.co" in url_lower and "/apply" not in url_lower:
            return current_url.rstrip("/") + "/apply"
        if "greenhouse.io" in url_lower and "/apply" not in url_lower:
            return current_url.rstrip("/") + "#app"
        if "ashbyhq.com" in url_lower:
            # Ashby embeds the form on the same page — just scroll to it
            return current_url

        # Strategy 2: Look for apply links/buttons on the page
        selectors = [
            'a[href*="/apply"]',
            'a[href*="application"]',
            'a:has-text("Apply Now")',
            'a:has-text("Apply")',
            'button:has-text("Apply Now")',
            'button:has-text("Apply for this job")',
            'button:has-text("Apply")',
            'input[value*="Apply"]',
        ]
        for selector in selectors:
            try:
                el = page.locator(selector).first
                if await el.count() > 0:
                    href = await el.get_attribute("href")
                    if href:
                        # Skip anchor-only links like "#anchor-application"
                        if href.startswith("#"):
                            # Scroll to the anchor instead of navigating
                            await page.evaluate(f'document.querySelector("{href}")?.scrollIntoView()')
                            await page.wait_for_timeout(1000)
                            return current_url  # Stay on same page
                        if href.startswith("/"):
                            base = current_url.split("/")[0] + "//" + current_url.split("/")[2]
                            href = base + href
                        if href.startswith("http"):
                            return href
                    # No href — it's a button. Click it and see what happens.
                    await el.click()
                    await page.wait_for_timeout(3000)
                    new_url = page.url
                    if new_url != current_url:
                        return new_url
                    # Page didn't navigate — form might have appeared inline
                    # Check if a form is now visible
                    form = page.locator('form, [class*="application"], [id*="application"]').first
                    if await form.count() > 0:
                        return current_url
            except Exception:
                continue

        # Strategy 3: Check for iframes (Workday, iCIMS, Taleo)
        try:
            iframe_selectors = [
                'iframe[src*="workday"]',
                'iframe[src*="icims"]',
                'iframe[src*="taleo"]',
                'iframe[src*="apply"]',
                'iframe[src*="career"]',
            ]
            for sel in iframe_selectors:
                iframe = page.locator(sel).first
                if await iframe.count() > 0:
                    src = await iframe.get_attribute("src")
                    if src:
                        return src
        except Exception:
            pass

        # Strategy 4: Look for any form on the page already
        try:
            form = page.locator('form[action*="apply"], form[action*="submit"], form[class*="application"]').first
            if await form.count() > 0:
                return current_url
        except Exception:
            pass

        return None

    async def _submit_form(self, page, company: str) -> bool:
        """Find and click the submit button on the application form."""
        # Check if we have a learned submit selector for this company
        pattern = self.ats_learner.get_pattern(company)
        if pattern and pattern.get("submit_selector"):
            try:
                btn = page.locator(pattern["submit_selector"]).first
                if await btn.count() > 0:
                    await btn.click()
                    await page.wait_for_timeout(3000)
                    return True
            except Exception:
                pass

        # Fallback: try common submit selectors
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Submit Application")',
            'button:has-text("Submit")',
            'button:has-text("Apply")',
            'button:has-text("Send Application")',
        ]
        for selector in submit_selectors:
            try:
                btn = page.locator(selector).first
                if await btn.count() > 0:
                    await btn.click()
                    await page.wait_for_timeout(3000)
                    return True
            except Exception:
                continue
        return False

    async def _fill_application_form(self, page, job: dict, cv_file: str = None) -> bool:
        """Auto-detect and fill application form fields.
        
        Handles: standard forms, Lever, Greenhouse, Ashby, Workday, and
        non-standard field naming conventions.
        """
        user = self.user_data
        filled_count = 0
        cv_path = cv_file or self.cv_path

        # Expanded field patterns — keys are substrings matched against
        # id, name, placeholder, aria-label, and associated label text
        field_map = {
            "full_name": user.get("name", ""),
            "full name": user.get("name", ""),
            "your name": user.get("name", ""),
            "candidate_name": user.get("name", ""),
            "name": user.get("name", ""),
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "first name": user.get("name", "").split()[0] if user.get("name") else "",
            "given_name": user.get("name", "").split()[0] if user.get("name") else "",
            "last_name": user.get("name", "").split()[-1] if user.get("name") else "",
            "last name": user.get("name", "").split()[-1] if user.get("name") else "",
            "family_name": user.get("name", "").split()[-1] if user.get("name") else "",
            "surname": user.get("name", "").split()[-1] if user.get("name") else "",
            "email": user.get("email", ""),
            "e-mail": user.get("email", ""),
            "email_address": user.get("email", ""),
            "phone": user.get("phone", ""),
            "phone_number": user.get("phone", ""),
            "mobile": user.get("phone", ""),
            "telephone": user.get("phone", ""),
            "cell": user.get("phone", ""),
            "linkedin": user.get("linkedin", ""),
            "linkedin_url": user.get("linkedin", ""),
            "linkedin_profile": user.get("linkedin", ""),
            "location": user.get("location", ""),
            "current_location": user.get("location", ""),
            "city": "Bangalore",
            "current_company": "Amazon",
            "current_title": "Strategic Account Manager",
            "current company": "Amazon",
            "current title": "Strategic Account Manager",
        }

        # Use locator API for all visible form inputs
        input_selectors = [
            "input[type='text']", "input[type='email']", "input[type='tel']",
            "input[type='url']", "input:not([type])",
            "input[type='number']",
        ]
        input_locator = page.locator(", ".join(input_selectors)).filter(has_not=page.locator("[type='hidden']"))
        count = await input_locator.count()

        for i in range(count):
            inp = input_locator.nth(i)
            try:
                # Skip hidden/invisible inputs
                if not await inp.is_visible():
                    continue

                inp_id = await inp.get_attribute("id") or ""
                inp_name = await inp.get_attribute("name") or ""
                inp_placeholder = await inp.get_attribute("placeholder") or ""
                inp_label = await inp.get_attribute("aria-label") or ""
                inp_autocomplete = await inp.get_attribute("autocomplete") or ""

                # Try to find associated label element
                if inp_id:
                    label_loc = page.locator(f'label[for="{inp_id}"]')
                    if await label_loc.count() > 0:
                        inp_label = await label_loc.first.inner_text() or inp_label

                # Also check parent/sibling text for unlabeled fields
                parent_text = ""
                try:
                    parent = inp.locator("xpath=..")
                    parent_text = (await parent.inner_text(timeout=1000)).strip()[:100]
                except Exception:
                    pass

                identifiers = f"{inp_id} {inp_name} {inp_placeholder} {inp_label} {inp_autocomplete} {parent_text}".lower()

                # Skip already-filled inputs
                current_val = await inp.input_value()
                if current_val and len(current_val) > 2:
                    continue

                for key, value in field_map.items():
                    if key in identifiers and value:
                        await inp.fill(value)
                        filled_count += 1
                        break
            except Exception:
                continue

        # Also try filling textareas (cover letter, additional info)
        try:
            textareas = page.locator("textarea:visible")
            ta_count = await textareas.count()
            for i in range(ta_count):
                ta = textareas.nth(i)
                ta_id = await ta.get_attribute("id") or ""
                ta_name = await ta.get_attribute("name") or ""
                ta_label = await ta.get_attribute("aria-label") or ""
                ta_placeholder = await ta.get_attribute("placeholder") or ""
                idents = f"{ta_id} {ta_name} {ta_label} {ta_placeholder}".lower()
                if any(kw in idents for kw in ["cover", "letter", "why", "interest", "motivation"]):
                    cover = (f"I am excited to apply for the {job.get('title', '')} role at {job.get('company', '')}. "
                             f"With 9+ years of experience in AI platforms, product management, and strategic account growth, "
                             f"I bring a strong track record of driving revenue and building AI-powered solutions.")
                    await ta.fill(cover)
                    filled_count += 1
        except Exception:
            pass

        # Try to upload resume/CV
        file_locator = page.locator('input[type="file"]')
        file_count = await file_locator.count()
        for i in range(file_count):
            file_input = file_locator.nth(i)
            try:
                accept = await file_input.get_attribute("accept") or ""
                inp_id = await file_input.get_attribute("id") or ""
                inp_name = await file_input.get_attribute("name") or ""
                parent_text = ""
                try:
                    parent = file_input.locator("xpath=..")
                    parent_text = (await parent.inner_text(timeout=1000)).lower()
                except Exception:
                    pass
                all_idents = f"{accept} {inp_id} {inp_name} {parent_text}".lower()
                if ("pdf" in all_idents or "resume" in all_idents
                        or "cv" in all_idents or "document" in all_idents
                        or not accept):  # No accept filter = likely resume
                    if os.path.exists(cv_path):
                        await file_input.set_input_files(cv_path)
                        filled_count += 1
                        print(f"    📄 Resume uploaded: {Path(cv_path).name}")
                        break
            except Exception as e:
                print(f"    ⚠ File upload failed: {e}")

        # Answer Yes/No questions
        await self._answer_screening_questions(page)

        return filled_count >= 2  # At least name/email + resume

    async def _answer_screening_questions(self, page):
        """Answer common screening questions on application forms.
        
        Handles: Yes/No buttons, radio buttons, dropdowns, and text inputs.
        """
        screening = ProfileLoader.get_screening_answers(self.profile)

        try:
            # Strategy 1: Yes/No button groups
            q_locator = page.locator('[class*="question"], [class*="field"], fieldset, [data-qa*="question"]')
            q_count = await q_locator.count()
            for i in range(min(q_count, 30)):  # Cap at 30 to avoid infinite loops
                q = q_locator.nth(i)
                try:
                    text = (await q.inner_text(timeout=2000)).lower()
                except Exception:
                    continue

                answer = self._match_screening_answer(text, screening)
                if not answer:
                    continue

                # Try clicking Yes/No buttons
                if answer.lower() in ("yes", "no"):
                    btn = q.locator(f'button:has-text("{answer}")').first
                    if await btn.count() > 0:
                        await btn.click()
                        continue
                    # Try radio buttons
                    radio = q.locator(f'input[type="radio"][value*="{answer}" i], label:has-text("{answer}") input[type="radio"]').first
                    if await radio.count() > 0:
                        await radio.click()
                        continue

                # Try filling text inputs within the question
                inp = q.locator('input[type="text"], input[type="number"], textarea').first
                if await inp.count() > 0:
                    await inp.fill(str(answer))
                    continue

                # Try selecting from dropdown
                sel = q.locator('select').first
                if await sel.count() > 0:
                    try:
                        await sel.select_option(label=str(answer))
                    except Exception:
                        try:
                            await sel.select_option(value=str(answer))
                        except Exception:
                            pass

        except Exception as e:
            print(f"    ⚠ Screening questions error: {e}")

    def _match_screening_answer(self, question_text: str, screening: dict) -> str:
        """Match a screening question to a pre-configured answer."""
        q = question_text.lower()

        # Check profile-level screening answers first
        for key, val in screening.items():
            if key.lower().replace("_", " ") in q:
                return str(val)

        # Built-in answers
        if "authorized" in q and "work" in q:
            return "Yes" if "india" in q else "No"
        if "sponsorship" in q or ("visa" in q and "require" in q):
            return "Yes"
        if "relocate" in q:
            return "Yes"
        if "remote" in q and ("willing" in q or "open" in q or "comfortable" in q):
            return "Yes"
        if "years" in q and "experience" in q:
            return "9"
        if "salary" in q or "compensation" in q or "expected" in q:
            return "Open to discussion"
        if "notice" in q and "period" in q:
            return "30 days"
        if "start" in q and "date" in q:
            return "Within 2-4 weeks"
        if "current" in q and ("company" in q or "employer" in q):
            return "Amazon"
        if "gender" in q or "pronoun" in q:
            return ""  # Skip sensitive questions
        if "disability" in q or "veteran" in q or "race" in q or "ethnicity" in q:
            return ""  # Skip EEO questions

        return ""

    def _record_application(self, job_id: int, status: str, error: str = ""):
        """Record application result in database."""
        session = self.Session()
        try:
            job = session.query(Job).get(job_id)
            if not job:
                return

            app = Application(
                job_id=job_id,
                status=status,
                error_message=error if error else None,
                submitted_at=datetime.utcnow() if status == "submitted" else None,
            )
            session.add(app)
            job.status = "applied" if status == "submitted" else status
            job.applied_at = datetime.utcnow() if status == "submitted" else None
            session.commit()
        except Exception as e:
            print(f"    DB error: {e}")
        finally:
            session.close()


async def main():
    """CLI entry point for batch applier."""
    import argparse
    parser = argparse.ArgumentParser(description="MonkeyKing Batch Applier")
    parser.add_argument("--limit", type=int, default=100, help="Max jobs to apply to")
    parser.add_argument("--concurrent", type=int, default=3, help="Concurrent browser sessions")
    parser.add_argument("--visible", action="store_true", help="Show browser windows")
    parser.add_argument("--job-ids", type=str, help="Comma-separated job IDs to apply to")
    parser.add_argument("--no-dry-run", action="store_true", help="Actually submit applications (default is dry run)")
    args = parser.parse_args()

    job_ids = None
    if args.job_ids:
        job_ids = [int(x.strip()) for x in args.job_ids.split(",")]

    applier = BatchApplier(
        max_concurrent=args.concurrent,
        headless=not args.visible,
        dry_run=not args.no_dry_run,
    )
    results = await applier.run(job_ids=job_ids, limit=args.limit)
    return results


if __name__ == "__main__":
    asyncio.run(main())
