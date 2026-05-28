"""AI Browser Agent — Uses LLM + Playwright to autonomously navigate career pages.

For companies without known ATS APIs, this agent:
1. Opens the careers page
2. Asks the LLM what to click to find job listings
3. Navigates to the jobs page
4. Searches for relevant roles
5. Extracts job titles, URLs, locations, and descriptions

Works with any LLM provider (DeepSeek, OpenAI, etc.) via the llm_engine.
"""
import asyncio
import json
import re
from typing import Optional


async def _get_page_context(page, max_links: int = 50) -> str:
    """Extract a simplified view of the page for the LLM."""
    try:
        context = await page.evaluate(f"""() => {{
            const result = {{
                url: window.location.href,
                title: document.title,
                links: [],
                inputs: [],
                buttons: [],
            }};

            // Get visible links
            const links = document.querySelectorAll('a[href]');
            const seen = new Set();
            for (const a of links) {{
                const text = a.textContent.trim().replace(/\\s+/g, ' ').substring(0, 80);
                const href = a.getAttribute('href') || '';
                if (!text || text.length < 2 || seen.has(href)) continue;
                seen.add(href);
                const rect = a.getBoundingClientRect();
                if (rect.width === 0 && rect.height === 0) continue;
                result.links.push({{ text, href: a.href }});
                if (result.links.length >= {max_links}) break;
            }}

            // Get input fields
            const inputs = document.querySelectorAll('input[type="text"], input[type="search"], input:not([type])');
            for (const inp of inputs) {{
                const placeholder = inp.getAttribute('placeholder') || '';
                const name = inp.getAttribute('name') || inp.getAttribute('id') || '';
                result.inputs.push({{ placeholder, name, selector: inp.tagName + (inp.id ? '#' + inp.id : '') }});
                if (result.inputs.length >= 5) break;
            }}

            // Get buttons
            const buttons = document.querySelectorAll('button, [role="button"], input[type="submit"]');
            for (const btn of buttons) {{
                const text = btn.textContent.trim().replace(/\\s+/g, ' ').substring(0, 50);
                if (text && text.length > 1) {{
                    result.buttons.push({{ text }});
                    if (result.buttons.length >= 10) break;
                }}
            }}

            return result;
        }}""")
        return json.dumps(context, indent=2)
    except Exception:
        return json.dumps({"url": page.url, "title": "Error reading page", "links": [], "inputs": [], "buttons": []})


async def _ask_llm_for_action(page_context: str, task: str, provider: str, api_key: str) -> dict:
    """Ask the LLM what action to take on the current page."""
    from llm_engine import call_llm

    prompt = f"""You are a web navigation agent. Your task: {task}

Current page state:
{page_context}

Based on the page state, decide the SINGLE best next action. Return ONLY valid JSON:

Option A - Click a link to navigate:
{{"action": "click_link", "href": "https://...", "reason": "why"}}

Option B - Type in a search box:
{{"action": "search", "query": "search text", "reason": "why"}}

Option C - Extract jobs from current page (if you can see job listings):
{{"action": "extract_jobs", "reason": "I can see job listings on this page"}}

Option D - Page has no useful content:
{{"action": "done", "reason": "why"}}

RULES:
- If you see links like "Jobs", "Opportunities", "Open Positions", "Careers", "View All Jobs" → click them
- If you see a search box → search for the role
- If you see job titles with links → extract them
- Prefer links that lead to job listings over generic pages
- Return ONLY the JSON, nothing else
"""

    result = await call_llm(provider, api_key, prompt,
                            system="You are a web navigation agent. Return only valid JSON.",
                            temperature=0.1)
    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1] if "\n" in result else result[3:]
    if result.endswith("```"):
        result = result[:-3]
    try:
        return json.loads(result.strip())
    except:
        start = result.find("{")
        end = result.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(result[start:end])
            except:
                pass
        return {"action": "done", "reason": "Could not parse LLM response"}


async def _extract_jobs_with_llm(page_context: str, company_name: str, provider: str, api_key: str) -> list[dict]:
    """Ask the LLM to extract job listings from the current page."""
    from llm_engine import call_llm

    prompt = f"""Extract all job listings visible on this page for company "{company_name}".

Page state:
{page_context}

Return ONLY a JSON array of jobs. Each job should have:
- "title": job title
- "url": full URL to the job posting
- "location": job location if visible (or empty string)

Example: [{{"title": "Product Manager", "url": "https://...", "location": "Bangalore"}}]

RULES:
- Only include actual job postings, not navigation links
- Include the full URL (not relative paths)
- If no jobs are visible, return an empty array []
- Return ONLY the JSON array, nothing else
"""

    result = await call_llm(provider, api_key, prompt,
                            system="You are a data extraction agent. Return only valid JSON array.",
                            temperature=0.1)
    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1] if "\n" in result else result[3:]
    if result.endswith("```"):
        result = result[:-3]
    try:
        data = json.loads(result.strip())
        if isinstance(data, list):
            return [{"title": j.get("title", ""), "url": j.get("url", ""),
                     "location": j.get("location", ""), "company": company_name,
                     "description": "", "source": "ai_browser"}
                    for j in data if j.get("title") and j.get("url")]
        return []
    except:
        return []


