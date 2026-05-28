"""Job Scanner — Hybrid: ATS APIs (fast) + Playwright (fallback)."""
import asyncio
import json
import re
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
from models import Job, Company, SearchRun, UserJobMatch

PARALLEL = 3  # Low parallelism for reliability on 8GB VPS

# ─── UNIFIED GARBAGE TITLE PATTERNS ────────────────────
# Merged from SKIP_TITLES and GARBAGE_WORDS — single source of truth
GARBAGE_PATTERNS: set[str] = {
    # Navigation / UI elements
    "apply", "apply now", "sign in", "log in", "sign up", "register",
    "home", "back", "next", "previous", "search", "filter", "clear",
    # Career page chrome
    "careers", "career", "jobs", "job search", "open positions", "view open",
    "explore roles", "find your role", "find your", "job categories",
    "early in profession", "neurodiversity", "contractor roles",
    "students", "internships", "application status", "check application",
    "careers at", "life at", "how we hire", "our culture", "benefits",
    "about us", "contact", "diversity", "inclusion", "teams",
    "locations", "offices",
    # Generic link text
    "see more", "read more", "learn more", "read full",
    "discover job", "explore", "browse", "all jobs",
    # ATS / HR jargon
    "work_outline", "requisition management", "job descriptions",
    "career compass", "hiring policies", "equal opportunity",
    "prospect application", "future jobs", "talent pool",
    # Misc scraped garbage
    "cookie", "privacy", "terms",
    "new cars", "used cars", "compare", "gaadi store",
}


def is_garbage_title(title: str) -> bool:
    """Return True if *title* is not a real job posting title.

    Pure function — no side effects, no DB access.
    """
    # None / non-string → garbage
    if not isinstance(title, str):
        return True

    stripped = title.strip()
    lower = stripped.lower()

    # Length bounds
    if len(stripped) < 5 or len(stripped) > 150:
        return True

    # HTML tags (<…>) or HTML entities (&amp; &nbsp; etc.)
    if re.search(r"<[^>]+>", stripped) or re.search(r"&[a-z]+;", lower):
        return True

    # Literal "work_outline" (Material-icon text leak)
    if "work_outline" in lower:
        return True

    # Temporal markers — scraped date fragments
    if re.search(r"(days?\s+ago|hours?\s+ago|posted\s+on|date\s+posted)", lower):
        return True

    # Single word shorter than 15 chars
    if " " not in stripped and len(stripped) < 15:
        return True

    # Pattern match against known garbage
    if any(g in lower for g in GARBAGE_PATTERNS):
        return True

    return False


# ─── ADAPTIVE LEARNING HELPERS ───────────────────────────

def _record_scan_outcome(db, company_id: int, method_name: str, success: bool, jobs_found: int):
    """Record scan method outcome for a company. Non-blocking — errors are logged and swallowed."""
    try:
        from models import ScanHistory
        existing = db.query(ScanHistory).filter_by(company_id=company_id, method_name=method_name).first()
        now = datetime.utcnow()
        if existing:
            existing.success = success
            existing.jobs_found = jobs_found
            existing.last_attempted = now
            if success:
                existing.last_success = now
                existing.consecutive_failures = 0
            else:
                existing.consecutive_failures = (existing.consecutive_failures or 0) + 1
        else:
            db.add(ScanHistory(
                company_id=company_id, method_name=method_name,
                success=success, jobs_found=jobs_found,
                last_attempted=now, last_success=now if success else None,
                consecutive_failures=0 if success else 1
            ))
        db.commit()
    except Exception as e:
        try: db.rollback()
        except: pass
        print(f"  [learn] Failed to record scan outcome: {e}", flush=True)


def _get_prioritized_methods(db, company_id: int) -> list[str]:
    """Return scan methods ordered by history. Most recently successful first."""
    DEFAULT_ORDER = ["ats_api", "browser", "html_parse", "linkedin", "vision"]
    try:
        from models import ScanHistory
        records = db.query(ScanHistory).filter_by(company_id=company_id).all()
        if not records:
            return DEFAULT_ORDER

        cutoff = datetime.utcnow() - timedelta(days=14)
        available = []
        for r in records:
            # Skip methods with 3+ consecutive failures (unless stale > 14 days)
            if r.consecutive_failures >= 3 and r.last_attempted and r.last_attempted > cutoff:
                continue
            available.append(r)

        # Sort by: successful first, then by most recent success
        available.sort(key=lambda r: (not r.success, -(r.last_success or datetime.min).timestamp()))

        prioritized = [r.method_name for r in available]
        # Add any default methods not yet in history
        for m in DEFAULT_ORDER:
            if m not in prioritized:
                prioritized.append(m)
        return prioritized
    except Exception as e:
        print(f"  [learn] Failed to get prioritized methods: {e}", flush=True)
        return DEFAULT_ORDER


def _check_ats_patterns(company_name: str) -> tuple | None:
    """Check data/ats_patterns/ for a matching JSON file. Returns (ats_type, url) or None."""
    RECOGNIZED_ATS = {"greenhouse", "lever", "ashby", "workday", "smartrecruiters", "workable", "recruitee", "breezy", "hirehive"}
    try:
        import json
        patterns_dir = Path(__file__).parent.parent / "data" / "ats_patterns"
        if not patterns_dir.exists():
            return None
        # Normalize name: "Adobe India" → "adobe_india"
        normalized = company_name.lower().replace(" ", "_").replace("-", "_")
        for f in patterns_dir.glob("*.json"):
            if f.stem == normalized:
                data = json.loads(f.read_text())
                ats_type = data.get("ats_type", "").lower()
                if ats_type in RECOGNIZED_ATS:
                    url = data.get("careers_url", "")
                    return (ats_type, url) if url else None
                return None  # "unknown" or unrecognized
        return None
    except Exception as e:
        print(f"  [learn] ATS pattern check failed: {e}", flush=True)
        return None


# ─── WORKDAY CXS API CONFIGS ──────────────────────────
WORKDAY_CONFIGS = {
    "target": ("target", "wd5", "targetcareers"),
    "target india": ("target", "wd5", "targetcareers"),
    "nvidia": ("nvidia", "wd5", "NVIDIAExternalCareerSite"),
    "hp": ("hp", "wd5", "ExternalCareerSite"),
    "walmart": ("walmart", "wd5", "WalmartExternal"),
    "walmart india": ("walmart", "wd5", "WalmartExternal"),
    "netflix": ("netflix", "wd1", "netflix"),
    "cisco": ("cisco", "wd5", "cisco_Careers"),
    "crowdstrike": ("crowdstrike", "wd5", "crowdstrikecareers"),
    "dell": ("dell", "wd1", "External"),
    "zoom": ("zoom", "wd5", "Zoom"),
}

# ─── KNOWN ATS API PATTERNS ────────────────────────────
# These return structured JSON — no browser needed, 10x faster

