"""Account Creator Agent — Creates accounts on company job portals."""
from dataclasses import dataclass


@dataclass
class AccountCreationPlan:
    company: str
    portal_url: str
    signup_url: str
    email: str
    instructions: str


class AccountCreatorAgent:
    """
    Generates Browser MCP instructions for creating accounts on company portals.
    Works with the Kiro orchestrator to execute via browser automation.
    """

    def __init__(self, user_config: dict, email_agent=None):
        self.user = user_config
        self.email_agent = email_agent

    def plan_account_creation(self, company: str, portal_url: str) -> AccountCreationPlan:
        """Generate a plan for creating an account on a company portal."""
        email = self.user.get("email", "")
        name = self.user.get("name", "")
        phone = self.user.get("phone", "")

        instructions = f"""
ACCOUNT CREATION INSTRUCTIONS for {company}:

1. Navigate to: {portal_url}
2. Look for "Sign Up", "Create Account", "Register", or "Join" button/link
3. Click on the registration option
4. Fill in the registration form with:
   - Full Name: {name}
   - Email: {email}
   - Phone: {phone}
   - Create a secure password when prompted
5. Accept terms and conditions if present
6. Submit the registration form
7. If CAPTCHA appears, pause and wait for manual intervention
8. After submission, check for:
   - Immediate verification (account ready)
   - Email verification required (trigger email agent)
   - Phone verification required (pause for manual)
9. Report the result: success, needs_email_verify, needs_manual, or failed

IMPORTANT:
- If the portal uses SSO (Google/LinkedIn login), prefer Google sign-in with {email}
- If the portal asks for resume upload during registration, skip it (we'll upload tailored CV later)
- Screenshot each step for the dashboard log
"""
        return AccountCreationPlan(
            company=company,
            portal_url=portal_url,
            signup_url=portal_url,
            email=email,
            instructions=instructions,
        )

    def get_verification_instructions(self, company: str, portal_url: str) -> str:
        """Instructions for verifying an account via email."""
        domain = portal_url.split("//")[-1].split("/")[0].replace("www.", "")
        return f"""
EMAIL VERIFICATION for {company}:

1. The Email Agent will search for verification emails from *@{domain}
2. Once a verification link is found, navigate to that link using Browser MCP
3. Complete any additional verification steps on the page
4. Confirm the account is now active by navigating back to {portal_url}
5. Try logging in to verify access
6. Report: verified, failed, or needs_manual
"""

    def get_login_instructions(self, company: str, portal_url: str) -> str:
        """Instructions for logging into an existing account."""
        email = self.user.get("email", "")
        return f"""
LOGIN INSTRUCTIONS for {company}:

1. Navigate to: {portal_url}
2. Look for "Sign In", "Login", or "Log In" button
3. Enter email: {email}
4. Enter password (stored securely)
5. Handle any 2FA if needed (pause for manual)
6. Confirm successful login
7. Navigate to job application section
"""
