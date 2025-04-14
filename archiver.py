"""Handles file copying and archive structure creation."""

from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import os

from . import constants, log
from .utils import normalize_path, ensure_ltfs_safe, copy_file_or_sequence, validate_path_exists
from .exceptions import ArchiverError, ConfigurationError, DependencyError

def _get_spt_path(archive_root: str, metadata: Dict[str, str], relative_path: str) -> Path:
    """
    Constructs the full SPT path within the archive root, based on metadata.
    Performs basic sanitization on metadata values used in paths.
    """
    try:
        # Sanitize metadata used in paths (replace problematic chars, ensure not empty)
        def sanitize_for_path(value: str, key_name: str) -> str:
            if not isinstance(value, str): value = str(value) # Ensure string
            # Basic sanitize: replace slashes, colons, maybe excessive whitespace?
            sanitized = value.replace('\\', '_').replace('/', '_').replace(':', '_').strip()
            # Add more specific replacements if needed
            # Check if result is empty after sanitizing (except for optional season)
            if not sanitized and key_name != 'season':
                 raise ValueError(f"Metadata key '{key_name}' resulted in empty string after sanitization ('{value}')")
            # Check for remaining invalid chars (ensure_ltfs_safe handles this later, but good preliminary check)
            # if not ensure_ltfs_safe(sanitized): # Check individual component
            #      raise ValueError(f"Sanitized metadata key '{key_name}' ('{sanitized}') still contains invalid characters.")
            return sanitized

        vendor = sanitize_for_path(metadata['vendor'], 'vendor')
        show = sanitize_for_path(metadata['show'], 'show')
        season = sanitize_for_path(metadata.get('season', ''), 'season') # Optional
        episode = sanitize_for_path(metadata['episode'], 'episode')
        shot = sanitize_for_path(metadata['shot'], 'shot')

        # Construct base path
        base = Path(normalize_path(archive_root)) / \
               constants.VENDOR_DIR.format(vendor=vendor) / \
               constants.SHOW_DIR.format(show=show)

        if season: # Only add season dir if season metadata is present and non-empty
            base /= constants.SEASON_DIR.format(season=season)

        base /= constants.EPISODE_DIR.format(episode=episode) / \
                constants.SHOT_DIR.format(shot=shot)

        # Ensure relative path doesn't try to escape the base (basic check)
        clean_relative_path = normalize_path(relative_path).strip('/')
        if '..' in clean_relative_path.split('/'):
             raise ValueError(f"Relative path '{relative_path}' contains '..', potentially unsafe.")

        # Combine base and relative path
        full_path = base / clean_relative_path

        # Defer final LTFS check until filename is added in map_dependency_to_archive

        return full_path

    except KeyError as e:
        # Specific error if required metadata (vendor, show, episode, shot) is missing
        raise ConfigurationError(f"Missing required metadata key for SPT path construction: {e}. Provided: {metadata}") from e
    except ValueError as e:
        # Catch errors from sanitization or path construction logic
        raise ArchiverError(f"Error constructing SPT path: {e}") from e
    except Exception as e:
        # Catch any other unexpected errors
        log.exception("Unexpected error during SPT path construction.")
        raise ArchiverError(f"Unexpected error constructing SPT path: {e}") from e


