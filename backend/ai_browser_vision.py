"""Vision-based AI Browser Agent — Uses screenshots + vision LLM to extract jobs.

Like the Kiro browser agent: takes screenshots, sends to a vision-capable LLM
(GPT-4o, Gemini), and extracts job listings from what it "sees".

Works on ANY website including React SPAs, because it reads the rendered visual
output, not the DOM.
"""
import asyncio
import base64
import json
import time
from datetime import datetime
import httpx

# Global rate limiter: max 15 requests per minute (Gemini Flash-Lite free tier)
_last_vision_call = 0.0
_vision_lock = asyncio.Lock()


def _save_nav_path(db, company_id: int, steps: list[dict], final_url: str):
    """Persist successful navigation path to vision_nav_cache table."""
    if not db or not company_id:
        return
    try:
        from models import VisionNavCache
        existing = db.query(VisionNavCache).filter_by(company_id=company_id).first()
        now = datetime.utcnow()
        if existing:
            existing.navigation_steps = steps
            existing.final_url = final_url
            existing.last_verified = now
            existing.success_count = (existing.success_count or 0) + 1
        else:
            db.add(VisionNavCache(
                company_id=company_id, navigation_steps=steps,
                final_url=final_url, last_verified=now, success_count=1
            ))
        db.commit()
        print(f"    [vision-cache] Saved nav path ({len(steps)} steps)", flush=True)
    except Exception as e:
        try: db.rollback()
        except: pass
        print(f"    [vision-cache] Failed to save: {e}", flush=True)


async def _replay_nav_path(page, cached_steps: list[dict]) -> bool:
    """Replay cached navigation steps. Returns True if replay completed without errors."""
    try:
        for i, step in enumerate(cached_steps):
            action = step.get("action", "")
            target = step.get("target", "")
            query = step.get("query", "")

            if action == "click" and target:
                # Try to find and click the element by text content
                try:
                    await page.get_by_text(target, exact=False).first.click(timeout=5000)
                    await asyncio.sleep(2)
                except:
                    # Try by role/label as fallback
                    try:
                        await page.get_by_role("link", name=target).first.click(timeout=3000)
                        await asyncio.sleep(2)
                    except:
                        print(f"    [vision-cache] Replay failed at step {i}: click '{target}'", flush=True)
                        return False
            elif action == "search" and query:
                # Find search input and type query
                try:
                    search_input = page.locator('input[type="search"], input[type="text"], input[placeholder*="search" i], input[placeholder*="keyword" i], input[aria-label*="search" i]').first
                    await search_input.fill(query, timeout=5000)
                    await search_input.press("Enter")
                    await asyncio.sleep(3)
                except:
                    print(f"    [vision-cache] Replay failed at step {i}: search '{query}'", flush=True)
                    return False
            elif action == "navigate" and target:
                try:
                    await page.goto(target, wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(2)
                except:
                    print(f"    [vision-cache] Replay failed at step {i}: navigate '{target[:50]}'", flush=True)
                    return False

        print(f"    [vision-cache] Replay completed ({len(cached_steps)} steps)", flush=True)
        return True
    except Exception as e:
        print(f"    [vision-cache] Replay error: {e}", flush=True)
        return False

async def _rate_limit():
    """Ensure at least 2.5 seconds between vision API calls (24 RPM safe for 30 RPM limit)."""
    global _last_vision_call
    async with _vision_lock:
        now = time.time()
        elapsed = now - _last_vision_call
        if elapsed < 2.5:
            wait = 2.5 - elapsed
            await asyncio.sleep(wait)
        _last_vision_call = time.time()


async def _take_screenshot_base64(page) -> str:
    """Take a screenshot and return as base64 string. Uses JPEG for smaller size."""
    screenshot_bytes = await page.screenshot(full_page=False, type="jpeg", quality=60)
    return base64.b64encode(screenshot_bytes).decode("utf-8")


async def _ask_vision_llm(screenshot_b64: str, prompt: str, provider: str, api_key: str) -> str:
    """Send a screenshot to a vision-capable LLM and get a text response."""
    await _rate_limit()  # Enforce 15 RPM limit

    if provider == "openrouter":
        return await _call_openrouter_vision(api_key, screenshot_b64, prompt)
    elif provider == "openai":
        return await _call_openai_vision(api_key, screenshot_b64, prompt)
    elif provider == "google":
        return await _call_google_vision(api_key, screenshot_b64, prompt)
    elif provider == "anthropic":
        return await _call_anthropic_vision(api_key, screenshot_b64, prompt)
    else:
        raise ValueError(f"Vision not supported for provider '{provider}'. Use openrouter, openai, google, or anthropic.")


async def _call_openrouter_vision(api_key: str, img_b64: str, prompt: str) -> str:
    """Call OpenRouter API with vision model (Gemma 4 26B free)."""
    async with httpx.AsyncClient(timeout=120) as client:
        for attempt in range(3):
            try:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://monkeyking.ai",
                        "X-Title": "MonkeyKing Job Search",
                    },
                    json={
                        "model": "google/gemma-4-26b-a4b-it:free",
                        "messages": [{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                            ],
                        }],
                        "max_tokens": 4096,
                        "temperature": 0.1,
                    },
                )
                if resp.status_code == 429:
                    wait = 15 * (attempt + 1)
                    print(f"    [vision] Rate limited, waiting {wait}s...", flush=True)
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < 2:
                    wait = 15 * (attempt + 1)
                    print(f"    [vision] Rate limited, waiting {wait}s...", flush=True)
                    await asyncio.sleep(wait)
                    continue
                raise
    return ""


