"""
Configuration management for PAIPI.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from .openrouter_models import FALLBACK_ROUTER_MODEL

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


def _parse_models(value: Optional[str]) -> list[str]:
    """Parse a comma/newline separated model list."""
    if not value:
        return []

    models: list[str] = []
    for item in value.replace("\r", "\n").replace(",", "\n").split("\n"):
        model = item.strip()
        if model and model not in models:
            models.append(model)
    return models


def save_model_preferences(
    models: list[str], env_path: str | Path = ".env"
) -> list[str]:
    """Persist preferred models into the local .env file."""
    deduped = _parse_models("\n".join(models))
    if not deduped:
        deduped = [FALLBACK_ROUTER_MODEL]

    path = Path(env_path)
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    def upsert(lines: list[str], key: str, value: str) -> list[str]:
        new_line = f"{key}={value}"
        replaced = False
        updated: list[str] = []
        for line in lines:
            if line.startswith(f"{key}="):
                updated.append(new_line)
                replaced = True
            else:
                updated.append(line)
        if not replaced:
            if updated and updated[-1].strip():
                updated.append("")
            updated.append(new_line)
        return updated

    lines = existing_lines
    lines = upsert(lines, "OPENROUTER_MODEL", deduped[0])
    lines = upsert(lines, "OPENROUTER_MODELS", ",".join(deduped))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return deduped


class Config:
    """Application configuration."""

    def __init__(self) -> None:
        """Initialize configuration from environment variables."""
        self.openrouter_api_key: Optional[str] = _load_api_key()
        self.openrouter_base_url: str = os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        )
        primary_model = os.getenv("OPENROUTER_MODEL")
        configured_models = _parse_models(os.getenv("OPENROUTER_MODELS"))

        combined_models = _parse_models(primary_model) + configured_models
        deduped_models: list[str] = []
        for model in combined_models:
            if model not in deduped_models:
                deduped_models.append(model)

        self.configured_openrouter_models: list[str] = list(deduped_models)
        self.openrouter_models: list[str] = deduped_models or [FALLBACK_ROUTER_MODEL]
        self.default_model: str = self.openrouter_models[0]
        self.rotate_models: bool = (
            os.getenv("OPENROUTER_ROTATE_MODELS", "true").lower() != "false"
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

    def set_openrouter_models(self, models: list[str]) -> None:
        """Update the runtime model pool."""
        resolved = _parse_models("\n".join(models))
        self.openrouter_models = resolved or [FALLBACK_ROUTER_MODEL]
        self.default_model = self.openrouter_models[0]


# Global configuration instance
config = Config()