async def _fetch_lever_jobs(company_slug: str, client: httpx.AsyncClient) -> list[dict]:
    """Lever public API: https://api.lever.co/v0/postings/{company}"""
    try:
        r = await client.get(f"https://api.lever.co/v0/postings/{company_slug}?mode=json", timeout=15)
        if r.status_code == 200:
            data = r.json()
            return [{"title": j["text"], "url": j["hostedUrl"], "location": j.get("categories", {}).get("location", ""),
                     "company": company_slug, "description": j.get("descriptionPlain", "")[:5000]}
                    for j in data if isinstance(j, dict) and "text" in j]
    except Exception:
        pass
    return []

async def _fetch_greenhouse_jobs(board_token: str, client: httpx.AsyncClient) -> list[dict]:
    """Greenhouse public API: https://boards-api.greenhouse.io/v1/boards/{token}/jobs"""
    try:
        r = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true", timeout=15)
        if r.status_code == 200:
            data = r.json().get("jobs", [])
            return [{"title": j["title"], "url": j["absolute_url"],
                     "location": j.get("location", {}).get("name", ""),
                     "company": board_token,
                     "description": re.sub(r'<[^>]+>', '', re.sub(r'&[a-z]+;', ' ', j.get("content", "")))[:5000]}
                    for j in data]
    except Exception:
        pass
    return []

async def _fetch_ashby_jobs(org_name: str, client: httpx.AsyncClient) -> list[dict]:
    """Ashby public API: https://api.ashbyhq.com/posting-api/job-board/{org}"""
    try:
        r = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{org_name}", timeout=15)
        if r.status_code == 200:
            data = r.json().get("jobs", [])
            return [{"title": j["title"], "url": f"https://jobs.ashbyhq.com/{org_name}/{j['id']}",
                     "location": j.get("location", ""),
                     "company": org_name,
                     "description": re.sub(r'<[^>]+>', '', j.get("descriptionHtml", ""))[:5000]}
                    for j in data]
    except Exception:
        pass
    return []


async def _fetch_workday_jobs(tenant: str, wd_server: str, site: str, client: httpx.AsyncClient) -> list[dict]:
    """Workday CXS public API — no auth needed."""
    try:
        url = f"https://{tenant}.{wd_server}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
        r = await client.post(url,
            json={"appliedFacets": {}, "limit": 50, "offset": 0, "searchText": ""},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=15)
        if r.status_code == 200:
            data = r.json()
            base = f"https://{tenant}.{wd_server}.myworkdayjobs.com/en-US/{site}"
            return [{
                "title": j.get("title", ""),
                "url": f"{base}/job/{j.get('externalPath', '')}",
                "location": j.get("locationsText", ""),
                "company": tenant,
                "description": j.get("descriptionTeaser", "")[:3000],
            } for j in data.get("jobPostings", [])]
    except Exception:
        pass
    return []


