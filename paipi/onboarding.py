"""
First-run onboarding for PAIPI.

Guides the user through entering their OpenRouter API key and persists it
to the system keyring so they never have to enter it again.
"""

from __future__ import annotations

import os
import sys

from .config import _parse_models, save_model_preferences
from .openrouter_models import (
    FALLBACK_ROUTER_MODEL,
    fetch_models,
    format_shortlist,
    shortlist_models,
    shortlisted_model_ids,
)

_OPENROUTER_URL = "https://openrouter.ai/keys"

_BANNER = """
╔══════════════════════════════════════════════════════════════╗
║          Welcome to PAIPI - AI-Powered PyPI Search           ║
╚══════════════════════════════════════════════════════════════╝

PAIPI uses OpenRouter to access large language models that power
the AI package search. You'll need a free OpenRouter API key.

  Get one at: {url}

Your key will be stored securely in your system keyring (not in
any file) and will be used automatically on future runs.
""".format(
    url=_OPENROUTER_URL
)

_SEPARATOR = "─" * 64


def prompt_for_models(api_key: str) -> list[str]:
    """Prompt for preferred models, with live OpenRouter suggestions when possible."""
    suggested_models = [FALLBACK_ROUTER_MODEL]
    try:
        models = fetch_models(api_key)
        shortlist = shortlist_models(models)
        if shortlist["free"]:
            print(format_shortlist("free", shortlist["free"]))
        if shortlist["cheap"]:
            print(format_shortlist("cheap", shortlist["cheap"]))
        suggested_models = shortlisted_model_ids(shortlist)
    except Exception as exc:
        print(f"\n  Could not fetch OpenRouter's current model list ({exc}).")
        print(f"  Falling back to {FALLBACK_ROUTER_MODEL} unless you enter models manually.")

    default_display = ", ".join(suggested_models)
    while True:
        try:
            raw = input(
                f"\n  Preferred model IDs (comma separated, blank for {default_display}): "
            ).strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nUsing the suggested model list.")
            return suggested_models

        chosen_models = _parse_models(raw) if raw else list(suggested_models)
        if chosen_models:
            return chosen_models

        print("  Please enter at least one model ID, or press Enter to accept the suggestion.\n")


def run_onboarding() -> str:
    """
    Interactively prompt the user for their OpenRouter API key.

    Saves the key to the system keyring and returns it.
    Exits with a helpful message if the user cancels.
    """
    print(_BANNER)
    print(_SEPARATOR)

    while True:
        key = ""
        try:
            key = input(
                "  Paste your OpenRouter API key (starts with sk-or-): "
            ).strip()
        except (KeyboardInterrupt, EOFError):
            print(
                "\n\nSetup cancelled. Run `paipi start` again when you have your key."
            )
            sys.exit(0)

        if not key:
            print("  No key entered — try again, or press Ctrl+C to cancel.\n")
            continue

        if not key.startswith("sk-or-"):
            print(
                "  That doesn't look like an OpenRouter key (should start with sk-or-).\n"
                "  Double-check and try again, or press Ctrl+C to cancel.\n"
            )
            continue

        # Save to keyring
        try:
            from paipi.config import save_api_key

            save_api_key(key)
            print("\n  API key saved to system keyring.")
        except Exception as exc:
            print(f"\n  Warning: could not save to keyring ({exc}).")
            print("  You can set OPENROUTER_API_KEY in your environment instead.")

        chosen_models = prompt_for_models(key)
        try:
            saved_models = save_model_preferences(chosen_models)
            os.environ["OPENROUTER_MODEL"] = saved_models[0]
            os.environ["OPENROUTER_MODELS"] = ",".join(saved_models)
            print(f"\n  Saved preferred model pool: {', '.join(saved_models)}")
        except Exception as exc:
            print(f"\n  Warning: could not save model preferences to .env ({exc}).")
            print("  You can set OPENROUTER_MODEL / OPENROUTER_MODELS manually instead.")

        print(_SEPARATOR)
        return key


def ensure_api_key() -> str:
    """
    Return the OpenRouter API key, running onboarding if it isn't set yet.

    This is called by `paipi start` before the server boots.
    """
    from paipi.config import _load_api_key

    key = _load_api_key()
    if key:
        return key

    # No key found anywhere — run the interactive wizard
    return run_onboarding()
