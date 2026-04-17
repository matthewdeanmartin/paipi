from pathlib import Path

import pytest

from paipi.config import Config, save_model_preferences


def test_config_uses_defaults_when_environment_is_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    for variable in (
        "OPENROUTER_API_KEY",
        "OPENROUTER_BASE_URL",
        "OPENROUTER_MODEL",
        "APP_TITLE",
        "APP_DESCRIPTION",
        "HOST",
        "PORT",
        "DEBUG",
    ):
        monkeypatch.delenv(variable, raising=False)

    from unittest.mock import patch

    with patch("paipi.config._load_api_key", return_value=None):
        config = Config()

    assert config.openrouter_api_key is None
    assert config.openrouter_base_url == "https://openrouter.ai/api/v1"
    assert config.default_model == "openrouter/free"
    assert config.app_title == "PAIPI - AI-Powered PyPI Search"
    assert (
        config.app_description
        == "PyPI search powered by AI's knowledge of Python packages"
    )
    assert config.host == "0.0.0.0"
    assert config.port == 8000
    assert config.debug is False


def test_config_reads_environment_overrides(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-key")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://example.invalid/api")
    monkeypatch.setenv("OPENROUTER_MODEL", "gpt-4.1")
    monkeypatch.setenv("APP_TITLE", "Custom title")
    monkeypatch.setenv("APP_DESCRIPTION", "Custom description")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "9001")
    monkeypatch.setenv("DEBUG", "TrUe")

    config = Config()

    assert config.openrouter_api_key == "secret-key"
    assert config.openrouter_base_url == "https://example.invalid/api"
    assert config.default_model == "gpt-4.1"
    assert config.app_title == "Custom title"
    assert config.app_description == "Custom description"
    assert config.host == "127.0.0.1"
    assert config.port == 9001
    assert config.debug is True


def test_config_parses_multiple_models(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-4.1-mini")
    monkeypatch.setenv(
        "OPENROUTER_MODELS",
        "google/gemma-4-31b-it:free, openai/gpt-4.1-mini\nanthropic/claude-3.5-sonnet",
    )
    monkeypatch.setenv("OPENROUTER_ROTATE_MODELS", "false")

    config = Config()

    assert config.default_model == "openai/gpt-4.1-mini"
    assert config.openrouter_models == [
        "openai/gpt-4.1-mini",
        "google/gemma-4-31b-it:free",
        "anthropic/claude-3.5-sonnet",
    ]
    assert config.rotate_models is False


def test_config_validate_requires_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    from unittest.mock import patch

    with patch("paipi.config._load_api_key", return_value=None):
        config = Config()

        with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
            config.validate()


def test_save_model_preferences_updates_env_file(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text("OPENROUTER_API_KEY=test-key\n", encoding="utf-8")

    saved = save_model_preferences(
        ["google/gemma-4-31b-it:free", "openrouter/free"], env_path=env_path
    )

    assert saved == ["google/gemma-4-31b-it:free", "openrouter/free"]
    content = env_path.read_text(encoding="utf-8")
    assert "OPENROUTER_MODEL=google/gemma-4-31b-it:free" in content
    assert (
        "OPENROUTER_MODELS=google/gemma-4-31b-it:free,openrouter/free" in content
    )