async def _fetch_turbohire_jobs(org_id: str, company_name: str, client: httpx.AsyncClient) -> list[dict]:
    """TurboHire API — intercept token from browser, then fetch jobs."""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context()
            page = await ctx.new_page()

            token = None
            async def capture_token(request):
                nonlocal token
                if "filteredjobs" in request.url:
                    auth = request.headers.get("authorization", "")
                    if auth.startswith("Bearer "):
                        token = auth

            page.on("request", capture_token)
            slug = company_name.lower().replace(" ", "")
            await page.goto(f"https://{slug}.turbohire.co/dashboardv2?orgId={org_id}", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
            await ctx.close()
            await browser.close()

            if not token:
                return []

            # Now use the captured token to fetch all jobs
            r = await client.post(
                f"https://api.turbohire.co/api/careerpagev2/filteredjobs?orgId={org_id}&pageType=0",
                headers={"Authorization": token, "Content-Type": "application/json", "Accept": "application/json"},
                json={"SortByV2": {"Key": "PostedDate", "Order": 2},
                      "BunitIds": {"Value": None, "FilterType": 0},
                      "Experience": {"Value": None, "FilterType": 0},
                      "JobTypes": {"Value": None, "FilterType": 0},
                      "Locations": {"Value": None, "FilterType": 0},
                      "PageNumber": 1, "PageSize": 100},
                timeout=15,
            )
            if r.status_code == 200:
                data = r.json()
                results = data.get("Result", [])
                jobs = []
                for j in results:
                    title = j.get("JobTitle", "")
                    job_id = j.get("JobIdObfuscated", j.get("JobId", ""))
                    location = j.get("Location", "")
                    desc = j.get("JobDescription", "")
                    url = f"https://{slug}.turbohire.co/jobs/{job_id}"
                    if title:
                        jobs.append({
                            "title": title, "url": url, "location": location,
                            "company": company_name,
                            "description": (desc or "")[:5000],
                        })
                return jobs
    except Exception as e:
        print(f"  TurboHire error: {e}", flush=True)
    return []


async def _fetch_smartrecruiters_jobs(company_id: str, client: httpx.AsyncClient) -> list[dict]:
    """SmartRecruiters public API."""
    try:
        jobs = []
        offset = 0
        while offset < 200:
            r = await client.get(f"https://api.smartrecruiters.com/v1/companies/{company_id}/postings?limit=100&offset={offset}", timeout=15)
            if r.status_code != 200:
                break
            data = r.json()
            content = data.get("content", [])
            if not content:
                break
            for j in content:
                url = j.get("ref", "") or f"https://jobs.smartrecruiters.com/{company_id}/{j.get('id', '')}"
                jobs.append({
                    "title": j.get("name", ""),
                    "url": url,
                    "location": j.get("location", {}).get("city", ""),
                    "company": company_id,
                    "description": (j.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text", "") or "")[:5000],
                })
            offset += 100
            if len(content) < 100:
                break
        return jobs
    except Exception:
        pass
    return []


async def _fetch_workable_jobs(company_slug: str, client: httpx.AsyncClient) -> list[dict]:
    """Workable public API: https://apply.workable.com/api/v1/widget/accounts/{slug}"""
    try:
        r = await client.get(f"https://apply.workable.com/api/v1/widget/accounts/{company_slug}", timeout=15)
        if r.status_code == 200:
            data = r.json()
            jobs = data.get("jobs", [])
            return [{"title": j.get("title", ""), "url": j.get("url", j.get("shortlink", "")),
                     "location": j.get("location", {}).get("city", "") if isinstance(j.get("location"), dict) else j.get("location", ""),
                     "company": company_slug,
                     "description": j.get("description", "")[:5000]}
                    for j in jobs if j.get("title")]
    except Exception:
        pass
    return []


async def _fetch_recruitee_jobs(company_slug: str, client: httpx.AsyncClient) -> list[dict]:
    """Recruitee public API: https://{slug}.recruitee.com/api/offers"""
    try:
        r = await client.get(f"https://{company_slug}.recruitee.com/api/offers", timeout=15)
        if r.status_code == 200:
            data = r.json()
            offers = data.get("offers", [])
            return [{"title": j.get("title", ""), "url": j.get("careers_url", j.get("url", "")),
                     "location": j.get("location", ""),
                     "company": company_slug,
                     "description": re.sub(r'<[^>]+>', '', j.get("description", ""))[:5000]}
                    for j in offers if j.get("title")]
    except Exception:
        pass
    return []


async def _fetch_breezy_jobs(company_slug: str, client: httpx.AsyncClient) -> list[dict]:
    """Breezy HR public API: https://{slug}.breezy.hr/json"""
    try:
        r = await client.get(f"https://{company_slug}.breezy.hr/json", timeout=15)
        if r.status_code == 200:
            jobs = r.json()
            if isinstance(jobs, list):
                return [{"title": j.get("name", ""), "url": j.get("url", ""),
                         "location": j.get("location", {}).get("name", "") if isinstance(j.get("location"), dict) else j.get("location", ""),
                         "company": company_slug,
                         "description": j.get("description", "")[:5000]}
                        for j in jobs if j.get("name")]
    except Exception:
        pass
    return []


async def _fetch_hirehive_jobs(company_slug: str, client: httpx.AsyncClient) -> list[dict]:
    """HireHive public API: https://{slug}.hirehive.com/api/v1/jobs"""
    try:
        r = await client.get(f"https://{company_slug}.hirehive.com/api/v1/jobs", timeout=15)
        if r.status_code == 200:
            data = r.json()
            jobs = data.get("jobs", data) if isinstance(data, dict) else data
            if isinstance(jobs, list):
                return [{"title": j.get("title", j.get("name", "")), "url": j.get("url", ""),
                         "location": j.get("location", ""),
                         "company": company_slug,
                         "description": j.get("description", "")[:5000]}
                        for j in jobs if j.get("title") or j.get("name")]
    except Exception:
        pass
    return []


async def _fetch_linkedin_jobs(company_name: str, role: str, client: httpx.AsyncClient) -> list[dict]:
    """Fetch jobs from LinkedIn's public job search (no login required)."""
    try:
        query = f"{role} {company_name}"
        r = await client.get(
            f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
            params={"keywords": query, "location": "India", "start": 0},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html",
            },
            timeout=15,
        )
        if r.status_code != 200:
            return []

        # Parse the HTML response for job cards
        jobs = []
        # LinkedIn returns HTML with job cards
        import re
        titles = re.findall(r'<h3[^>]*class="[^"]*job-card[^"]*"[^>]*>(.*?)</h3>', r.text, re.DOTALL)
        links = re.findall(r'href="(https://www\.linkedin\.com/jobs/view/[^"?]+)', r.text)
        locations = re.findall(r'<span[^>]*class="[^"]*job-card[^"]*location[^"]*"[^>]*>(.*?)</span>', r.text, re.DOTALL)

        # Simpler extraction: find all job links
        job_links = re.findall(r'href="(https://www\.linkedin\.com/jobs/view/[^"?]+)"', r.text)
        job_titles = re.findall(r'class="base-search-card__title"[^>]*>(.*?)<', r.text, re.DOTALL)
        job_locs = re.findall(r'class="job-search-card__location"[^>]*>(.*?)<', r.text, re.DOTALL)

        for i, url in enumerate(job_links[:10]):
            title = job_titles[i].strip() if i < len(job_titles) else ""
            loc = job_locs[i].strip() if i < len(job_locs) else ""
            if title and company_name.lower() in title.lower() + loc.lower():
                jobs.append({
                    "title": title, "url": url, "location": loc,
                    "company": company_name, "description": "",
                })

        return jobs
    except Exception:
        return []


async def _fetch_via_google(company_name: str, careers_domain: str, role: str, client: httpx.AsyncClient) -> list[dict]:
    """Try to extract jobs from the career page HTML source (for SPAs that embed data)."""
    try:
        r = await client.get(
            f"https://{careers_domain}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=15,
        )
        if r.status_code != 200:
            return []

        text = r.text
        jobs = []

        # Strategy 1: Find JSON-LD JobPosting structured data
        ld_matches = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', text, re.DOTALL)
        for ld in ld_matches:
            try:
                data = json.loads(ld)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if isinstance(item, dict) and item.get("@type") == "JobPosting":
                        jobs.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", f"https://{careers_domain}"),
                            "location": item.get("jobLocation", {}).get("address", {}).get("addressLocality", "") if isinstance(item.get("jobLocation"), dict) else "",
                            "company": company_name,
                            "description": re.sub(r'<[^>]+>', '', item.get("description", ""))[:5000],
                        })
            except:
                pass

        if jobs:
            return jobs

        # Strategy 2: Find embedded JSON data (React/Next.js apps)
        # Look for __NEXT_DATA__, window.__data, etc.
        json_patterns = [
            r'__NEXT_DATA__\s*=\s*({.*?})\s*</script>',
            r'window\.__data\s*=\s*({.*?})\s*;',
            r'window\.__INITIAL_STATE__\s*=\s*({.*?})\s*;',
            r'"jobs"\s*:\s*(\[.*?\])',
            r'"openings"\s*:\s*(\[.*?\])',
            r'"positions"\s*:\s*(\[.*?\])',
        ]
        for pattern in json_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)
                    # Try to find job arrays in the data
                    job_arrays = _find_job_arrays(data)
                    for arr in job_arrays:
                        for item in arr:
                            if isinstance(item, dict):
                                title = item.get("title") or item.get("name") or item.get("jobTitle") or ""
                                url = item.get("url") or item.get("link") or item.get("applyUrl") or ""
                                if title and len(title) > 5:
                                    if not url.startswith("http"):
                                        url = f"https://{careers_domain}/{url.lstrip('/')}"
                                    jobs.append({
                                        "title": title, "url": url, "location": item.get("location", ""),
                                        "company": company_name, "description": item.get("description", "")[:3000],
                                    })
                except:
                    pass

        # Strategy 3: Extract job links from raw HTML (even without JS rendering)
        if not jobs:
            links = re.findall(r'href="([^"]*)"', text, re.I)
            seen = set()
            for href in links:
                if href in seen:
                    continue
                seen.add(href)
                # Skip non-job URLs
                href_lower = href.lower()
                if any(skip in href_lower for skip in ['.css', '.js', '.png', '.jpg', '.svg', '.ico', '.woff', 'favicon', 'clientlib', 'bootstrap', 'font', 'static/', 'assets/', 'cdn.', 'facebook.com', 'twitter.com', 'linkedin.com/company', 'instagram.com', 'youtube.com']):
                    continue
                # Must look like a job URL
                if not re.search(r'(job|position|opening|career|detail|requisition|vacancy|role|posting)', href_lower):
                    continue
                if not href.startswith("http"):
                    href = f"https://{careers_domain}/{href.lstrip('/')}"
                # Must be from the same domain or a known ATS
                if careers_domain not in href and not any(ats in href for ats in ['lever.co', 'greenhouse.io', 'ashbyhq.com', 'workday', 'smartrecruiters', 'turbohire', 'phenompeople', 'icims']):
                    continue
                # Extract title from URL
                slug = href.rstrip("/").split("/")[-1]
                slug = re.sub(r'[?#].*', '', slug)
                slug = slug.replace("-", " ").replace("_", " ").replace("+", " ")
                if len(slug) > 5 and len(slug) < 200 and not re.search(r'\.(css|js|png|jpg|svg)', slug):
                    jobs.append({"title": slug.title(), "url": href, "location": "",
                                 "company": company_name, "description": ""})

        return jobs[:30]
    except Exception:
        pass
    return []


