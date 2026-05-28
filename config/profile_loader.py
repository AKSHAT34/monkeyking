"""Multi-user profile loader for MonkeyKing."""
import os
import yaml
from pathlib import Path


class ProfileLoader:
    """Loads user profiles from config/profiles/ directory.
    
    Each user has their own YAML file with personal info, CV data,
    job preferences, compensation, and screening answers.
    Supports multiple users — the bot works dynamically for any profile.
    """

    PROFILES_DIR = Path(__file__).parent / "profiles"

    @classmethod
    def list_profiles(cls) -> list[str]:
        """List all available profile IDs."""
        profiles = []
        if cls.PROFILES_DIR.exists():
            for f in cls.PROFILES_DIR.glob("*.yaml"):
                profiles.append(f.stem)
        return sorted(profiles)

    @classmethod
    def load(cls, profile_id: str) -> dict:
        """Load a specific user profile by ID."""
        path = cls.PROFILES_DIR / f"{profile_id}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Profile not found: {path}")
        with open(path, "r") as f:
            return yaml.safe_load(f)

    @classmethod
    def get_active_profile(cls) -> dict:
        """Get the currently active profile."""
        for pid in cls.list_profiles():
            profile = cls.load(pid)
            if profile.get("profile", {}).get("active", False):
                return profile
        raise ValueError("No active profile found. Set active: true in a profile YAML.")

    @classmethod
    def get_user_data(cls, profile: dict) -> dict:
        """Extract user data in the format expected by agents."""
        return {
            "name": profile["personal"]["name"],
            "email": profile["personal"]["email"],
            "phone": profile["personal"]["phone"],
            "location": profile["personal"]["location"],
            "linkedin": profile["personal"].get("linkedin", ""),
        }

    @classmethod
    def get_screening_answers(cls, profile: dict) -> dict:
        """Get pre-configured screening answers."""
        return profile.get("screening_answers", {})

    @classmethod
    def get_compensation(cls, profile: dict) -> dict:
        """Get compensation expectations."""
        return profile.get("compensation", {})