async def _call_openai_vision(api_key: str, img_b64: str, prompt: str) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "high"}},
                    ],
                }],
                "max_tokens": 4096,
                "temperature": 0.1,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def _call_google_vision(api_key: str, img_b64: str, prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={api_key}"
    async with httpx.AsyncClient(timeout=60) as client:
        for attempt in range(3):
            resp = await client.post(url, json={
                "contents": [{"parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
                ]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096},
            })
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"    [vision] Gemini 429, waiting {wait}s...", flush=True)
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    raise Exception("Gemini rate limited after 3 retries")


async def _call_anthropic_vision(api_key: str, img_b64: str, prompt: str) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4096,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                        {"type": "text", "text": prompt},
                    ],
                }],
            },
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]


def _parse_json_response(text: str) -> list | dict:
    """Extract JSON from LLM response that may contain markdown."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    try:
        return json.loads(text)
    except:
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except:
                pass
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except:
                pass
    return []


async def _extract_all_jobs_with_scroll(page, company_name: str, provider: str, api_key: str,
                                        max_scrolls: int = 8) -> list[dict]:
    """Extract jobs by scrolling through the page and taking multiple screenshots."""
    all_jobs = []
    seen_titles = set()

    for scroll_idx in range(max_scrolls):
        screenshot = await _take_screenshot_base64(page)
        extract_prompt = f"""Look at this careers/jobs page for {company_name}. 
Extract ALL job listings visible on screen right now.

For each job provide:
- title: exact job title
- location: location if shown (city, country, or "Remote")
- url: the job URL if visible (otherwise empty string)

Return ONLY a JSON array. Example:
[{{"title": "Product Manager", "location": "Bangalore, India", "url": "https://..."}}]

If no job listings are visible, return []
IMPORTANT: Only extract actual job postings, not navigation links or page headers."""

        try:
            result = await _ask_vision_llm(screenshot, extract_prompt, provider, api_key)
            jobs = _parse_json_response(result)
            new_count = 0
            if isinstance(jobs, list):
                for j in jobs:
                    if isinstance(j, dict) and j.get("title"):
                        title_key = j["title"].lower().strip()
                        if title_key not in seen_titles:
                            seen_titles.add(title_key)
                            all_jobs.append({
                                "title": j.get("title", ""),
                                "url": j.get("url", "") or page.url,
                                "location": j.get("location", ""),
                                "company": company_name,
                                "description": "",
                                "source": "vision_browser",
                            })
                            new_count += 1

            # If no new jobs found after scrolling, stop
            if new_count == 0 and scroll_idx > 0:
                break

            # Scroll down for more jobs
            if scroll_idx < max_scrolls - 1:
                await page.evaluate("window.scrollBy(0, 800)")
                await asyncio.sleep(2)

        except Exception as e:
            print(f"    [vision] Scroll {scroll_idx+1} error: {str(e)[:60]}", flush=True)
            break

    return all_jobs


async def _fetch_jd_via_vision(page, job: dict, company_name: str, provider: str, api_key: str) -> str:
    """Click into a job listing and extract the full job description using vision."""
    job_url = job.get("url", "")
    job_title = job.get("title", "")

    if not job_url or job_url == page.url:
        # No individual job URL — try clicking the job title text on the current page
        try:
            link = page.get_by_text(job_title, exact=False).first
            if await link.count() > 0:
                await link.click(timeout=5000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=8000)
                except:
                    await asyncio.sleep(3)
            else:
                return ""
        except:
            return ""
    else:
        # Navigate to the job URL
        try:
            await page.goto(job_url, wait_until="domcontentloaded", timeout=15000)
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except:
                await asyncio.sleep(3)
        except:
            return ""

    # Take screenshot and extract JD
    try:
        screenshot = await _take_screenshot_base64(page)
        jd_prompt = f"""Look at this job posting page for "{job_title}" at {company_name}.