def _find_job_arrays(data, depth=0):
    """Recursively find arrays that look like job listings in nested JSON."""
    if depth > 5:
        return []
    results = []
    if isinstance(data, list) and len(data) > 0:
        # Check if items look like jobs
        if isinstance(data[0], dict) and any(k in data[0] for k in ["title", "name", "jobTitle", "position"]):
            results.append(data)
    elif isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, (list, dict)):
                results.extend(_find_job_arrays(val, depth + 1))
    return results


# ─── ATS DETECTION FROM URL ────────────────────────────
# Known company → ATS API mappings (discovered by testing)
GREENHOUSE_SLUGS = {
    "groww": "groww", "postman": "postman", "phonepe": "phonepe", "slice": "slice",
    "databricks": "databricks", "stripe": "stripe", "figma": "figma",
    "mongodb": "mongodb", "elastic": "elastic", "scale ai": "scaleai",
    "anthropic": "anthropic", "stability ai": "stabilityai", "druva": "druva",
    "observe.ai": "observeai", "hubspot": "hubspotjobs", "hashicorp": "hashicorp",
    "glance": "glance", "pine labs": "pine", "tcs": "tcs", "yes bank": "yes",
    "sigmoid": "sigmoid",
    # Phase 3: new discoveries
    "cloudflare": "cloudflare", "datadog": "datadog", "brex": "brex", "xai": "xai",
    "intercom": "intercom", "fivetran": "fivetran", "smartsheet": "smartsheet",
    "asana": "asana", "twilio": "twilio", "deepmind": "deepmind", "gusto": "gusto",
    "vercel": "vercel", "vonage": "vonage", "hightouch": "hightouch",
    "airtable": "airtable", "new relic": "newrelic", "fastly": "fastly",
    "webflow": "webflow", "mixpanel": "mixpanel", "bandwidth": "bandwidth",
    "amplitude": "amplitude", "otter": "otter", "salesloft": "salesloft",
    "marqeta": "marqeta", "calendly": "calendly", "superblocks": "superblocks",
    "lattice": "lattice", "lithic": "lithic", "bluestone": "bluestone",
    "labelbox": "labelbox", "planetscale": "planetscale",
}
LEVER_SLUGS = {
    "cred": "cred",
    "dozee": "dozee", "hevo data": "hevodata", "meesho": "meesho", "paytm": "paytm",
    "dream11": "dreamsports",
    # Phase 3
    "outreach": "outreach", "porter": "porter", "angellist": "angellist",
    "upstox": "upstox", "fi money": "fi", "15five": "15five", "clari": "clari",
    "anyscale": "anyscale",
}
ASHBY_SLUGS = {
    "notion": "notion", "cohere": "cohere", "runway": "runway",
    "perplexity ai": "perplexity", "confluent": "confluent",
    "openai": "openai", "scaler": "scaler", "tiger analytics": "tiger",
    "ola electric": "olaelectric",
    # Phase 3
    "deel": "deel", "ramp": "ramp", "plaid": "plaid", "langchain": "langchain",
    "semgrep": "semgrep", "modal": "modal", "dust": "dust", "oyster": "oyster",
    "linear": "linear", "bubble": "bubble", "livekit": "livekit", "titan": "titan",
    "posthog": "posthog", "leapsome": "leapsome", "llamaindex": "llamaindex",
    "bounce": "bounce", "unit": "unit", "coframe": "coframe", "pinecone": "pinecone",
    "airbyte": "airbyte", "navi": "navi", "neon": "neon", "weaviate": "weaviate",
}
TURBOHIRE_SLUGS = {
    "flipkart": "4d757ba0-3d57-448a-b82c-238ed87ac90f",
}

WORKABLE_SLUGS = {
    "razorpay": "razorpay", "dunzo": "dunzo", "licious": "licious",
    "jupiter": "jupiter-money", "smallcase": "smallcase",
    "yellow.ai": "yellowai", "hasura": "hasura", "clevertap": "clevertap",
    "moengage": "moengage", "browserstack": "browserstack",
}

RECRUITEE_SLUGS = {
    "zepto": "zepto", "park+": "parkplus", "spinny": "spinny",
}

BREEZY_SLUGS: dict[str, str] = {}

HIREHIVE_SLUGS: dict[str, str] = {}

# Companies known to use Darwinbox (no public API — vision agent handles these)
DARWINBOX_COMPANIES = {
    "swiggy", "zepto", "ola", "ola electric", "lenskart", "pharmeasy",
    "vedanta", "adani wilmar", "l&t metro rail", "starbucks india",
    "delhivery", "nykaa", "boat", "sugar cosmetics", "mamaearth",
    "country delight", "rapido", "urban company",
}

SMARTRECRUITERS_SLUGS = {
    "freshworks": "Freshworks",
    "canva": "Canva", "cars24": "Cars24", "lendingkart": "Lendingkart",
    "nobroker": "NoBroker", "unacademy": "Unacademy", "visa": "Visa",
    "visa india": "Visa", "whatfix": "Whatfix", "ixigo": "ixigo",
    "servicenow": "ServiceNow", "mindtickle": "Mindtickle",
    "uber": "Uber", "uber india": "Uber",
    # Phase 3
    "together ai": "together", "gong": "gong", "instahyre": "Instahyre",
    "turtlemint": "turtlemint",
}

def detect_ats(company_name: str, careers_url: str) -> tuple[str, str]:
    """Detect ATS type from known mappings or URL patterns."""
    name_lower = company_name.lower()
    # Check Workday first
    if name_lower in WORKDAY_CONFIGS:
        return "workday", name_lower
    # Check known mappings — SmartRecruiters first (often has more jobs)
    if name_lower in SMARTRECRUITERS_SLUGS:
        return "smartrecruiters", SMARTRECRUITERS_SLUGS[name_lower]
    if name_lower in TURBOHIRE_SLUGS:
        return "turbohire", TURBOHIRE_SLUGS[name_lower]
    if name_lower in WORKABLE_SLUGS:
        return "workable", WORKABLE_SLUGS[name_lower]
    if name_lower in RECRUITEE_SLUGS:
        return "recruitee", RECRUITEE_SLUGS[name_lower]
    if name_lower in BREEZY_SLUGS:
        return "breezy", BREEZY_SLUGS[name_lower]
    if name_lower in HIREHIVE_SLUGS:
        return "hirehive", HIREHIVE_SLUGS[name_lower]
    if name_lower in GREENHOUSE_SLUGS:
        return "greenhouse", GREENHOUSE_SLUGS[name_lower]
    if name_lower in LEVER_SLUGS:
        return "lever", LEVER_SLUGS[name_lower]
    if name_lower in ASHBY_SLUGS:
        return "ashby", ASHBY_SLUGS[name_lower]
    # Check URL patterns
    m = re.search(r'lever\.co/([a-zA-Z0-9_-]+)', careers_url)
    if m:
        return "lever", m.group(1)
    m = re.search(r'greenhouse\.io/([a-zA-Z0-9_-]+)', careers_url)
    if m:
        return "greenhouse", m.group(1)
    m = re.search(r'ashbyhq\.com/([a-zA-Z0-9_-]+)', careers_url)
    if m:
        return "ashby", m.group(1)
    if "smartrecruiters" in careers_url.lower():
        m = re.search(r'smartrecruiters\.com/([a-zA-Z0-9_-]+)', careers_url)
        if m:
            return "smartrecruiters", m.group(1)
    if "turbohire" in careers_url.lower():
        m = re.search(r'orgId=([a-f0-9-]+)', careers_url)
        if m:
            return "turbohire", m.group(1)
    if "workable.com" in careers_url.lower():
        m = re.search(r'workable\.com/([a-zA-Z0-9_-]+)', careers_url)
        if m:
            return "workable", m.group(1)
    if "recruitee.com" in careers_url.lower():
        m = re.search(r'([a-zA-Z0-9_-]+)\.recruitee\.com', careers_url)
        if m:
            return "recruitee", m.group(1)
    if "breezy.hr" in careers_url.lower():
        m = re.search(r'([a-zA-Z0-9_-]+)\.breezy\.hr', careers_url)
        if m:
            return "breezy", m.group(1)
    if "hirehive.com" in careers_url.lower():
        m = re.search(r'([a-zA-Z0-9_-]+)\.hirehive\.com', careers_url)
        if m:
            return "hirehive", m.group(1)
    return "unknown", ""


