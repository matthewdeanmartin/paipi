from unittest.mock import patch

import pytest

from paipi.onboarding import ensure_api_key, prompt_for_models, run_onboarding


def test_run_onboarding_success():
    with patch("builtins.input", return_value="sk-or-fake-key"), patch(
        "paipi.config.save_api_key"
    ) as mock_save, patch(
        "paipi.onboarding.prompt_for_models", return_value=["openrouter/free"]
    ), patch(
        "paipi.onboarding.save_model_preferences", return_value=["openrouter/free"]
    ):
        key = run_onboarding()
        assert key == "sk-or-fake-key"
        mock_save.assert_called_once_with("sk-or-fake-key")


def test_run_onboarding_retry_then_success():
    # First input is empty, second is invalid, third is valid
    with patch(
        "builtins.input", side_effect=["", "invalid-key", "sk-or-valid-key"]
    ), patch("paipi.config.save_api_key") as mock_save, patch(
        "paipi.onboarding.prompt_for_models", return_value=["openrouter/free"]
    ), patch(
        "paipi.onboarding.save_model_preferences", return_value=["openrouter/free"]
    ):
        key = run_onboarding()
        assert key == "sk-or-valid-key"
        mock_save.assert_called_once_with("sk-or-valid-key")


def test_run_onboarding_cancel():
    with patch("builtins.input", side_effect=KeyboardInterrupt), patch(
        "sys.exit", side_effect=SystemExit
    ) as mock_exit:
        with pytest.raises(SystemExit):
            run_onboarding()
        mock_exit.assert_called_once_with(0)


def test_ensure_api_key_existing():
    with patch("paipi.config._load_api_key", return_value="existing-key"):
        key = ensure_api_key()
        assert key == "existing-key"


def test_ensure_api_key_runs_onboarding():
    with patch("paipi.config._load_api_key", return_value=None), patch(
        "paipi.onboarding.run_onboarding", return_value="new-key"
    ) as mock_onboarding:
        key = ensure_api_key()
        assert key == "new-key"
        mock_onboarding.assert_called_once()


def test_prompt_for_models_uses_fallback_when_fetch_fails():
    with patch(
        "paipi.onboarding.fetch_models", side_effect=RuntimeError("nope")
    ), patch("builtins.input", return_value=""):
        models = prompt_for_models("sk-or-fake-key")

    assert models == ["openrouter/free"]