async def ai_scan_company(browser, company: dict, target_roles: list[str],
                          provider: str = "deepseek", api_key: str = "") -> list[dict]:
    """Use AI agent to autonomously navigate a company's career page and find jobs.

    Flow:
    1. Open careers URL
    2. LLM decides: click "Jobs"/"Opportunities" link, or search
    3. Navigate to job listings
    4. Search for target roles
    5. Extract job titles + URLs
    6. For each job, fetch the description

    Max 5 LLM calls per company to control cost.
    """
    url = company["careers_url"]
    name = company["name"]
    role_query = target_roles[0] if target_roles else "Product Manager"

    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    page = await context.new_page()
    all_jobs = []

    try:
        # Step 1: Open the careers page
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        except Exception:
            await context.close()
            return []

        # Wait for page to render
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except:
            await asyncio.sleep(3)

        # Dismiss any popups/modals/cookie banners that block interaction
        try:
            await page.evaluate("""() => {
                // Close MUI dialogs
                const muiClose = document.querySelectorAll('.MuiDialog-root button, [class*="modal"] button[class*="close"], [class*="popup"] button[class*="close"], [aria-label="close"], [aria-label="Close"]');
                for (const btn of muiClose) {
                    const rect = btn.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) { btn.click(); break; }
                }
                // Click backdrop overlays
                const backdrop = document.querySelector('.MuiBackdrop-root, [class*="overlay"], [class*="backdrop"]');
                if (backdrop) backdrop.click();
                // Accept cookie banners
                const cookieBtn = document.querySelector('[class*="cookie"] button, [id*="cookie"] button, button[class*="accept"], button[class*="consent"]');
                if (cookieBtn) cookieBtn.click();
            }""")
            await asyncio.sleep(1)
        except:
            pass

        # Step 2-6: Navigate with LLM guidance (max 6 navigation steps)
        task = f'Find job listings for "{role_query}" at {name}. Navigate to the jobs/opportunities page and search for this role.'

        for step in range(6):
            page_ctx = await _get_page_context(page)
            action = await _ask_llm_for_action(page_ctx, task, provider, api_key)

            act = action.get("action", "done")
            print(f"    Step {step+1}: {act} — {action.get('reason','')[:80]}", flush=True)

            if act == "click_link":
                href = action.get("href", "")
                if href:
                    try:
                        # Try multiple strategies to click the link
                        clicked = False
                        # Strategy 1: exact href match
                        link = page.locator(f'a[href="{href}"]').first
                        if await link.count() > 0:
                            await link.click(timeout=5000)
                            clicked = True
                        if not clicked:
                            # Strategy 2: partial href match
                            href_part = href.split("/")[-1] if "/" in href else href
                            if href_part:
                                link2 = page.locator(f'a[href*="{href_part}"]').first
                                if await link2.count() > 0:
                                    await link2.click(timeout=5000)
                                    clicked = True
                        if not clicked:
                            # Strategy 3: direct navigation
                            if href.startswith("http"):
                                await page.goto(href, wait_until="domcontentloaded", timeout=15000)
                            elif href.startswith("#"):
                                # SPA hash navigation
                                base = page.url.split("#")[0]
                                await page.goto(base + href, wait_until="domcontentloaded", timeout=15000)
                            else:
                                await page.goto(href, wait_until="domcontentloaded", timeout=15000)
                        try:
                            await page.wait_for_load_state("networkidle", timeout=8000)
                        except:
                            await asyncio.sleep(3)
                    except Exception:
                        try:
                            if href.startswith("http"):
                                await page.goto(href, wait_until="domcontentloaded", timeout=15000)
                            await asyncio.sleep(5)
                        except:
                            pass
                    # Extra wait for SPA content to render
                    await asyncio.sleep(3)

            elif act == "search":
                query = action.get("query", role_query)
                try:
                    # Find and fill search input
                    search_input = page.locator('input[type="search"], input[type="text"], input[placeholder*="search" i], input[placeholder*="Search" i], input[name*="search" i], input[name*="query" i], input[name*="q"]').first
                    if await search_input.count() > 0:
                        await search_input.fill(query)
                        await search_input.press("Enter")
                        try:
                            await page.wait_for_load_state("networkidle", timeout=8000)
                        except:
                            await asyncio.sleep(3)
                except Exception:
                    pass

            elif act == "extract_jobs":
                # Extract jobs from current page
                page_ctx = await _get_page_context(page, max_links=100)
                jobs = await _extract_jobs_with_llm(page_ctx, name, provider, api_key)
                print(f"    Extracted: {len(jobs)} jobs", flush=True)
                if jobs:
                    all_jobs.extend(jobs)
                break

            elif act == "done":
                break

        # If no jobs extracted yet, try one final extraction
        if not all_jobs:
            print(f"    Final extraction attempt on {page.url[:60]}...", flush=True)
            page_ctx = await _get_page_context(page, max_links=100)
            jobs = await _extract_jobs_with_llm(page_ctx, name, provider, api_key)
            print(f"    Final extracted: {len(jobs)} jobs", flush=True)
            all_jobs.extend(jobs)

        # Deduplicate by URL
        seen = set()
        unique_jobs = []
        for j in all_jobs:
            if j["url"] not in seen:
                seen.add(j["url"])
                unique_jobs.append(j)

        if unique_jobs:
            print(f"  🤖 {name}: {len(unique_jobs)} jobs via AI browser agent", flush=True)

        return unique_jobs[:30]  # Cap at 30

    except asyncio.TimeoutError:
        print(f"  ⏰ {name}: AI browser timed out", flush=True)
        return []
    except Exception as e:
        print(f"  ❌ {name}: AI browser error: {str(e)[:100]}", flush=True)
        return []
    finally:
        await context.close()
