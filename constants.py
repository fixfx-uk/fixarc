# fixarc/constants.py
"""Constants used by the Fix Archive (fixarc) tool."""
import os

# --- Nuke Executable Paths ---
# Attempt to get from fixenv, provide basic defaults otherwise
try:
    from fixenv import (
        NUKE_EXEC_PATH_WIN as DEFAULT_NUKE_EXECUTABLE_WIN,
        NUKE_EXEC_PATH_LIN as DEFAULT_NUKE_EXECUTABLE_LIN,
        NUKE_EXEC_PATH_MAC as DEFAULT_NUKE_EXECUTABLE_MAC,
        constants as fixenv_constants
    )
    # Use studio short name from fixenv if available, otherwise use fallback
    DEFAULT_VENDOR_NAME = getattr(fixenv_constants, 'STUDIO_SHORT_NAME', 'FixFX')
    _fixenv_available = True
except ImportError:
    DEFAULT_NUKE_EXECUTABLE_WIN = "C:/Program Files/Nuke15.1v1/Nuke15.1.exe" # Example
    DEFAULT_NUKE_EXECUTABLE_LIN = "/usr/local/Nuke15.1v1/Nuke15.1" # Example
    DEFAULT_NUKE_EXECUTABLE_MAC = "/Applications/Nuke15.1v1/Nuke15.1.app/Contents/MacOS/Nuke15.1" # Example
    DEFAULT_VENDOR_NAME = "FixFX" # Fallback vendor name
    _fixenv_available = False


# --- SPT v3.2.0 Folder Names (Placeholders for format()) ---
# These should match the spec exactly. Use braces {} for placeholders.
VENDOR_DIR = "{vendor}"
SHOW_DIR = "{show}"
EPISODE_DIR = "{episode}"
SHOT_DIR = "{shot}"

# --- Relative Archive Paths within SHOT_DIR ---
# Use os.path.join for platform-agnostic joining, then force forward slashes for consistency.
def _rel_path(*args) -> str:
    """Helper to join path components and ensure forward slashes."""
    return os.path.join(*args).replace("\\", "/")

PROJECT_FILES_REL = _rel_path("project", "nuke")
ELEMENTS_REL = "elements" # Root elements folder
PRERENDERS_REL = "prerenders"
ROTO_REL = "roto"
TRACKS_REL = "tracks"
CLEANPLATES_REL = _rel_path(ELEMENTS_REL, "cleanplates") # Subfolder under elements
MATTES_REL = _rel_path(ELEMENTS_REL, "mattes") # Subfolder under elements
REFERENCE_REL = "reference"
LUT_REL = _rel_path(REFERENCE_REL, "lut")
GEO_CACHE_REL = _rel_path(ELEMENTS_REL, "geo_cache") # Example for geo/alembic
CAMERA_REL = _rel_path(TRACKS_REL, "camera")      # Example for cameras

# --- Nuke Node Classes ---
# Classes typically containing file paths for *reading* dependencies
READ_NODE_CLASSES = frozenset([ # Use frozenset for minor perf gain and immutability
    "Read",
    "ReadGeo", "ReadGeo2",
    "DeepRead",
    "Camera", "Camera2", "Camera3",
    "Axis", "Axis2", "Axis3",
    "OCIOFileTransform",
    "Vectorfield",
    "GenerateLUT",
    "BlinkScript", # Check file knobs specifically
    "ParticleCache",
    "PointCloudGenerator",
    "STMap",
    # Add more as needed
])

# Classes considered as final output nodes for pruning trace
WRITE_NODE_CLASSES = frozenset([
    "Write",
    "WriteGeo",
    "DeepWrite",
    # WriteFix handled specially
])

# --- LTFS / Path Safety ---
# Characters generally considered unsafe for LTFS or simple cross-platform paths.
INVALID_FILENAME_CHARS = r'[<>:"/\\|?*\s]' # Raw string

# --- Internal Script Name ---
NUKE_EXECUTOR_SCRIPT_NAME = "_nuke_executor.py"

__all__ = [
    # Nuke Executable Defaults (might change based on fixenv import)
    'DEFAULT_NUKE_EXECUTABLE_WIN',
    'DEFAULT_NUKE_EXECUTABLE_LIN',
    'DEFAULT_NUKE_EXECUTABLE_MAC',

    # Default Vendor Name
    'DEFAULT_VENDOR_NAME',

    # SPT Folder Names
    'VENDOR_DIR', 'SHOW_DIR', 'EPISODE_DIR', 'SHOT_DIR',

    # Relative Paths
    'PROJECT_FILES_REL', 'ELEMENTS_REL', 'PRERENDERS_REL', 'ROTO_REL',
    'TRACKS_REL', 'CLEANPLATES_REL', 'MATTES_REL', 'REFERENCE_REL', 'LUT_REL',
    'GEO_CACHE_REL', 'CAMERA_REL',

    # Node Classes
    'READ_NODE_CLASSES', 'WRITE_NODE_CLASSES',

    # Path Safety
    'INVALID_FILENAME_CHARS',

    # Internal Script
    'NUKE_EXECUTOR_SCRIPT_NAME',
]