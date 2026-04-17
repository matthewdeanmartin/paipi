import sys
import pytest
from unittest.mock import patch
from paipi.__main__ import _entry

def test_entry_default():
    with patch("sys.argv", ["paipi"]), \
         patch("paipi.main.main") as mock_main:
        _entry()
        mock_main.assert_called_once()

def test_entry_start():
    with patch("sys.argv", ["paipi", "start"]), \
         patch("paipi.onboarding.ensure_api_key", return_value="sk-or-test"), \
         patch("paipi.main.start") as mock_mock_start:
        _entry()
        mock_mock_start.assert_called_once()


def test_entry_start_runs_onboarding_first():
    with patch("sys.argv", ["paipi", "start"]), \
         patch("paipi.onboarding.ensure_api_key", return_value="sk-or-test") as mock_ensure, \
         patch("paipi.main.start") as mock_start:
        _entry()

    mock_ensure.assert_called_once()
    mock_start.assert_called_once()

def test_entry_other_args():
    with patch("sys.argv", ["paipi", "help"]), \
         patch("paipi.main.main") as mock_main:
        _entry()
        mock_main.assert_called_once()
