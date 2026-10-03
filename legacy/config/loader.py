"""Configuration loader for MonkeyKing."""
import os
import yaml
from pathlib import Path


def _load_env(env_path: str = None):
    """Load .env file into os.environ."""
    if env_path is None:
        env_path = str(Path(__file__).parent.parent / ".env")
    p = Path(env_path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())


class Config:
    """Loads and provides access to all MonkeyKing configuration."""

    def __init__(self, config_dir: str = None):
        if config_dir is None:
            # Auto-detect: config dir is always next to this file
            config_dir = str(Path(__file__).parent)
        self.config_dir = Path(config_dir)
        _load_env(str(Path(__file__).parent.parent / ".env"))
        self._settings = self._load_yaml("settings.yaml")
        self._cv_data = self._load_yaml("cv_data.yaml")
        self._inject_env_secrets()

    def _load_yaml(self, filename: str) -> dict:
        path = self.config_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path, "r") as f:
            return yaml.safe_load(f)

    def _inject_env_secrets(self):
        """Override config values with .env secrets (never hardcode creds)."""
        pw = os.environ.get("GMAIL_APP_PASSWORD", "")
        if pw:
            self._settings.setdefault("email", {})["app_password"] = pw
        ds_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if ds_key:
            self._settings.setdefault("llm", {}).setdefault("deepseek", {})["api_key"] = ds_key

    @property
    def user(self) -> dict:
        return self._settings.get("user", {})

    @property
    def job_preferences(self) -> dict:
        return self._settings.get("job_preferences", {})

    @property
    def target_companies(self) -> list:
        companies = []
        # Load from settings.yaml
        for category, items in self._settings.get("target_companies", {}).items():
            for item in items:
                item["category"] = category
                companies.append(item)
        # Also load from companies_india.yaml if it exists
        india_path = self.config_dir / "companies_india.yaml"
        if india_path.exists():
            with open(india_path, "r") as f:
                india_data = yaml.safe_load(f) or {}
            for category, items in india_data.items():
                if isinstance(items, list):
                    for item in items:
                        item["category"] = category
                        companies.append(item)
        return companies

    @property
    def llm_config(self) -> dict:
        return self._settings.get("llm", {})

    @property
    def email_config(self) -> dict:
        return self._settings.get("email", {})

    @property
    def cv_data(self) -> dict:
        return self._cv_data

    @property
    def dashboard_config(self) -> dict:
        return self._settings.get("dashboard", {})
