"""
CAPTCHA Solver — Integrates multiple CAPTCHA bypass strategies.

Strategies (in order of preference):
1. PyPasser — Free, uses speech-to-text for reCAPTCHA v2 (github.com/xHossein/PyPasser)
2. 2Captcha API — Paid service, handles all CAPTCHA types ($2.99/1000 solves)
3. Manual fallback — Pauses and waits for human intervention

Install: pip install PyPasser 2captcha-python
"""
import asyncio
from typing import Optional


class CaptchaSolver:
    """Multi-strategy CAPTCHA solver for job application automation."""

    def __init__(self, two_captcha_api_key: str = "", manual_wait: int = 15):
        self.two_captcha_key = two_captcha_api_key
        self.manual_wait = manual_wait  # seconds to wait for manual solve before skipping

    async def detect_captcha(self, page) -> Optional[str]:
        """Detect if a CAPTCHA is present on the page. Returns type or None."""
        try:
            # Check for reCAPTCHA
            recaptcha = await page.query_selector(
                'iframe[src*="recaptcha"], div.g-recaptcha, [data-sitekey]'
            )
            if recaptcha:
                return "recaptcha"

            # Check for hCaptcha
            hcaptcha = await page.query_selector(
                'iframe[src*="hcaptcha"], div.h-captcha'
            )
            if hcaptcha:
                return "hcaptcha"

            # Check for Cloudflare Turnstile
            turnstile = await page.query_selector(
                'iframe[src*="turnstile"], div.cf-turnstile'
            )
            if turnstile:
                return "turnstile"

            return None
        except Exception:
            return None

    async def solve(self, page, captcha_type: str) -> bool:
        """Attempt to solve a detected CAPTCHA."""
        print(f"    🔐 CAPTCHA detected: {captcha_type}")

        # Strategy 1: Try PyPasser for reCAPTCHA v2
        if captcha_type == "recaptcha":
            solved = await self._try_pypasser(page)
            if solved:
                return True

        # Strategy 2: Try 2Captcha API (paid, works for all types)
        if self.two_captcha_key:
            solved = await self._try_2captcha(page, captcha_type)
            if solved:
                return True

        # Strategy 3: Short wait then skip (don't block the pipeline)
        print(f"    ⏸ CAPTCHA unsolved — waiting {self.manual_wait}s then skipping")
        await page.wait_for_timeout(self.manual_wait * 1000)
        # Check if CAPTCHA is still present (user may have solved it manually)
        still_present = await self.detect_captcha(page)
        if still_present:
            print(f"    ⚠ CAPTCHA still present — marking job for manual review")
            return False
        print(f"    ✅ CAPTCHA resolved during wait")
        return True

    async def _try_pypasser(self, page) -> bool:
        """Try to solve reCAPTCHA v2 using PyPasser (free, speech-to-text)."""
        try:
            from pypasser import reCaptchaV2
            # Get the sitekey from the page
            sitekey = await page.evaluate("""() => {
                const el = document.querySelector('[data-sitekey]');
                return el ? el.getAttribute('data-sitekey') : null;
            }""")
            if not sitekey:
                return False

            # Solve using audio challenge
            token = reCaptchaV2(sitekey)
            if token:
                # Inject the token
                await page.evaluate(f"""(token) => {{
                    document.getElementById('g-recaptcha-response').value = token;
                }}""", token)
                print(f"    ✅ reCAPTCHA solved via PyPasser")
                return True
        except ImportError:
            print(f"    ⚠ PyPasser not installed. Run: pip install PyPasser")
        except Exception as e:
            print(f"    ⚠ PyPasser failed: {e}")
        return False

    async def _try_2captcha(self, page, captcha_type: str) -> bool:
        """Try to solve CAPTCHA using 2Captcha API (paid service)."""
        try:
            from twocaptcha import TwoCaptcha
            solver = TwoCaptcha(self.two_captcha_key)

            sitekey = await page.evaluate("""() => {
                const el = document.querySelector('[data-sitekey]');
                return el ? el.getAttribute('data-sitekey') : null;
            }""")
            if not sitekey:
                return False

            url = page.url

            if captcha_type == "recaptcha":
                result = solver.recaptcha(sitekey=sitekey, url=url)
            elif captcha_type == "hcaptcha":
                result = solver.hcaptcha(sitekey=sitekey, url=url)
            elif captcha_type == "turnstile":
                result = solver.turnstile(sitekey=sitekey, url=url)
            else:
                return False

            if result and result.get("code"):
                await page.evaluate(f"""(token) => {{
                    const textarea = document.querySelector('[name="g-recaptcha-response"], [name="h-captcha-response"]');
                    if (textarea) textarea.value = token;
                }}""", result["code"])
                print(f"    ✅ CAPTCHA solved via 2Captcha")
                return True
        except ImportError:
            print(f"    ⚠ 2captcha-python not installed. Run: pip install 2captcha-python")
        except Exception as e:
            print(f"    ⚠ 2Captcha failed: {e}")
        return False
