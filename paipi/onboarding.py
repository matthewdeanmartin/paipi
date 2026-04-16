"""
First-run onboarding for PAIPI.

Guides the user through entering their OpenRouter API key and persists it
to the system keyring so they never have to enter it again.
"""

from __future__ import annotations

import sys

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
