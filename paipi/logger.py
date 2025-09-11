# paipi/logger.py
"""
Dedicated logger for LLM communications.
"""

import logging
from pathlib import Path

# Create a 'logs' directory if it doesn't exist
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Create a logger
llm_logger = logging.getLogger("llm_comms")
llm_logger.setLevel(logging.DEBUG)

# Create a file handler which logs even debug messages
fh = logging.FileHandler(log_dir / "llm_communications.log", encoding="utf-8")
fh.setLevel(logging.DEBUG)

# Create formatter and add it to the handlers
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
fh.setFormatter(formatter)

# Add the handlers to the logger
if not llm_logger.handlers:
    llm_logger.addHandler(fh)
