"""Constants used by the Fix Archive tool."""
import os # Use os for path joining

# --- Nuke Executable Paths ---
from fixenv import (
    NUKE_EXEC_PATH_WIN,
    NUKE_EXEC_PATH_LIN,
    NUKE_EXEC_PATH_MAC,
)

# --- SPT v3.2.0 Folder Names (Placeholders for format()) ---
# These should match the spec exactly. Use braces {} for placeholders.
VENDOR_DIR = "{vendor}"
SHOW_DIR = "{show}"
SEASON_DIR = "{season}" # Optional, only added if season metadata exists and is non-empty
EPISODE_DIR = "{episode}"
SHOT_DIR = "{shot}"

# Relative paths within the SHOT_DIR, using os.path.join and normalizing slashes
# Ensures correct separator regardless of OS where script runs, then forces forward slash.
def _spt_rel_path(*args):
    """Helper to join path components and ensure forward slashes."""
    return os.path.join(*args).replace("\\", "/")

PROJECT_FILES_REL = _spt_rel_path("project", "nuke")
ELEMENTS_REL = "elements" # Root elements folder
PRERENDERS_REL = "prerenders"
ROTO_REL = "roto" # As per spec, sometimes under elements, sometimes separate? Assuming separate for now.
TRACKS_REL = "tracks"
CLEANPLATES_REL = _spt_rel_path(ELEMENTS_REL, "cleanplates") # Subfolder under elements
MATTES_REL = _spt_rel_path(ELEMENTS_REL, "mattes") # Subfolder under elements
REFERENCE_REL = "reference" # General reference folder
LUT_REL = _spt_rel_path(REFERENCE_REL, "lut") # Example LUT location under reference

# --- Nuke Node Classes ---
# Classes typically containing file paths for *reading* dependencies
# List should be comprehensive based on common usage.
READ_NODE_CLASSES = [
    "Read",
    "ReadGeo", "ReadGeo2", # Include older geo reader
    "DeepRead",
    "Camera", "Camera2", "Camera3", # Camera nodes often load Alembic/FBX
    "Axis", "Axis2", "Axis3", # Axis nodes can also load geometry
    "OCIOFileTransform", # Reads LUTs (.csp, .cub, etc.)
    "Vectorfield", # Reads .vf files
    "GenerateLUT", # Often reads source LUTs (.cube, .spi1d, etc.) for baking
    "BlinkScript", # Can define file knobs
    "ParticleCache", # Reads particle caches
    "PointCloudGenerator", # Might read geo
    # Add specific plugins/gizmos known to read files if needed
    # "STMap", # Reads UV maps
    # "PlanarTracker", # Might save/load tracking data? Check knobs.
]

# Classes considered as final output nodes for pruning trace
# This list determines the starting points for dependency tracing.
WRITE_NODE_CLASSES = [
    "Write",
    "WriteGeo", # For geometry output
    "DeepWrite", # For deep data output
    # Custom Write nodes like WriteFix are handled separately by `is_valid_writefix`
]

# --- LTFS / Path Safety ---
# Characters generally considered unsafe for LTFS or simple cross-platform paths.
# Includes: <>:"/\|?* and whitespace (\s)
# Adjusted to be slightly less strict on spaces if needed, but SPT spec might disallow them.
# Sticking to stricter pattern for now. Use raw string r'...'
INVALID_FILENAME_CHARS = r'[<>:"/\\|?*\s]'

__all__ = [
    # Nuke Executables
    'NUKE_EXEC_PATH_WIN',
    'NUKE_EXEC_PATH_LIN',
    'NUKE_EXEC_PATH_MAC',
    
    # SPT Folder Names
    'VENDOR_DIR',
    'SHOW_DIR',
    'SEASON_DIR',
    'EPISODE_DIR',
    'SHOT_DIR',
    
    # Relative Paths
    'PROJECT_FILES_REL',
    'ELEMENTS_REL',
    'PRERENDERS_REL',
    'ROTO_REL',
    'TRACKS_REL',
    'CLEANPLATES_REL',
    'MATTES_REL',
    'REFERENCE_REL',
    'LUT_REL',
    
    # Node Classes
    'READ_NODE_CLASSES',
    'WRITE_NODE_CLASSES',
    
    # Path Safety
    'INVALID_FILENAME_CHARS',
]