Extract the FULL job description text — include:
- Role overview/summary
- Responsibilities
- Requirements/qualifications
- Nice-to-haves
- Any mentioned experience level, skills, location

Return ONLY the plain text of the job description. No JSON, no formatting — just the text content."""

        jd_text = await _ask_vision_llm(screenshot, jd_prompt, provider, api_key)

        # Scroll down and get more if the JD is long
        if jd_text and len(jd_text) > 200:
            await page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(2)
            screenshot2 = await _take_screenshot_base64(page)
            more_prompt = f"""Continue reading the job description for "{job_title}" at {company_name}.
Extract any additional text visible on screen that wasn't in the first part.
If you see requirements, qualifications, or skills sections, include them.
Return ONLY the additional text. If nothing new, return EMPTY."""

            try:
                more_text = await _ask_vision_llm(screenshot2, more_prompt, provider, api_key)
                if more_text and len(more_text) > 50 and "empty" not in more_text.lower():
                    jd_text += "\n\n" + more_text
            except:
                pass

        return (jd_text or "")[:8000]
    except Exception as e:
        print(f"    [vision] JD fetch error for {job_title}: {str(e)[:60]}", flush=True)
        return ""


async def vision_scan_company(browser, company: dict, target_roles: list[str],
                               provider: str = "openai", api_key: str = "",
                               max_steps: int = 15, db=None, company_id: int = 0) -> list[dict]:
    """Use screenshot + vision LLM to navigate and extract jobs from any website.

    Flow:
    1. Open careers page, take screenshot
    2. Vision LLM sees the page and decides: what to click or where to search
    3. Navigate, take another screenshot
    4. Vision LLM extracts job listings from what it sees
    """
    url = company["careers_url"]
    name = company["name"]
    role_query = target_roles[0] if target_roles else "Product Manager"
    # Search all target roles for thorough coverage
    roles_to_search = target_roles if target_roles else ["Product Manager"]

    ctx = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 900},
    )
    page = await ctx.new_page()
    all_jobs = []

    try:
        # Step 1: Open careers page
        print(f"    [vision] Opening {url}...", flush=True)
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except:
            await asyncio.sleep(3)

        # Check vision nav cache
        if db and company_id:
            try:
                from models import VisionNavCache
                cached = db.query(VisionNavCache).filter_by(company_id=company_id).first()
                if cached and cached.navigation_steps:
                    age_days = (datetime.utcnow() - cached.last_verified).days if cached.last_verified else 999
                    if age_days <= 30:
                        print(f"    [vision-cache] Replaying cached path ({cached.success_count} prev successes)...", flush=True)
                        replay_ok = await _replay_nav_path(page, cached.navigation_steps)
                        if replay_ok:
                            # Try extracting jobs from the replayed page
                            cache_jobs = await _extract_all_jobs_with_scroll(page, name, provider, api_key)
                            if cache_jobs:
                                print(f"    [vision-cache] Cache hit: {len(cache_jobs)} jobs", flush=True)
                                cached.last_verified = datetime.utcnow()
                                cached.success_count = (cached.success_count or 0) + 1
                                try: db.commit()
                                except: pass
                                # Deduplicate and return
                                seen = set()
                                unique = []
                                for j in cache_jobs:
                                    key = j["title"].lower().strip()
                                    if key not in seen:
                                        seen.add(key)
                                        unique.append(j)
                                return unique[:50]
                        # Cache miss — delete stale cache and fall through to full scan
                        print(f"    [vision-cache] Cache miss — falling back to full scan", flush=True)
                        try:
                            db.delete(cached)
                            db.commit()
                        except: pass
                        # Re-navigate to careers page
                        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        try: await page.wait_for_load_state("networkidle", timeout=10000)
                        except: await asyncio.sleep(3)
            except Exception as e:
                print(f"    [vision-cache] Cache check error: {e}", flush=True)

        # Search for each target role
        for role_idx, role_query in enumerate(roles_to_search):
            if role_idx > 0:
                # Navigate back to careers page for next role search
                print(f"    [vision] Searching role {role_idx+1}: {role_query[:40]}...", flush=True)
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    try:
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except:
                        await asyncio.sleep(3)
                except:
                    break

            # Navigate with LLM guidance (max 15 steps per role for thorough coverage)
            for step in range(max_steps):
                # Rate limit spacing — wait between vision calls
                if step > 0:
                    await asyncio.sleep(2)

                screenshot = await _take_screenshot_base64(page)

            if step == 0:
                # First step: navigate to jobs page
                nav_prompt = f"""Look at this careers page for {name}. I need to find job listings for "{role_query}".

