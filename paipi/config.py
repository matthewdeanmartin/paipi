"""
Configuration management for PAIPI.
"""

from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

KEYRING_SERVICE = "paipi"
KEYRING_USERNAME = "openrouter_api_key"


def _load_api_key() -> Optional[str]:
    """Load the OpenRouter API key from env var or keyring (env takes priority)."""
    env_key = os.getenv("OPENROUTER_API_KEY")
    if env_key:
        return env_key
    try:
        import keyring

        return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except Exception:
        return None


def save_api_key(key: str) -> None:
    """Persist the OpenRouter API key to the system keyring."""
    import keyring

    keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, key)


class Config:
    """Application configuration."""

    def __init__(self) -> None:
        """Initialize configuration from environment variables."""
        self.openrouter_api_key: Optional[str] = _load_api_key()
        self.openrouter_base_url: str = os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        )
        self.default_model: str = os.getenv(
            "OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"
        )
        self.app_title: str = os.getenv("APP_TITLE", "PAIPI - AI-Powered PyPI Search")
        self.app_description: str = os.getenv(
            "APP_DESCRIPTION",
            "PyPI search powered by AI's knowledge of Python packages",
        )
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))
        self.debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    def validate(self) -> None:
        """Validate required configuration."""
        if not self.openrouter_api_key:
            raise ValueError(
                "OPENROUTER_API_KEY environment variable is required. "
                "Please set it to your OpenRouter API key."
            )


# Global configuration instance
config = Config()
