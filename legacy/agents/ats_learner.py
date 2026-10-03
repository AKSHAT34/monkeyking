"""
ATS Learner — Learns and stores how each company's application process works.

Saves the DOM structure, form fields, selectors, and flow for each ATS/company
so MonkeyKing can reuse this knowledge for future applications.
"""
import base64
import json
import os
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet


def _get_or_create_key() -> bytes:
    """Get or create an encryption key for credential storage."""
    key_path = Path(__file__).parent.parent / "data" / "credentials" / ".key"
    key_path.parent.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        return key_path.read_bytes()
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    # Restrict permissions (owner-only)
    os.chmod(key_path, 0o600)
    return key


class ATSLearner:
    """Learns and caches ATS form structures per company."""

    DATA_DIR = Path(__file__).parent.parent / "data" / "ats_patterns"

    def __init__(self):
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._cache = {}
        self._load_all()

    def _load_all(self):
        """Load all saved ATS patterns into memory."""
        for f in self.DATA_DIR.glob("*.json"):
            try:
                with open(f) as fh:
                    data = json.load(fh)
                    key = data.get("company", f.stem)
                    self._cache[key.lower()] = data
            except Exception:
                pass

    def get_pattern(self, company: str) -> dict:
        """Get saved ATS pattern for a company. Returns {} if unknown."""
        return self._cache.get(company.lower(), {})

    def has_pattern(self, company: str) -> bool:
        """Check if we have a saved pattern for this company."""
        return company.lower() in self._cache

    async def learn_from_page(self, page, company: str, url: str) -> dict:
        """Analyze a job application page and learn its structure."""
        pattern = {
            "company": company,
            "url": url,
            "ats_type": "unknown",
            "learned_at": datetime.utcnow().isoformat(),
            "apply_url_pattern": "",
            "form_fields": [],
            "file_inputs": [],
            "yes_no_questions": [],
            "submit_selector": "",
            "notes": "",
        }

        try:
            # Detect ATS type from URL
            current_url = page.url.lower()
            if "ashbyhq.com" in current_url:
                pattern["ats_type"] = "ashby"
            elif "greenhouse.io" in current_url or "boards.greenhouse" in current_url:
                pattern["ats_type"] = "greenhouse"
            elif "lever.co" in current_url:
                pattern["ats_type"] = "lever"
            elif "workday" in current_url or "myworkdayjobs" in current_url:
                pattern["ats_type"] = "workday"
            elif "taleo" in current_url:
                pattern["ats_type"] = "taleo"
            elif "smartrecruiters" in current_url:
                pattern["ats_type"] = "smartrecruiters"
            elif "icims" in current_url:
                pattern["ats_type"] = "icims"

            pattern["apply_url_pattern"] = current_url

            # Extract all form fields
            fields = await page.evaluate("""() => {
                const fields = [];
                const inputs = document.querySelectorAll('input, textarea, select');
                for (const inp of inputs) {
                    fields.push({
                        tag: inp.tagName.toLowerCase(),
                        type: inp.type || '',
                        name: inp.name || '',
                        id: inp.id || '',
                        placeholder: inp.placeholder || '',
                        required: inp.required || false,
                        ariaLabel: inp.getAttribute('aria-label') || '',
                    });
                }
                return fields;
            }""")
            pattern["form_fields"] = fields

            # Extract file upload inputs
            file_inputs = await page.evaluate("""() => {
                const files = [];
                const inputs = document.querySelectorAll('input[type="file"]');
                for (const inp of inputs) {
                    files.push({
                        id: inp.id || '',
                        name: inp.name || '',
                        accept: inp.accept || '',
                        parentText: inp.parentElement?.textContent?.trim()?.substring(0, 100) || '',
                    });
                }
                return files;
            }""")
            pattern["file_inputs"] = file_inputs

            # Find submit button
            submit = await page.evaluate("""() => {
                const btns = document.querySelectorAll('button[type="submit"], input[type="submit"], button:has-text("Submit"), button:has-text("Apply")');
                for (const btn of btns) {
                    return {
                        tag: btn.tagName.toLowerCase(),
                        text: btn.textContent?.trim() || '',
                        type: btn.type || '',
                        id: btn.id || '',
                    };
                }
                return null;
            }""")
            if submit:
                pattern["submit_selector"] = f"#{submit['id']}" if submit.get('id') else f"button:has-text(\"{submit['text']}\")"

        except Exception as e:
            pattern["notes"] = f"Learning error: {str(e)[:200]}"

        # Save pattern
        self._save_pattern(company, pattern)
        self._cache[company.lower()] = pattern
        return pattern

    def _save_pattern(self, company: str, pattern: dict):
        """Save ATS pattern to disk."""
        safe_name = "".join(c if c.isalnum() else "_" for c in company.lower())
        filepath = self.DATA_DIR / f"{safe_name}.json"
        with open(filepath, "w") as f:
            json.dump(pattern, f, indent=2)

    def save_account_credentials(self, company: str, profile_id: str,
                                  portal_url: str, email: str, password: str):
        """Save account credentials for a company portal (encrypted)."""
        creds_dir = Path(__file__).parent.parent / "data" / "credentials"
        creds_dir.mkdir(parents=True, exist_ok=True)

        creds_file = creds_dir / f"{profile_id}_accounts.json"
        accounts = {}
        if creds_file.exists():
            accounts = self._load_encrypted_creds(creds_file)

        accounts[company.lower()] = {
            "company": company,
            "portal_url": portal_url,
            "email": email,
            "password": password,
            "created_at": datetime.utcnow().isoformat(),
        }

        self._save_encrypted_creds(creds_file, accounts)

    def get_account_credentials(self, company: str, profile_id: str) -> dict:
        """Get saved credentials for a company portal (decrypted)."""
        creds_file = Path(__file__).parent.parent / "data" / "credentials" / f"{profile_id}_accounts.json"
        if not creds_file.exists():
            return {}
        accounts = self._load_encrypted_creds(creds_file)
        return accounts.get(company.lower(), {})

    def list_accounts(self, profile_id: str) -> dict:
        """List all saved accounts for a profile (decrypted)."""
        creds_file = Path(__file__).parent.parent / "data" / "credentials" / f"{profile_id}_accounts.json"
        if not creds_file.exists():
            return {}
        return self._load_encrypted_creds(creds_file)

    def _save_encrypted_creds(self, filepath: Path, data: dict):
        """Encrypt and save credentials to disk."""
        key = _get_or_create_key()
        f = Fernet(key)
        plaintext = json.dumps(data).encode()
        encrypted = f.encrypt(plaintext)
        filepath.write_bytes(encrypted)
        os.chmod(filepath, 0o600)

    def _load_encrypted_creds(self, filepath: Path) -> dict:
        """Load and decrypt credentials from disk."""
        key = _get_or_create_key()
        f = Fernet(key)
        try:
            encrypted = filepath.read_bytes()
            decrypted = f.decrypt(encrypted)
            return json.loads(decrypted)
        except Exception:
            # Fallback: try reading as plain JSON (migration from old format)
            try:
                with open(filepath) as fh:
                    data = json.load(fh)
                # Re-save encrypted
                self._save_encrypted_creds(filepath, data)
                return data
            except Exception:
                return {}
