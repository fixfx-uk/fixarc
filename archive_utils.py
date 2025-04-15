# fixarc/archive_utils.py
"""
Utilities specifically for determining archive paths based on SPT structure and metadata.
"""
from pathlib import Path
from typing import Dict, Any, Optional
import os

from . import constants, log
from .utils import normalize_path, ensure_ltfs_safe # Use general utils for path safety
from .exceptions import ConfigurationError, ArchiverError

def get_spt_directory(
    archive_root: str,
    metadata: Dict[str, str],
    relative_category_path: str
) -> Path:
    """
    Constructs the absolute SPT directory path for a given category within the archive.

    Args:
        archive_root: The absolute root path of the archive destination.
        metadata: Dictionary containing required keys ('vendor', 'show', 'episode', 'shot')
                  and optional keys ('season').
        relative_category_path: The relative path within the shot folder
                                (e.g., constants.ELEMENTS_REL, constants.PROJECT_FILES_REL).

    Returns:
        A Path object representing the absolute directory path.

    Raises:
        ConfigurationError: If required metadata is missing or invalid.
        ArchiverError: If path construction fails.
    """
    log.debug(f"Constructing SPT directory for category '{relative_category_path}'")
    try:
        # --- Sanitize metadata components used in the path ---
        def sanitize_for_path(value: Optional[Any], key_name: str) -> str:
            """Ensure string, basic sanitize, check non-empty (unless optional)."""
            is_optional = key_name == 'season'
            if value is None or value == '':
                if is_optional: return "" # Allow empty optional season
                raise ValueError(f"Required metadata key '{key_name}' cannot be empty.")

            val_str = str(value).strip() # Ensure string and strip whitespace
            # Basic sanitization: replace common problematic chars with underscore
            sanitized = val_str.replace('\\', '_').replace('/', '_').replace(':', '_')
            # Check for remaining invalid characters according to constants
            if not ensure_ltfs_safe(sanitized):
                raise ValueError(f"Sanitized metadata for '{key_name}' ('{sanitized}') contains invalid characters.")
            if not sanitized and not is_optional:
                raise ValueError(f"Metadata key '{key_name}' resulted in empty string after sanitization ('{value}')")
            return sanitized

        vendor = sanitize_for_path(metadata.get('vendor'), 'vendor')
        show = sanitize_for_path(metadata.get('show'), 'show')
        season = sanitize_for_path(metadata.get('season'), 'season') # Optional
        episode = sanitize_for_path(metadata.get('episode'), 'episode')
        shot = sanitize_for_path(metadata.get('shot'), 'shot')

        # --- Construct Base Path ---
        base = Path(normalize_path(archive_root)) / \
               constants.VENDOR_DIR.format(vendor=vendor) / \
               constants.SHOW_DIR.format(show=show)

        if season: # Only add season dir if season metadata is present and non-empty
            base /= constants.SEASON_DIR.format(season=season)

        base /= constants.EPISODE_DIR.format(episode=episode) / \
                constants.SHOT_DIR.format(shot=shot)

        # --- Add Relative Category Path ---
        # Ensure relative path doesn't try to escape the base (basic check)
        clean_relative_path = normalize_path(relative_category_path).strip('/')
        if '..' in clean_relative_path.split('/'):
             raise ValueError(f"Relative category path '{relative_category_path}' contains '..', potentially unsafe.")

        # Combine base and relative category path
        full_dir_path = base / clean_relative_path

        # Final safety check on the full directory path components
        for part in full_dir_path.parts[len(Path(archive_root).parts):]: # Check only added parts
             if not ensure_ltfs_safe(part):
                  raise ValueError(f"Constructed SPT directory path component '{part}' contains invalid characters.")

        log.debug(f"Constructed SPT directory path: {full_dir_path}")
        return full_dir_path

    except KeyError as e:
        raise ConfigurationError(f"Missing required metadata key for SPT path: {e}. Provided: {metadata}") from e
    except ValueError as e:
        raise ArchiverError(f"Error constructing SPT directory path: {e}") from e
    except Exception as e:
        log.exception("Unexpected error during SPT directory path construction.")
        raise ArchiverError(f"Unexpected error constructing SPT directory path: {e}") from e


