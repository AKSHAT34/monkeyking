"""Test vision-based AI browser agent with Google Gemini Flash."""
import asyncio
from playwright.async_api import async_playwright
from ai_browser_vision import vision_scan_company

GOOGLE_KEY = "${GOOGLE_AI_KEY}"

companies = [
    {"name": "Swiggy", "careers_url": "https://careers.swiggy.com/"},
    {"name": "Flipkart", "careers_url": "https://www.flipkartcareers.com/"},
    {"name": "CoinDCX", "careers_url": "https://careers.coindcx.com/"},
]
roles = ["Product Manager", "Account Manager"]

print("Vision LLM: Google Gemini 1.5 Flash (free)", flush=True)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for co in companies:
            name = co["name"]
            print(f"\n{'='*60}", flush=True)
            print(f"TESTING: {name}", flush=True)
            print(f"{'='*60}", flush=True)
            try:
                result = await asyncio.wait_for(
                    vision_scan_company(browser, co, roles,
                                       provider="google", api_key=GOOGLE_KEY),
                    timeout=300
                )
                print(f"\nRESULT: {name} -> {len(result)} jobs", flush=True)
                for j in result[:10]:
                    t = j.get("title", "")[:55]
                    loc = j.get("location", "")
                    print(f"  -> {t} | {loc}", flush=True)
            except asyncio.TimeoutError:
                print(f"\nRESULT: {name} -> TIMEOUT", flush=True)
            except Exception as e:
                print(f"\nRESULT: {name} -> ERROR: {e}", flush=True)
            # Small delay between companies
            await asyncio.sleep(5)
        await browser.close()
    print("\nDone.", flush=True)

asyncio.run(main())
