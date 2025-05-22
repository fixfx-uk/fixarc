# fixarc/constants.py
"""Constants used by the Fix Archive (fixarc) tool."""
import os
from typing import Dict, List, FrozenSet, Callable, Any
from pathlib import Path

# Import fixenv directly
import fixenv

# Use studio short name from fixenv
DEFAULT_VENDOR_NAME = getattr(fixenv.constants, 'STUDIO_SHORT_NAME', 'FixFX')

# --- SPT v3.2.0 Folder Names (Placeholders for format()) ---
# These should match the spec exactly. Use braces {} for placeholders.
VENDOR_DIR: str = "{vendor}"
SHOW_DIR: str = "{show}"
EPISODE_DIR: str = "{episode}"
SHOT_DIR: str = "{episode}_{sequence}_{shot}_{tag}"

# --- Relative Archive Paths within SHOT_DIR ---
def _rel_path(*args: str) -> str:
    """Helper to join path components and ensure forward slashes.
    
    Args:
        *args: Path components to join
        
    Returns:
        Joined path with forward slashes
    """
    return os.path.join(*args).replace("\\", "/")

PROJECT_FILES_REL: str = _rel_path("project", "nuke")
ELEMENTS_REL: str = "elements" # Root elements folder
PRERENDERS_REL: str = "prerenders"
ROTO_REL: str = "roto"
TRACKS_REL: str = "tracks"
CLEANPLATES_REL: str = _rel_path(ELEMENTS_REL, "cleanplates") # Subfolder under elements
MATTES_REL: str = _rel_path(ELEMENTS_REL, "mattes") # Subfolder under elements
REFERENCE_REL: str = "reference"
LUT_REL: str = _rel_path(REFERENCE_REL, "lut")
GEO_CACHE_REL: str = _rel_path(ELEMENTS_REL, "geo_cache") # Example for geo/alembic
CAMERA_REL: str = _rel_path(TRACKS_REL, "camera")      # Example for cameras

# --- Asset Handling ---
ASSETS_REL: str = "assets" # Standard relative path for assets at vendor level
# General library roots. Paths should be absolute and use forward slashes.
# Trailing slash is recommended for robust prefix matching.
LIBRARY_ROOTS: List[str] = [
    "Z:/fxlb/",
    "/mnt/fxlb/",
    # Add other common, fixed library paths here
]
# Project-specific assets (e.g., Z:/proj/{project_name}/assets/) are handled dynamically
# in the Nuke executor using metadata, but these general ones can be defined here.

# --- Nuke Node Classes ---
# Classes typically containing file paths for *reading* dependencies
READ_NODE_CLASSES: FrozenSet[str] = frozenset([
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
WRITE_NODE_CLASSES: FrozenSet[str] = frozenset([
    "Write",
    "WriteGeo",
    "DeepWrite",
    # WriteFix handled specially
])

# --- LTFS / Path Safety ---
# Characters generally considered unsafe for LTFS or simple cross-platform paths.
INVALID_FILENAME_CHARS: str = r'[<>:"/\\|?*\s]' # Raw string

# --- Internal Script Name ---
NUKE_EXECUTOR_SCRIPT_NAME: str = "_nuke_executor.py"

# Path to the internal Nuke script (derived from this file's location)
NUKE_EXECUTOR_SCRIPT_PATH: Path = Path(__file__).parent / NUKE_EXECUTOR_SCRIPT_NAME

__all__ = [
    # OS Detection (via fixenv)
    'fixenv',
    
    # Default Vendor Name
    'DEFAULT_VENDOR_NAME',

    # SPT Folder Names
    'VENDOR_DIR', 'SHOW_DIR', 'EPISODE_DIR', 'SHOT_DIR',

    # Relative Paths
    'PROJECT_FILES_REL', 'ELEMENTS_REL', 'PRERENDERS_REL', 'ROTO_REL',
    'TRACKS_REL', 'CLEANPLATES_REL', 'MATTES_REL', 'REFERENCE_REL', 'LUT_REL',
    'GEO_CACHE_REL', 'CAMERA_REL',

    # Asset Handling
    'ASSETS_REL', 'LIBRARY_ROOTS',

    # Node Classes
    'READ_NODE_CLASSES', 'WRITE_NODE_CLASSES',

    # Path Safety
    'INVALID_FILENAME_CHARS',

    # Internal Script
    'NUKE_EXECUTOR_SCRIPT_NAME',
    'NUKE_EXECUTOR_SCRIPT_PATH',
]