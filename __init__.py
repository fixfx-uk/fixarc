# fixarc/__init__.py
"""
Fix Archive Tool (fixarc): Prunes, collects, and archives Nuke scripts and
dependencies according to specified standards (e.g., SPT).
"""
import logging
import sys
import os

# --- Centralized Logging Setup ---
# Use the fixfx logger as a required dependency
from fixfx.core.logger import get_logger

# Initialize the package root logger
log = get_logger(__name__)  # Logger named 'fixarc'

# Ensure we have a console handler
if not any(isinstance(h, logging.StreamHandler) for h in log.handlers):
    console_handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter('%(asctime)s [%(levelname)-7s] [%(name)s]: %(message)s')
    console_handler.setFormatter(formatter)
    log.addHandler(console_handler)
    log.debug("Added console handler to fixarc logger during initialization")

__version__ = "1.2.0"

# --- Exports ---
# Expose the root logger AND the get_logger function for submodules to use
__all__ = [
    "log",
    "get_logger",
    "__version__",
]

# log.info(f"Fix Archive (fixarc) package initialized (version {__version__})")