# ─── COMPANY-SPECIFIC SEARCH URL PATTERNS ──────────────
COMPANY_SEARCH_PATTERNS = {
    "accenture": "https://www.accenture.com/in-en/careers/jobsearch?q={query}&pg=1",
    "google": "https://www.google.com/about/careers/applications/jobs/results?q={query}&location=India",
    "microsoft": "https://careers.microsoft.com/global/en/search?q={query}&l=India",
    "amazon": "https://www.amazon.jobs/en/search?base_query={query}&loc_query=India",
    "meta": "https://www.metacareers.com/jobs?q={query}",
    "apple": "https://jobs.apple.com/en-in/search?search={query}&location=india-INDC",
    "salesforce": "https://careers.salesforce.com/en/jobs/?search={query}&country=India",
    "oracle": "https://careers.oracle.com/jobs/#en/sites/jobsearch/requisitions?keyword={query}",
    "adobe": "https://careers.adobe.com/us/en/search-results?keywords={query}",
    "nvidia": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite?q={query}",
    "ibm": "https://www.ibm.com/careers/search?field_keyword_18[0]={query}",
    "tcs": "https://ibegin.tcs.com/iBegin/jobs?q={query}",
    "infosys": "https://career.infosys.com/joblist?q={query}",
    "flipkart": "https://www.flipkartcareers.com/#!/joblist?q={query}",
    "razorpay": "https://razorpay.com/careers/?q={query}",
    "cisco": "https://jobs.cisco.com/jobs/SearchJobs?21178={query}&21178_format=6020",
    "dell": "https://jobs.dell.com/search-jobs/{query}",
    "atlassian": "https://www.atlassian.com/company/careers/all-jobs?search={query}&location=India",
    "deloitte": "https://apply.deloitte.com/careers/SearchJobs?keyword={query}",
    "bcg": "https://careers.bcg.com/job-search?q={query}",
    "databricks": "https://www.databricks.com/company/careers/open-positions?q={query}",
    "stripe": "https://stripe.com/jobs/search?q={query}",
    "servicenow": "https://careers.servicenow.com/jobs/search?q={query}",
    "snowflake": "https://careers.snowflake.com/us/en/search-results?keywords={query}",
    "swiggy": "https://careers.swiggy.com/#/careers?query={query}",
    "zomato": "https://www.zomato.com/careers?query={query}",
    "phonepe": "https://www.phonepe.com/careers/openings/?q={query}",
    "freshworks": "https://www.freshworks.com/company/careers/jobs/?q={query}",
    "zoho": "https://www.zoho.com/careers/jobs/?q={query}",
    "postman": "https://www.postman.com/company/careers/open-positions/?q={query}",
}

def get_search_url(company_name: str, base_url: str, role: str) -> list[str]:
    """Get the best search URLs for a company."""
    key = company_name.lower().replace(" india", "").replace(" ", "")
    query = role.replace(" ", "+")
    if key in COMPANY_SEARCH_PATTERNS:
        pattern = COMPANY_SEARCH_PATTERNS[key]
        return [pattern.format(base=base_url.rstrip("/"), query=query)]
    # Generic fallback patterns
    return [
        f"{base_url}?q={query}",
        f"{base_url}?query={query}",
        f"{base_url}?keyword={query}",
        f"{base_url}/search?q={query}",
    ]


# ─── PLAYWRIGHT SCANNER (FALLBACK) ─────────────────────

async def scan_company_browser(browser, company: dict, roles: list[str], timeout: int = 15000) -> list[dict]:
    """Scan using Playwright browser — fallback for unknown ATS."""
    jobs = []
    url = company["careers_url"]
    name = company["name"]

    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    page = await context.new_page()

    try:
        async with asyncio.timeout(50):
            for role in roles[:2]:
                search_urls = get_search_url(name, url, role)
                for search_url in search_urls[:2]:
                    try:
                        # Use networkidle for iCIMS/SPA pages
                        try:
                            await page.goto(search_url, wait_until="networkidle", timeout=20000)
                        except Exception:
                            await page.goto(search_url, wait_until="domcontentloaded", timeout=timeout)
                        # Wait for JS to render job listings
                        try:
                            await page.wait_for_selector('a[href*="job"], a[href*="position"], a[href*="detail"], a[href*="requisition"], a[href*="opening"], [class*="job-title"], [class*="jobTitle"]', timeout=10000)
                        except Exception:
                            try:
                                await page.wait_for_load_state("networkidle", timeout=8000)
                            except Exception:
                                await page.wait_for_timeout(6000)

                        results = await page.evaluate("""() => {
                            const jobs = [];
                            // Strategy A: Standard link extraction
                            const allLinks = document.querySelectorAll('a');
                            for (const link of allLinks) {
                                const href = link.getAttribute('href') || '';
                                const text = link.textContent.trim().replace(/\\s+/g, ' ');
                                if (text.length < 15 || text.length > 300) continue;
                                const hrefLower = href.toLowerCase();
                                const isJobUrl = (
                                    /\\/jobs?\\/[a-z0-9\\-]+/i.test(href) ||
                                    /\\/position[s]?\\/[a-z0-9\\-]+/i.test(href) ||
                                    /\\/opening[s]?\\/[a-z0-9\\-]+/i.test(href) ||
                                    /\\/requisition[s]?\\/[a-z0-9]+/i.test(href) ||
                                    /\\/details?\\/[a-z0-9\\-]+/i.test(href) ||
                                    /jobdetails/i.test(href) ||
                                    /\\/[a-f0-9\\-]{20,}/i.test(href) ||
                                    hrefLower.includes('lever.co/') ||
                                    hrefLower.includes('greenhouse.io/') ||
                                    hrefLower.includes('ashbyhq.com/') ||
                                    hrefLower.includes('workday') ||
                                    hrefLower.includes('smartrecruiters') ||
                                    hrefLower.includes('icims') ||
                                    hrefLower.includes('myworkday') ||
                                    hrefLower.includes('successfactors') ||
                                    hrefLower.includes('taleo')
                                );
                                if (!isJobUrl) continue;
                                if (/\\/(content|programs?|categories|teams|locations|about|blog|culture)\\//i.test(href)) continue;
                                jobs.push({title: text, url: link.href});
                            }
                            // Strategy B: Extract from job listing cards (iCIMS, Phenom, custom)
                            const cardSelectors = [
                                '[class*="job-title"]', '[class*="jobTitle"]', '[class*="job-name"]',
                                '[class*="position-title"]', '[class*="posting-title"]',
                                '[data-job-title]', 'h3 a', 'h4 a',
                                '.job-card a', '.job-listing a', '.career-item a',
                            ];
                            for (const sel of cardSelectors) {
                                const els = document.querySelectorAll(sel);
                                for (const el of els) {
                                    const a = el.tagName === 'A' ? el : el.querySelector('a') || el.closest('a');
                                    if (a) {
                                        const text = (el.textContent || '').trim().replace(/\\s+/g, ' ');
                                        const href = a.getAttribute('href') || '';
                                        if (text.length > 5 && text.length < 200 && href) {
                                            jobs.push({title: text, url: a.href});
                                        }
                                    }
                                }
                            }
                            // Deduplicate
                            const seen = new Set();
                            return jobs.filter(j => {
                                const key = j.url;
                                if (seen.has(key)) return false;
                                seen.add(key);
                                return true;
                            });
                        }""")
                        for r in results:
                            title = r["title"].strip()
                            if is_garbage_title(title):
                                continue
                            jobs.append({"title": title, "company": name, "url": r["url"],
                                         "location": "", "description": "", "source": "company_website"})
                        if jobs:
                            break
                    except Exception:
                        continue
                if jobs:
                    break
                await asyncio.sleep(1)
    except asyncio.TimeoutError:
        print(f"  ⏰ {name}: timed out", flush=True)
    except Exception as e:
        print(f"  ❌ {name}: {str(e)[:100]}", flush=True)
    finally:
        await context.close()
    return jobs