def map_dependency_to_archive(
    manifest_key: str, # Use node.knob key from parser
    dep_data: Dict[str, Any],
    archive_root: str,
    metadata: Dict[str, str]
) -> Tuple[Optional[str], Optional[str]]:
    """
    Determines the source path and the absolute archive destination path for a dependency.

    Returns:
        Tuple (absolute_source_path, absolute_archive_path_with_filename).
        Returns (source_path, None) if mapping fails or destination path is invalid.
        Returns (None, None) if source path itself is invalid.
    """
    source_path = dep_data.get("evaluated_path")
    node_class = dep_data.get("node_class")
    node_name = dep_data.get("node_name") # For logging/context

    if not source_path: # Don't check node_class, might be None for some reason
        log.warning(f"Skipping mapping for '{manifest_key}': Missing source path.")
        return None, None # Cannot proceed without source

    # Normalize source path for internal use
    norm_source_path = normalize_path(source_path)

    try:
        filename = Path(norm_source_path).name
        # Ensure filename itself is safe *before* constructing full path
        if not ensure_ltfs_safe(filename):
             log.warning(f"Filename '{filename}' from '{norm_source_path}' (Source: {manifest_key}) contains invalid characters. Skipping archive for this file.")
             return norm_source_path, None # Return source but None for destination

        # --- Determine Relative SPT Folder ---
        # Default to 'elements'
        rel_spt_folder = constants.ELEMENTS_REL
        lower_source = norm_source_path.lower() # Use normalized path for checks

        # More specific rules based on common patterns and node types
        if node_class in ["Write", "DeepWrite", "WriteGeo"]:
            # Outputs being read back in are often pre-renders
            if "prerender" in lower_source or "precomp" in lower_source:
                rel_spt_folder = constants.PRERENDERS_REL
            # Add rules based on Write node names or paths if needed
        elif node_class in ["ReadGeo2", "Camera3", "Axis3", "Camera2", "Axis2"]:
            if "track" in lower_source or "matchmove" in lower_source or node_class.startswith("Camera") or node_class.startswith("Axis"):
                rel_spt_folder = constants.TRACKS_REL
            # Otherwise, keep as 'elements' (could be Alembic caches etc.)
        elif node_class in ["Read", "DeepRead"]:
            if "/roto/" in lower_source or "_roto." in lower_source:
                 rel_spt_folder = constants.ROTO_REL
            elif "/matte/" in lower_source or "_matte." in lower_source:
                 rel_spt_folder = constants.MATTES_REL
            elif "/cleanplate/" in lower_source or "_cp." in lower_source or "cleanplate" in lower_source:
                 rel_spt_folder = constants.CLEANPLATES_REL
            elif "plate" in lower_source or "element" in lower_source: # Common keywords for source footage
                 rel_spt_folder = constants.ELEMENTS_REL # Explicitly map to elements
            # Add more rules (e.g., for textures, reference images)
        elif node_class == "OCIOFileTransform":
             # LUTs usually go into a specific folder, maybe 'reference/lut'? Assume 'elements' for now.
             # rel_spt_folder = "reference/lut" # Example if needed
             pass # Keep default 'elements'

        # Add more rules here based on path components, tags, task names etc.

        # --- Construct Full Destination Path ---
        target_base_dir = _get_spt_path(archive_root, metadata, rel_spt_folder)
        target_path = target_base_dir / filename # Combine directory and filename

        # --- Final LTFS Check on Full Path ---
        # Check each component of the final absolute path
        for part in target_path.parts:
            if not ensure_ltfs_safe(part):
                 log.error(f"Constructed archive path component '{part}' in '{target_path}' contains invalid characters. Cannot archive to this location.")
                 return norm_source_path, None # Cannot use this destination

        log.debug(f"Mapped '{manifest_key}' ({node_class}, {norm_source_path}) -> {target_path}")

        return norm_source_path, str(target_path) # Return strings

    except Exception as e:
        # Catch errors during mapping logic (e.g., from _get_spt_path, Path operations)
        log.error(f"Failed to determine archive path for '{manifest_key}' ({norm_source_path}): {e}")
        return norm_source_path, None # Return source but None for destination

