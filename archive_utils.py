# fixarc/archive_utils.py
"""
Utilities specifically for determining archive paths based on SPT structure and metadata.
"""
from pathlib import Path
# Make sure all necessary types are imported from typing
from typing import Dict, Any, Optional, Tuple # Added Tuple just in case, ensure Dict is here

from fixenv import normalize_path
from . import constants, log
from .utils import ensure_ltfs_safe # Use general utils for path safety
from .exceptions import ConfigurationError, ArchiverError

def _get_spt_directory(
    archive_root: str,
    metadata: Dict[str, str],
    relative_category_path: str
) -> Path:
    """
    Constructs the absolute SPT directory path for a given category within the archive.
    The structure is: {archive_root}/{vendor}/{show}/{episode}/{episode}_{sequence}_{shot}_{tag}/{relative_category_path}

    Args:
        archive_root: The absolute root path of the archive destination.
        metadata: Dictionary containing required keys ('vendor', 'show', 'episode', 'sequence', 'shot', 'tag').
        relative_category_path: The relative path within the shot folder determined by
                                mapping rules (e.g., 'assets/images', 'projects/nuke').
                                If empty, returns the base shot directory path.

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
            """Ensure string, basic sanitize, check non-empty."""
            if value is None or value == '' or str(value).strip() == '':
                raise ValueError(f"Required metadata key '{key_name}' cannot be empty.")

            val_str = str(value).strip() # Ensure string and strip whitespace
            # Basic sanitization: replace common problematic chars with underscore
            sanitized = val_str.replace('\\', '_').replace('/', '_').replace(':', '_').strip()
            # Check for remaining invalid characters according to constants
            if not ensure_ltfs_safe(sanitized):
                raise ValueError(f"Sanitized metadata for '{key_name}' ('{sanitized}') contains invalid characters.")
            if not sanitized:
                raise ValueError(f"Metadata key '{key_name}' resulted in empty string after sanitization ('{value}')")
            return sanitized

        # Ensure required keys exist before sanitizing
        required_keys = ['vendor', 'show', 'episode', 'sequence', 'shot', 'tag']
        missing_keys = [k for k in required_keys if k not in metadata or not metadata[k]]
        if missing_keys:
             raise KeyError(f"Missing required metadata key(s): {', '.join(missing_keys)}")

        vendor = sanitize_for_path(metadata['vendor'], 'vendor')
        show = sanitize_for_path(metadata['show'], 'show')
        episode = sanitize_for_path(metadata['episode'], 'episode')
        sequence = sanitize_for_path(metadata['sequence'], 'sequence')
        shot = sanitize_for_path(metadata['shot'], 'shot')
        tag = sanitize_for_path(metadata['tag'], 'tag')

        # --- Construct Base Path (Vendor/Show/Episode/Shot) ---
        base = Path(archive_root) / \
               constants.VENDOR_DIR.format(vendor=vendor) / \
               constants.SHOW_DIR.format(show=show) / \
               constants.EPISODE_DIR.format(episode=episode) / \
               constants.SHOT_DIR.format(episode=episode, sequence=sequence, shot=shot, tag=tag)

        # --- Add Relative Category Path (if provided) ---
        full_dir_path = base
        if relative_category_path:
            # Assume relative_category_path might not be normalized yet
            clean_relative_path = normalize_path(relative_category_path).strip('/')
            if '..' in clean_relative_path.split('/'):
                 raise ValueError(f"Relative category path '{relative_category_path}' contains '..', potentially unsafe.")
            full_dir_path = base / clean_relative_path

        # Check constructed directory parts for safety
        for part in full_dir_path.parts[len(Path(archive_root).parts):]:
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

# Removed map_dependency_to_archive_path function
# This logic is now handled in cli.py using rules and get_spt_directory

def get_archive_script_path(
    archive_root: str,
    metadata: Dict[str, str],
    original_script_name: str
) -> str:
    """
    Determines the final path for the Nuke script within the archive.
    Uses a standard relative path defined in constants (PROJECT_FILES_REL)
    and preserves the original filename.

    Args:
        archive_root: The absolute root path of the archive destination.
        metadata: Dictionary containing metadata.
        original_script_name: The filename of the original script, used as-is.

    Returns:
        The absolute destination path for the script as a string.

    Raises:
        ConfigurationError: If required metadata is missing or invalid.
        ArchiverError: If path construction fails or the filename is invalid.
    """
    log.debug(f"Determining archive path for script '{original_script_name}'")
    try:
        # Validate the original filename is LTFS safe
        if not ensure_ltfs_safe(original_script_name):
             log.warning(f"Original script name '{original_script_name}' contains potentially unsafe characters.")
        
        # Get the target directory within SPT structure using the fixed relative path for project files
        archive_script_dir = _get_spt_directory(archive_root, metadata, constants.PROJECT_FILES_REL)
        
        # Simply use the original script name without modification
        final_path = archive_script_dir / original_script_name

        log.info(f"Determined final archive script path: {final_path}")
        return str(final_path)

    except (ConfigurationError, ArchiverError, ValueError, KeyError) as e:
        # Catch specific expected errors
        log.error(f"Failed to determine final script archive path: {e}")
        # Re-raise as ArchiverError, as this path is critical
        raise ArchiverError(f"Failed to determine final script archive path: {e}") from e
    except Exception as e:
        # Catch any other unexpected errors
        log.exception("Unexpected error determining final script archive path.")
        raise ArchiverError(f"Unexpected error determining final script archive path: {e}") from e