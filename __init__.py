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

__version__ = "0.2.0"

# --- Exports ---
# Expose the root logger AND the get_logger function for submodules to use
__all__ = [
    "log",
    "get_logger",
    "__version__",
]

# log.info(f"Fix Archive (fixarc) package initialized (version {__version__})")