def archive_project(
    source_script_path: str, # Path to the script being archived (e.g., the pruned temp script)
    dependency_manifest: Dict[str, Any], # Manifest derived from source_script_path
    archive_root: str,
    metadata: Dict[str, str],
    dry_run: bool = False
) -> Dict[str, Optional[str]]:
    """
    Copies the source script and all valid dependencies (from manifest) to the SPT archive structure.

    Args:
        source_script_path: Path to the Nuke script to be placed in the archive.
        dependency_manifest: Dictionary from the parser ('node.knob' -> data).
        archive_root: Root directory for the archive.
        metadata: Dictionary containing vendor, show, episode, shot, etc.
        dry_run: If True, simulate without copying.

    Returns:
        A dictionary mapping original evaluated dependency paths to their new archived paths (or None if failed).
        Includes the source script itself under the special key "script".
    """
    log.info("Starting project archiving process...")
    archive_map = {} # {original_evaluated_path: archive_path_or_None}
    copied_files_log = [] # Tracks (src, dest) pairs successfully copied/simulated
    failed_archives = [] # Tracks original source paths that failed archiving

    # --- 1. Archive the Source Nuke Script ---
    norm_script_path = normalize_path(source_script_path)
    script_filename = Path(norm_script_path).name
    base_name, ext = os.path.splitext(script_filename)

    # Construct a more meaningful archive script name using metadata
    # Remove temporary suffixes like _pruned or _baked if present
    clean_base = base_name.replace("_pruned", "").replace("_baked", "")
    # Use shot name + optional suffix + original extension
    # Maybe add version if available in metadata? For now, keep simple.
    archive_script_name = f"{metadata['shot']}_archive{ext}"
    log.debug(f"Determined archive script name: {archive_script_name}")

    try:
        # Get the target directory within SPT structure
        archive_script_base_dir = _get_spt_path(archive_root, metadata, constants.PROJECT_FILES_REL)
        # Construct full path and ensure it's safe
        archive_script_path_obj = archive_script_base_dir / archive_script_name
        for part in archive_script_path_obj.parts: ensure_ltfs_safe(part)
        archive_script_path = str(archive_script_path_obj)

        log.info(f"Archiving source script: {norm_script_path} -> {archive_script_path}")
        archive_map["script"] = archive_script_path # Special key

        # Ensure source script exists before attempting copy
        validate_path_exists(norm_script_path, "Source script for archive")

        # Perform the copy (or simulation)
        copied_pairs = copy_file_or_sequence(norm_script_path, archive_script_path, None, dry_run)
        if not dry_run and not copied_pairs: # Check if copy actually occurred
             raise ArchiverError("copy_file_or_sequence returned empty list for source script.")
        copied_files_log.extend(copied_pairs)
        log.info(f"Source script archived {'(simulated)' if dry_run else ''}.")

    except (ConfigurationError, ArchiverError, DependencyError, Exception) as e:
         log.exception(f"CRITICAL: Failed to archive source Nuke script {norm_script_path}. Aborting.")
         archive_map["script"] = None
         # Re-raise as critical failure if the script itself cannot be archived
         raise ArchiverError(f"Could not archive source Nuke script: {e}") from e

    # --- 2. Archive Dependencies ---
    # Track unique source paths to avoid redundant processing and copying
    processed_source_paths = {norm_script_path}

    log.info(f"Archiving dependencies listed in manifest ({len(dependency_manifest)} entries)...")
    for manifest_key, dep_data in dependency_manifest.items():
        original_eval_path = dep_data.get("evaluated_path")

        if not original_eval_path: continue # Skip entries without a path

        norm_source_path = normalize_path(original_eval_path)

        # Check if this source path has already been processed
        if norm_source_path in processed_source_paths:
            log.debug(f"Skipping already processed source path: {norm_source_path} (from {manifest_key})")
            # Ensure map reflects the previous outcome for this path if needed? Usually not necessary.
            continue

        processed_source_paths.add(norm_source_path) # Mark as processed

        # Check for validation errors reported by the parser
        if dep_data.get("validation_error"):
            log.warning(f"Skipping archive for '{norm_source_path}' (Source: {manifest_key}) due to parser validation error: {dep_data['validation_error']}")
            archive_map[norm_source_path] = None # Mark as failed
            failed_archives.append(norm_source_path)
            continue

        # Get the target archive path for this dependency
        mapped_source, archive_dep_path = map_dependency_to_archive(manifest_key, dep_data, archive_root, metadata)

        # mapped_source should match norm_source_path here
        if not archive_dep_path:
             # Mapping failed (e.g., invalid chars, construction error)
             log.error(f"Failed to determine valid archive path for '{norm_source_path}' (Source: {manifest_key}). Skipping archive.")
             archive_map[norm_source_path] = None
             failed_archives.append(norm_source_path)
             continue

        # Proceed with copying the dependency
        try:
            frame_range = None
            if dep_data.get("is_sequence"):
                f1, f2 = dep_data.get("first_frame"), dep_data.get("last_frame")
                # Check for valid integer frames before creating tuple
                if f1 is not None and f2 is not None:
                     try:
                          frame_range = (int(f1), int(f2))
                     except (ValueError, TypeError):
                          raise DependencyError(f"Invalid non-integer frame range ({f1}-{f2}) found for sequence node {dep_data.get('node_name')}")
                else:
                    # Frame range is required for sequence copy if not determinable
                    raise DependencyError(f"Missing valid frame range ({f1}-{f2}) for sequence '{norm_source_path}' (Source: {manifest_key})")

            # Perform copy/simulation - validate_path_exists is called inside copy func
            log.debug(f"Copying dependency: {norm_source_path} -> {archive_dep_path}")
            copied_pairs = copy_file_or_sequence(norm_source_path, archive_dep_path, frame_range, dry_run)

            # Verify copy outcome if not dry run
            if not dry_run and not copied_pairs:
                 # Indicates failure inside copy_file_or_sequence (e.g., file missing just before copy, skipped all frames)
                 raise ArchiverError(f"Copy operation returned no files for dependency {norm_source_path}. Check logs.")

            copied_files_log.extend(copied_pairs)
            archive_map[norm_source_path] = archive_dep_path # Map original evaluated path -> final archive path

        except (DependencyError, ArchiverError, Exception) as e:
            # Catch errors during the copy process for this specific dependency
            log.error(f"Failed to archive dependency '{norm_source_path}' (Source: {manifest_key}): {e}")
            archive_map[norm_source_path] = None # Mark as failed
            failed_archives.append(norm_source_path)
            # Continue processing other dependencies

    # --- Final Summary ---
    if failed_archives:
         # Log unique failed paths clearly
         unique_failed = sorted(list(set(failed_archives)))
         log.warning(f"Archiving finished with {len(unique_failed)} unique dependency archival failures:")
         for failed_path in unique_failed:
              log.warning(f"  - {failed_path}")
    else:
         log.info("All dependencies processed successfully.")

    successful_deps = len([k for k,v in archive_map.items() if v is not None and k != 'script'])
    total_dep_entries = len(dependency_manifest) # Count entries in manifest
    unique_source_paths_processed = len(processed_source_paths) - 1 # Exclude script itself

    log.info(f"Archiving summary: Processed {total_dep_entries} dependency entries corresponding to {unique_source_paths_processed} unique source paths.")
    log.info(f"Successfully archived {successful_deps} unique dependencies {'(simulated)' if dry_run else ''}.")
    log.debug(f"Total file copy operations performed/simulated: {len(copied_files_log)}")

    return archive_map