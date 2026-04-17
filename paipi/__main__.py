"""Module entry point for `python -m paipi` and `python -m paipi start`."""

import os
import sys


def _entry() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "start":
        from paipi.onboarding import ensure_api_key

        api_key = ensure_api_key()
        if api_key:
            os.environ["OPENROUTER_API_KEY"] = api_key

        from paipi.main import start

        start()
    else:
        from paipi.main import main

        main()


if __name__ == "__main__":
    _entry()