# ─── HYBRID SCAN: API first, browser fallback ──────────
async def scan_company_hybrid(browser, company: dict, roles: list[str], client: httpx.AsyncClient,
                              llm_provider: str = "deepseek", llm_key: str = "",
                              db=None, company_id: int = 0) -> list[dict]:
    """Try ATS API first (instant), then browser, then Google search as last resort."""
    name = company["name"]
    url = company["careers_url"]
    ats_type, slug = detect_ats(name, url)

    # Check ATS patterns if detect_ats returned unknown
    if ats_type == "unknown" and company_id:
        pattern = _check_ats_patterns(name)
        if pattern:
            ats_type, slug = pattern[0], pattern[1]
            print(f"  [learn] {name}: found ATS pattern → {ats_type}", flush=True)

    # Try API first
    if ats_type == "workday":
        config = WORKDAY_CONFIGS.get(slug)
        if config:
            tenant, wd_server, site = config
            jobs = await _fetch_workday_jobs(tenant, wd_server, site, client)
            if jobs:
                for j in jobs: j["company"] = name; j["source"] = "workday_api"
                print(f"  ⚡ {name}: {len(jobs)} jobs via Workday API", flush=True)
                if db and company_id:
                    _record_scan_outcome(db, company_id, "ats_api", True, len(jobs))
                return jobs

    if ats_type == "lever" and slug:
        jobs = await _fetch_lever_jobs(slug, client)
        if jobs:
            for j in jobs: j["company"] = name; j["source"] = "lever_api"
            print(f"  ⚡ {name}: {len(jobs)} jobs via Lever API", flush=True)
            if db and company_id:
                _record_scan_outcome(db, company_id, "ats_api", True, len(jobs))
            return jobs

    if ats_type == "greenhouse" and slug:
        jobs = await _fetch_greenhouse_jobs(slug, client)
        if jobs:
            for j in jobs: j["company"] = name; j["source"] = "greenhouse_api"
            print(f"  ⚡ {name}: {len(jobs)} jobs via Greenhouse API", flush=True)
            if db and company_id:
                _record_scan_outcome(db, company_id, "ats_api", True, len(jobs))
            return jobs

    if ats_type == "ashby" and slug:
        jobs = await _fetch_ashby_jobs(slug, client)
        if jobs:
            for j in jobs: j["company"] = name; j["source"] = "ashby_api"
            print(f"  ⚡ {name}: {len(jobs)} jobs via Ashby API", flush=True)
            if db and company_id:
                _record_scan_outcome(db, company_id, "ats_api", True, len(jobs))
            return jobs

    if ats_type == "smartrecruiters" and slug:
        jobs = await _fetch_smartrecruiters_jobs(slug, client)
        if jobs:
            for j in jobs: j["company"] = name; j["source"] = "smartrecruiters_api"
            print(f"  ⚡ {name}: {len(jobs)} jobs via SmartRecruiters API", flush=True)
            if db and company_id:
                _record_scan_outcome(db, company_id, "ats_api", True, len(jobs))
            return jobs

    if ats_type == "turbohire" and slug:
        jobs = await _fetch_turbohire_jobs(slug, name, client)
        if jobs:
            for j in jobs: j["source"] = "turbohire_api"
            print(f"  ⚡ {name}: {len(jobs)} jobs via TurboHire API", flush=True)
            if db and company_id:
                _record_scan_outcome(db, company_id, "ats_api", True, len(jobs))
            return jobs

    if ats_type == "workable" and slug:
        jobs = await _fetch_workable_jobs(slug, client)
        if jobs:
            for j in jobs: j["company"] = name; j["source"] = "workable_api"
            print(f"  ⚡ {name}: {len(jobs)} jobs via Workable API", flush=True)
            if db and company_id:
                _record_scan_outcome(db, company_id, "ats_api", True, len(jobs))
            return jobs

    if ats_type == "recruitee" and slug:
        jobs = await _fetch_recruitee_jobs(slug, client)
        if jobs:
            for j in jobs: j["company"] = name; j["source"] = "recruitee_api"
            print(f"  ⚡ {name}: {len(jobs)} jobs via Recruitee API", flush=True)
            if db and company_id:
                _record_scan_outcome(db, company_id, "ats_api", True, len(jobs))
            return jobs

    if ats_type == "breezy" and slug:
        jobs = await _fetch_breezy_jobs(slug, client)
        if jobs:
            for j in jobs: j["company"] = name; j["source"] = "breezy_api"
            print(f"  ⚡ {name}: {len(jobs)} jobs via Breezy API", flush=True)
            if db and company_id:
                _record_scan_outcome(db, company_id, "ats_api", True, len(jobs))
            return jobs

    if ats_type == "hirehive" and slug:
        jobs = await _fetch_hirehive_jobs(slug, client)
        if jobs:
            for j in jobs: j["company"] = name; j["source"] = "hirehive_api"
            print(f"  ⚡ {name}: {len(jobs)} jobs via HireHive API", flush=True)
            if db and company_id:
                _record_scan_outcome(db, company_id, "ats_api", True, len(jobs))
            return jobs

    # Skip browser scraping for known Darwinbox companies — go straight to vision agent
    is_darwinbox = name.lower() in DARWINBOX_COMPANIES

    if not is_darwinbox:
        # Try browser scraping
        print(f"  🌐 {name}: trying Playwright browser...", flush=True)
        jobs = await scan_company_browser(browser, company, roles)
    if jobs:
        for j in jobs: j["source"] = "browser"
        print(f"  🌐 {name}: {len(jobs)} jobs via browser", flush=True)
        if db and company_id:
            _record_scan_outcome(db, company_id, "browser", True, len(jobs))
        return jobs
    elif db and company_id and not is_darwinbox:
        _record_scan_outcome(db, company_id, "browser", False, 0)

    # Try HTML source parsing (for SPAs that embed data)
    if not is_darwinbox:
        domain = url.replace("https://", "").replace("http://", "").split("/")[0]
        print(f"  📄 {name}: trying HTML parsing...", flush=True)
        html_jobs = await _fetch_via_google(name, domain, roles[0] if roles else "manager", client)
        if html_jobs:
            for j in html_jobs: j["source"] = "html_parse"
            print(f"  📄 {name}: {len(html_jobs)} jobs via HTML parsing", flush=True)
            if db and company_id:
                _record_scan_outcome(db, company_id, "html_parse", True, len(html_jobs))
            return html_jobs
        elif db and company_id:
            _record_scan_outcome(db, company_id, "html_parse", False, 0)

    # Try LinkedIn public job search (no login required)
    if not is_darwinbox:
        try:
            linkedin_jobs = await _fetch_linkedin_jobs(name, roles[0] if roles else "manager", client)
            if linkedin_jobs:
                for j in linkedin_jobs: j["source"] = "linkedin"
                print(f"  💼 {name}: {len(linkedin_jobs)} jobs via LinkedIn", flush=True)
                if db and company_id:
                    _record_scan_outcome(db, company_id, "linkedin", True, len(linkedin_jobs))
                return linkedin_jobs
            elif db and company_id:
                _record_scan_outcome(db, company_id, "linkedin", False, 0)
        except Exception:
            if db and company_id:
                _record_scan_outcome(db, company_id, "linkedin", False, 0)

    # Final fallback: Vision-based AI browser agent (screenshot + Gemini)
    # Use Google Gemini for vision navigation (free tier, 250 req/day)
    try:
        from ai_browser_vision import vision_scan_company
        # Get Google API key from user's LLM settings or env
        google_key = ""
        if llm_key and llm_provider == "google":
            google_key = llm_key
        else:
            # Check user's saved Google key
            from models import UserLLMSettings
            from auth import get_db
            try:
                sdb = next(get_db())
                settings = sdb.query(UserLLMSettings).filter_by(user_id=None).first()  # TODO: need user_id
                sdb.close()
            except:
                pass
            # Fallback to env var
            import os
            if not google_key:
                google_key = os.environ.get("GOOGLE_AI_KEY", "")

        if google_key:
            print(f"  🔭 {name}: trying vision browser agent (Gemini)...", flush=True)
            ai_jobs = await asyncio.wait_for(
                vision_scan_company(browser, company, roles, provider="google", api_key=google_key, db=db, company_id=company_id),
                timeout=1200  # 20 min
            )
            if ai_jobs:
                if db and company_id:
                    _record_scan_outcome(db, company_id, "vision", True, len(ai_jobs))
                return ai_jobs
    except asyncio.TimeoutError:
        print(f"  ⏰ {name}: vision browser timed out", flush=True)
    except Exception as e:
        print(f"  ❌ {name}: vision browser error: {str(e)[:80]}", flush=True)

    if db and company_id:
        _record_scan_outcome(db, company_id, "vision", False, 0)
    return []


