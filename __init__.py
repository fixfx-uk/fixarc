# fixarc/__init__.py
"""
Fix Archive Tool (fixarc): Prunes, collects, and archives Nuke scripts and
dependencies according to specified standards (e.g., SPT).
"""
import logging
import sys
import os

# --- Centralized Logging Setup ---
# Attempt to import the potentially more advanced logger from fixfx first
# If fixfx isn't available, set up a basic stream handler.
try:
    from fixfx.core.logger import get_logger as _fixfx_get_logger
    _logger_configured = True
    # Define get_logger to return the fixfx version
    def get_logger(name: str) -> logging.Logger:
        return _fixfx_get_logger(name)

except ImportError:
    _logger_configured = False
    # Define a basic fallback get_logger function
    def get_logger(name: str) -> logging.Logger:
        """Basic fallback logger configuration."""
        logger = logging.getLogger(name)
        if not logger.hasHandlers(): # Configure only if not already done
            handler = logging.StreamHandler(sys.stdout)
            # Use a consistent format
            log_format = os.getenv('FIXARC_LOG_FORMAT', '[%(asctime)s] [%(levelname)-7s] [%(name)s] %(message)s')
            date_format = os.getenv('FIXARC_DATE_FORMAT', '%Y-%m-%d %H:%M:%S')
            formatter = logging.Formatter(log_format, date_format)
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            # Set default level (can be overridden later in cli.py)
            default_level_str = os.getenv('FIXARC_LOG_LEVEL', 'INFO')
            logger.setLevel(getattr(logging, default_level_str.upper(), logging.INFO))
            # Prevent propagation to avoid duplicate messages if root logger also has handler
            logger.propagate = False
        return logger

# Initialize the *package* root logger using the selected get_logger function
log = get_logger(__name__) # Logger named 'fixarc'

# Log which logger implementation is being used
if not _logger_configured:
    log.warning("fixfx.core.logger not found. Using basic fallback logger.")
else:
    log.debug("Using fixfx.core.logger.")


# --- Version Information ---
# Attempt to get version from standard location if using setuptools_scm or similar
try:
    from ._version import version as __version__
except ImportError:
    # Fallback version if _version.py doesn't exist (e.g., not installed)
    try:
        # Try reading from a VERSION file perhaps?
        with open(os.path.join(os.path.dirname(__file__), 'VERSION'), 'r') as vf:
             __version__ = vf.read().strip()
    except OSError:
         __version__ = "0.2.0" # Hardcoded fallback

# --- Exports ---
# Expose the root logger AND the get_logger function for submodules to use
__all__ = [
    "log",
    "get_logger",
    "__version__",
]

log.info(f"Fix Archive (fixarc) package initialized (version {__version__})")