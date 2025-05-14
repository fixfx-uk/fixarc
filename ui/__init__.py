# fixarc/ui/__init__.py
"""
PyQt5 User Interface for the Fix Archive Handler tool.
"""

# Initialize logger if main fixarc logger is available
log = None
try:
    from fixarc import log as root_log
    log = root_log.getChild("ui") # Get a child logger named 'fixarc.ui'
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)-7s] [%(name)s]: %(message)s')
    log = logging.getLogger("fixarc.ui")
    log.warning("Could not get logger from root 'fixarc' package. Using basic logging.")

# Try importing the main window class
try:
    from .main_window import FixarcHandlerWindow
    __all__ = ["FixarcHandlerWindow", "log"]
except ImportError as e:
    log.error(f"Failed to import UI components: {e}. UI might not be available.")
    __all__ = ["log"]

log.debug("fixarc.ui package initialized.")