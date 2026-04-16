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
         patch("paipi.main.start") as mock_mock_start:
        _entry()
        mock_mock_start.assert_called_once()

def test_entry_other_args():
    with patch("sys.argv", ["paipi", "help"]), \
         patch("paipi.main.main") as mock_main:
        _entry()
        mock_main.assert_called_once()