What should I do next? Options:
1. If you see a "Jobs", "Opportunities", "Open Positions", or "Careers" link/button, tell me to click it.
2. If you see a search box, tell me to search for "{role_query}".
3. If you can already see job listings on this page, tell me to extract them.

Return ONLY JSON:
{{"action": "click", "target": "text of the button/link to click"}}
or {{"action": "search", "query": "{role_query}"}}
or {{"action": "extract"}}"""
            else:
                # Subsequent steps: try to extract or navigate further
                nav_prompt = f"""Look at this page from {name}'s careers site. I'm looking for job listings for "{role_query}".

Can you see any job listings (job titles with links)? If yes, extract them.
If not, what should I click to find them?

Return ONLY JSON:
{{"action": "click", "target": "text of button/link"}}
or {{"action": "search", "query": "{role_query}"}}
or {{"action": "extract"}}
or {{"action": "done", "reason": "why"}}"""

            try:
                response = await _ask_vision_llm(screenshot, nav_prompt, provider, api_key)
                action = _parse_json_response(response)
                if isinstance(action, list):
                    action = action[0] if action else {"action": "done"}
                if not isinstance(action, dict):
                    action = {"action": "done"}
            except Exception as e:
                print(f"    [vision] LLM error: {str(e)[:80]}", flush=True)
                break

            act = action.get("action", "done")
            print(f"    [vision] Step {step+1}: {act} — {action.get('target', action.get('query', action.get('reason', '')))[:60]}", flush=True)

            if act == "click":
                target = action.get("target", "")
                if target:
                    try:
                        # Click by visible text
                        link = page.get_by_text(target, exact=False).first
                        await link.click(timeout=5000)
                        try:
                            await page.wait_for_load_state("networkidle", timeout=8000)
                        except:
                            await asyncio.sleep(3)
                    except:
                        try:
                            # Fallback: click by role
                            link = page.get_by_role("link", name=target).first
                            await link.click(timeout=5000)
                            await asyncio.sleep(3)
                        except:
                            pass

            elif act == "search":
                query = action.get("query", role_query)
                try:
                    search_input = page.locator('input[type="search"], input[type="text"], input[placeholder*="search" i], input[placeholder*="job" i], input[placeholder*="role" i]').first
                    if await search_input.count() > 0:
                        await search_input.fill(query)
                        await search_input.press("Enter")
                        # Wait longer for search results to load
                        try:
                            await page.wait_for_load_state("networkidle", timeout=10000)
                        except:
                            await asyncio.sleep(5)
                        # Extra wait for SPA rendering
                        await asyncio.sleep(3)
                except:
                    pass
                # After search, always try extraction on next step
                await asyncio.sleep(2)  # Rate limit spacing

            elif act == "extract":
                # Extract jobs with scrolling to find ALL listings
                all_extract = await _extract_all_jobs_with_scroll(page, name, provider, api_key)
                all_jobs.extend(all_extract)
                print(f"    [vision] Extracted {len(all_extract)} jobs (with scroll)", flush=True)
                break

            elif act == "done":
                break

        # Final attempt: if no jobs yet, try extracting from current page with scroll
        if not all_jobs:
            print(f"    [vision] Final extraction with scroll...", flush=True)
            final_jobs = await _extract_all_jobs_with_scroll(page, name, provider, api_key)
            all_jobs.extend(final_jobs)
            print(f"    [vision] Final: {len(all_jobs)} jobs", flush=True)

        # Deduplicate
        seen = set()
        unique = []
        for j in all_jobs:
            key = j["title"].lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(j)

        # Save navigation path to cache for future replays
        if all_jobs and db and company_id:
            nav_steps = [{"action": "navigate", "target": page.url}]
            _save_nav_path(db, company_id, nav_steps, page.url)

        # Fetch JDs for jobs that don't have descriptions (up to 10 jobs)
        jobs_needing_jd = [j for j in unique if not j.get("description")][:10]
        if jobs_needing_jd:
            print(f"    [vision] Fetching JDs for {len(jobs_needing_jd)} jobs...", flush=True)
            # Save current URL to navigate back
            listing_url = page.url
            for j in jobs_needing_jd:
                jd = await _fetch_jd_via_vision(page, j, name, provider, api_key)
                if jd and len(jd) > 100:
                    j["description"] = jd
                    print(f"    [vision] Got JD for {j['title'][:40]} ({len(jd)} chars)", flush=True)
                # Navigate back to listings page for next job
                try:
                    await page.goto(listing_url, wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(2)
                except:
                    pass

        if unique:
            print(f"  🔭 {name}: {len(unique)} jobs via vision browser agent", flush=True)
        return unique[:50]

    except Exception as e:
        print(f"    [vision] Error: {str(e)[:100]}", flush=True)
        return []
    finally:
        await ctx.close()
