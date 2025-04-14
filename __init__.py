"""
Fix Archive Tool: Parses Nuke scripts, collects dependencies, and archives
them according to specified standards (e.g., SPT), prioritizing pruned scripts.
"""

# Define a basic fallback logger function first
import logging
import sys
def _basic_get_logger(name):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    return logger

# Attempt to import the potentially more advanced logger from fixfx
try:
    from fixfx.core.logger import get_logger as fixfx_get_logger
    log = fixfx_get_logger(__name__) # Initialize package root logger with name
    get_logger = fixfx_get_logger # Assign fixfx version to be exported
    log.debug("Using fixfx.core.logger")
except ImportError:
    # fixfx not available, assign the basic fallback
    get_logger = _basic_get_logger
    log = get_logger(__name__) # Initialize package root logger using fallback
    log.warning("fixfx.core.logger not found. Using basic fallback logger.")

# Expose the root logger AND the get_logger function for submodules
__all__ = [
    "log",
    "get_logger",
]

log.info("Fix Archive package initialized")