async def fetch_job_description(browser, url: str, timeout: int = 15000) -> str:
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        # Wait for content to render
        try:
            await page.wait_for_selector('[class*="description"], [class*="job-detail"], [class*="posting"], article, main', timeout=6000)
        except Exception:
            await page.wait_for_timeout(4000)

        desc = await page.evaluate("""() => {
            const selectors = [
                '[class*="description"]', '[class*="job-detail"]',
                '[class*="posting"]', '[id*="description"]',
                '[class*="content"]', 'article', 'main'
            ];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el && el.textContent.trim().length > 200) {
                    return el.textContent.trim().substring(0, 8000);
                }
            }
            return document.body?.textContent?.trim()?.substring(0, 5000) || '';
        }""")
        return desc
    except Exception:
        return ""
    finally:
        await context.close()


# ─── MAIN SEARCH RUNNER ────────────────────────────────
async def _process_one_company(
    browser, company, target_roles, db, user_id, user_profile, search_run_id, results, lock, client,
    llm_provider: str = "deepseek", llm_key: str = ""
):
    from cv_parser import score_job_match
    company_matched = 0
    MAX_JOBS_TO_SCORE = 30  # Cap AI scoring per company to prevent timeouts

    # Build role keywords for title-based pre-filtering
    role_keywords = set()
    for role in target_roles:
        for word in role.lower().split():
            if len(word) > 3 and word not in {"the", "and", "for", "with"}:
                role_keywords.add(word)
    # Always include common management/business keywords
    role_keywords.update({"manager", "product", "account", "project", "program",
                          "strategy", "director", "lead", "head", "business",
                          "operations", "delivery", "growth", "revenue", "sales",
                          "marketing", "analyst", "consultant", "advisor"})

    try:
        company_record = db.query(Company).filter_by(name=company["name"]).first()
        company_id = company_record.id if company_record else 0
        company_jobs = await scan_company_hybrid(browser, company, target_roles, client,
                                                llm_provider=llm_provider, llm_key=llm_key,
                                                db=db, company_id=company_id)
    except Exception as e:
        company_jobs = []
        print(f"  ❌ {company['name']}: {e}", flush=True)

    scored_count = 0
    for job_data in company_jobs:
        async with lock:
            existing = db.query(Job).filter_by(url=job_data["url"]).first()
            if not existing:
                # Also check for fuzzy title duplicate within same company
                title_clean = job_data["title"].strip().lower()
                existing = db.query(Job).filter(
                    Job.company == job_data["company"],
                    Job.title.ilike(f"%{title_clean[:30]}%")
                ).first() if len(title_clean) > 10 else None
            if existing:
                job = existing
                # Update last_verified timestamp
                job.last_verified = datetime.utcnow()
                db.flush()
            else:
                job = Job(
                    title=job_data["title"], company=job_data["company"],
                    url=job_data["url"], location=job_data.get("location", ""),
                    description=job_data.get("description", ""),
                    source=job_data.get("source", "company_website"),
                )
                db.add(job)
                db.flush()
                results["jobs_found"] += 1

        # Fetch description if missing (for browser-scraped and vision-agent jobs)
        if (not job.description or len(job.description) < 100) and job_data.get("source") in ("browser", "vision_browser", "html_parse"):
            try:
                desc = await fetch_job_description(browser, job.url)
                if desc:
                    async with lock:
                        job.description = desc[:8000]
                        db.flush()
            except Exception:
                pass

        # Score with LLM (capped per company)
        desc_len = len(job.description or '')
        if desc_len <= 100:
            if desc_len > 0:
                print(f"    ⏭️ Skipped {job.company} - {job.title[:30]}: desc too short ({desc_len})", flush=True)
            continue
        if scored_count >= MAX_JOBS_TO_SCORE:
            continue

        # Skip clearly irrelevant titles and garbage scraped text
        if is_garbage_title(job.title):
            continue

        # Skip exact engineering/design titles to save LLM calls
        SKIP_EXACT = {"software engineer", "sde", "sde 2", "sde 3", "sde 1",
                      "frontend engineer", "backend engineer", "devops engineer",
                      "qa engineer", "test engineer", "ui designer", "ux designer",
                      "graphic designer", "data engineer", "ml engineer",
                      "ios developer", "android developer", "full stack developer"}
        if title_lower in SKIP_EXACT:
            continue

        if True:
            # Pre-filter: skip jobs with KNOWN wrong locations (not empty ones)
            from location_data import location_matches
            pref_locs = user_profile.get('preferred_locations') or []
            job_loc = job.location or ''
            if pref_locs and job_loc.strip():
                # Only skip if location is known AND doesn't match
                if not location_matches(job_loc, pref_locs):
                    print(f"    ⛔ Skipped {job.company} - {job.title[:30]}: loc={job_loc} not in {pref_locs[:3]}", flush=True)
                    continue

            async with lock:
                existing_match = db.query(UserJobMatch).filter_by(user_id=user_id, job_id=job.id).first()
            if not existing_match:
                try:
                    scored_count += 1
                    match = await score_job_match(user_profile, {
                        "title": job.title, "company": job.company,
                        "location": job.location, "description": job.description,
                    }, provider=llm_provider, api_key=llm_key)
                    llm_score = match.get("score", 0)
                    # Apply preference boost from learned user behavior
                    try:
                        from preference_engine import compute_preference_boost
                        boost, boost_explanation = compute_preference_boost(
                            db, user_id, job.title, job.company,
                            match.get("matched_skills", [])
                        )
                    except Exception:
                        boost, boost_explanation = 0.0, ""
                    score = max(0.0, min(1.0, llm_score + boost))
                    boost_str = f" (boost: {boost:+.2f})" if abs(boost) > 0.01 else ""
                    print(f"    📊 {job.company} - {job.title[:40]}: score={score:.2f}{boost_str}", flush=True)
                    # Log promotion/demotion across threshold
                    if boost > 0 and llm_score < 0.60 and score >= 0.60:
                        print(f"    ⬆️ Promoted by preference boost: {llm_score:.2f} → {score:.2f}", flush=True)
                    elif boost < 0 and llm_score >= 0.60 and score < 0.60:
                        print(f"    ⬇️ Demoted by preference boost: {llm_score:.2f} → {score:.2f}", flush=True)
                    if score >= 0.60:
                        async with lock:
                            ujm = UserJobMatch(
                                user_id=user_id, job_id=job.id, search_run_id=search_run_id,
                                match_score=score,
                                match_reason=(match.get("match_reason", "") + boost_explanation),
                                matched_skills=match.get("matched_skills", []),
                                missing_skills=match.get("missing_skills", []),
                                relevance_summary=match.get("relevance_summary", ""),
                            )
                            db.add(ujm)
                            results["jobs_matched"] += 1
                            company_matched += 1
                except Exception as e:
                    print(f"  Score error ({company['name']}): {e}", flush=True)

    # Determine source tier
    source = "none"
    if company_jobs:
        sources = set(j.get("source", "") for j in company_jobs)
        if any("api" in s for s in sources):
            source = "api"
        elif "vision_browser" in sources:
            source = "vision"
        elif "browser" in sources:
            source = "browser"
        elif "html_parse" in sources:
            source = "html"

    return {"company": company["name"], "jobs_found": len(company_jobs), "matched": company_matched, "source": source}