def map_dependency_to_archive_path(
    manifest_key: str, # node.knob identifier
    dep_data: Dict[str, Any],
    archive_root: str,
    metadata: Dict[str, str]
) -> Optional[str]:
    """
    Determines the absolute archive destination path (including filename) for a dependency.

    Args:
        manifest_key: Identifier from the manifest (e.g., "Read1.file").
        dep_data: The dictionary of data for this dependency from the manifest.
        archive_root: The absolute root path of the archive destination.
        metadata: Dictionary containing SPT metadata.

    Returns:
        The absolute destination path as a string, or None if mapping fails or
        the path is deemed invalid.
    """
    source_path = dep_data.get("evaluated_path")
    node_class = dep_data.get("node_class")
    node_name = dep_data.get("node_name") # For logging/context

    if not source_path:
        log.warning(f"Skipping mapping for '{manifest_key}': Missing source path.")
        return None

    norm_source_path = normalize_path(source_path)

    try:
        filename = Path(norm_source_path).name
        # Ensure filename itself is safe before proceeding
        if not ensure_ltfs_safe(filename):
             log.warning(f"Filename '{filename}' from '{norm_source_path}' (Source: {manifest_key}) contains invalid characters. Cannot archive.")
             return None

        # --- Determine Relative SPT Folder based on heuristics ---
        rel_spt_folder = constants.ELEMENTS_REL # Default
        lower_source = norm_source_path.lower()

        # Specific node class mappings take precedence
        if node_class == "OCIOFileTransform":
             rel_spt_folder = constants.LUT_REL
        elif node_class in ["ReadGeo2", "Camera3", "Axis3", "Camera2", "Axis2", "ReadGeo"]:
             if "track" in lower_source or "matchmove" in lower_source or node_class.startswith("Camera") or node_class.startswith("Axis"):
                 rel_spt_folder = constants.CAMERA_REL if node_class.startswith("Camera") else constants.TRACKS_REL
             else: # Assume generic geometry caches go here
                 rel_spt_folder = constants.GEO_CACHE_REL
        elif node_class == "Vectorfield":
             rel_spt_folder = constants.ELEMENTS_REL # Or a specific vector field dir?
        elif node_class == "GenerateLUT":
             # Often reads source LUTs, store them with other LUTs?
             rel_spt_folder = constants.LUT_REL
        elif node_class in ["Read", "DeepRead"]: # General readers, use path keywords
            if "/roto/" in lower_source or "_roto." in lower_source:
                 rel_spt_folder = constants.ROTO_REL
            elif "/matte/" in lower_source or "_matte." in lower_source:
                 rel_spt_folder = constants.MATTES_REL
            elif "/cleanplate/" in lower_source or "_cp." in lower_source or "cleanplate" in lower_source:
                 rel_spt_folder = constants.CLEANPLATES_REL
            elif "/lut/" in lower_source or any(lower_source.endswith(ext) for ext in ['.lut', '.csp', '.cube']):
                 rel_spt_folder = constants.LUT_REL
            elif "/reference/" in lower_source or "/ref/" in lower_source:
                 rel_spt_folder = constants.REFERENCE_REL
            elif "prerender" in lower_source or "precomp" in lower_source:
                 rel_spt_folder = constants.PRERENDERS_REL
            # Keep default ELEMENTS_REL if no other keywords match

        # Add more sophisticated rules based on project conventions if needed

        # --- Construct Full Destination Path ---
        target_base_dir = get_spt_directory(archive_root, metadata, rel_spt_folder)
        target_path = target_base_dir / filename # Combine directory and filename

        log.debug(f"Mapped '{manifest_key}' ({node_class}, {norm_source_path}) -> {target_path}")
        return str(target_path) # Return as string

    except (ConfigurationError, ArchiverError) as e:
        # Errors from get_spt_directory or path checks
        log.error(f"Failed to determine archive path for '{manifest_key}' ({norm_source_path}): {e}")
        return None
    except Exception as e:
        log.error(f"Unexpected error mapping dependency '{manifest_key}' ({norm_source_path}): {e}")
        return None


def get_archive_script_path(
    archive_root: str,
    metadata: Dict[str, str],
    original_script_name: str
) -> str:
    """
    Determines the final path for the Nuke script within the archive.

    Args:
        archive_root: The absolute root path of the archive destination.
        metadata: Dictionary containing SPT metadata.
        original_script_name: The filename of the original script being processed.

    Returns:
        The absolute destination path for the script as a string.

    Raises:
        ConfigurationError: If required metadata is missing or invalid.
        ArchiverError: If path construction fails.
    """
    log.debug(f"Determining archive path for script '{original_script_name}'")
    try:
        # Use shot name + _archive suffix + original extension
        base_name, ext = os.path.splitext(original_script_name)
        # Ensure extension is lowercase .nk
        if not ext or ext.lower() != ".nk": ext = ".nk"

        archive_script_name = f"{metadata['shot']}_archive{ext}"
        if not ensure_ltfs_safe(archive_script_name):
             raise ValueError(f"Generated archive script name '{archive_script_name}' contains invalid characters.")

        archive_script_dir = get_spt_directory(archive_root, metadata, constants.PROJECT_FILES_REL)
        final_path = archive_script_dir / archive_script_name

        log.info(f"Determined final archive script path: {final_path}")
        return str(final_path)

    except Exception as e:
        # Catch errors from get_spt_directory or filename checks
        log.error(f"Failed to determine final script archive path: {e}")
        # Re-raise as ArchiverError, as this path is critical
        raise ArchiverError(f"Failed to determine final script archive path: {e}") from e