async def run_search(
    db: Session, search_run_id: int, user_id: int,
    user_profile: dict, target_roles: list[str], companies_to_search: list[dict],
    llm_provider: str = "deepseek", llm_key: str = ""
) -> dict:
    from playwright.async_api import async_playwright

    search_run = db.query(SearchRun).get(search_run_id)
    search_run.status = "running"
    search_run.progress_log = [
        {"company": c["name"], "status": "pending", "jobs_found": 0, "matched": 0}
        for c in companies_to_search
    ]
    db.commit()

    results = {"jobs_found": 0, "jobs_matched": 0, "errors": 0}
    lock = asyncio.Lock()
    total = len(companies_to_search)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            semaphore = asyncio.Semaphore(PARALLEL)

            async with httpx.AsyncClient(timeout=20) as client:
                async def run_one(idx, company):
                    async with semaphore:
                        # Check if stopped
                        async with lock:
                            sr = db.query(SearchRun).get(search_run_id)
                            if sr.status == "stopped":
                                return
                            log = list(sr.progress_log or [])
                            log[idx]["status"] = "scanning"
                            sr.progress_log = log
                            db.commit()

                        try:
                            result = await asyncio.wait_for(
                                _process_one_company(
                                    browser, company, target_roles, db,
                                    user_id, user_profile, search_run_id, results, lock, client,
                                    llm_provider=llm_provider, llm_key=llm_key
                                ),
                                timeout=1500  # 25 min max per company
                            )
                        except asyncio.TimeoutError:
                            print(f"  ⏰ {company['name']}: timed out (25min)", flush=True)
                            result = {"company": company["name"], "jobs_found": 0, "matched": 0}

                        async with lock:
                            sr = db.query(SearchRun).get(search_run_id)
                            log = list(sr.progress_log or [])
                            log[idx] = {"company": company["name"], "status": "done",
                                        "jobs_found": result["jobs_found"], "matched": result["matched"],
                                        "source": result.get("source", "")}
                            sr.progress_log = log
                            done_count = sum(1 for e in log if e["status"] == "done")
                            sr.companies_searched = done_count
                            sr.jobs_found = results["jobs_found"]
                            sr.jobs_matched = results["jobs_matched"]
                            db.commit()

                        print(f"  [{done_count}/{total}] {company['name']}: {result['jobs_found']} jobs, {result['matched']} matched", flush=True)

                tasks = [run_one(i, c) for i, c in enumerate(companies_to_search)]
                await asyncio.gather(*tasks, return_exceptions=True)

            # Check if stopped
            sr = db.query(SearchRun).get(search_run_id)
            if sr.status != "stopped":
                sr.status = "completed"
                sr.completed_at = datetime.utcnow()
                db.commit()

            await browser.close()

    except Exception as e:
        sr = db.query(SearchRun).get(search_run_id)
        sr.status = "failed"
        db.commit()
        print(f"Search failed: {e}", flush=True)
        import traceback
        traceback.print_exc()

    return results
