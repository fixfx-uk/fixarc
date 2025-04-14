"""Repaths file paths within Nuke script content."""

import os
from pathlib import Path
from typing import Dict, Optional
import re

from . import log
from .exceptions import RepathingError
from .utils import normalize_path # Import normalize_path

def _calculate_relative_path(source_script_abs: str, target_dependency_abs: str) -> str:
    """
    Calculates the path of target_dependency_abs relative to the directory of source_script_abs.
    Uses forward slashes suitable for Nuke. Returns absolute path as fallback on error.
    """
    try:
        # Ensure inputs are normalized absolute paths
        norm_script_path = Path(normalize_path(source_script_abs))
        norm_target_path = Path(normalize_path(target_dependency_abs))

        if not norm_script_path.is_absolute() or not norm_target_path.is_absolute():
             raise ValueError("Input paths must be absolute for relative calculation.")

        source_dir = norm_script_path.parent

        # Use os.path.relpath for cross-platform compatibility including different drives on Windows
        relative = os.path.relpath(norm_target_path, source_dir)

        # Ensure forward slashes for Nuke compatibility
        nuke_relative_path = relative.replace("\\", "/")
        log.debug(f"Relative path from {source_dir} to {norm_target_path} -> {nuke_relative_path}")
        return nuke_relative_path

    except ValueError as e:
        # Handles cases like different drives on Windows where relpath fails
        abs_target_nuke = normalize_path(target_dependency_abs) # Ensure forward slashes
        log.warning(f"Could not calculate relative path from '{source_script_abs}' to '{target_dependency_abs}': {e}. Using absolute archive path: {abs_target_nuke}")
        # Return absolute path *within the archive* as fallback
        return abs_target_nuke
    except Exception as e:
        # Catch any other unexpected errors
        log.error(f"Unexpected error calculating relative path from '{source_script_abs}' to '{target_dependency_abs}': {e}")
        # Fallback to absolute path is safer than raising an error here maybe?
        abs_target_nuke = normalize_path(target_dependency_abs)
        log.warning(f"Falling back to absolute archive path due to error: {abs_target_nuke}")
        return abs_target_nuke
        # raise RepathingError(f"Relative path calculation failed: {e}") from e


def repath_script(
    script_content: str,
    archive_map: Dict[str, Optional[str]], # Maps original EVALUATED path -> archived path
    archive_script_path: str # The final destination path of the script being repathed
) -> str:
    """
    Replaces original evaluated file paths in script content with paths relative
    to the final archived script location.

    Args:
        script_content: The Nuke script content (pruned/baked) as a string.
        archive_map: Dictionary mapping original *evaluated* absolute paths to archived absolute paths (or None if failed).
        archive_script_path: The absolute path where this script *will be* saved in the archive.

    Returns:
        The modified script content with repathed file knobs.

    Raises:
        RepathingError: If critical errors occur.
    """
    log.info(f"Repathing script content relative to final destination: {archive_script_path}")
    modified_content = script_content
    repath_count = 0
    paths_not_found_in_script = []

    # Filter map: Only consider paths that were successfully archived and are not the script itself
    paths_to_repath = {
        orig_eval: archived
        for orig_eval, archived in archive_map.items()
        if archived and orig_eval != "script" and orig_eval # Ensure key is not empty
    }

    if not paths_to_repath:
        log.info("No successfully archived dependencies found to repath. Returning original content.")
        return script_content

    # Sort by length descending to replace longer paths first (e.g., /a/b/c before /a/b)
    sorted_original_eval_paths = sorted(paths_to_repath.keys(), key=len, reverse=True)

    log.debug(f"Attempting to repath {len(sorted_original_eval_paths)} paths.")

    current_content = modified_content # Work on a copy
    for original_eval_path in sorted_original_eval_paths:
        archived_path = paths_to_repath[original_eval_path]

        # Calculate the new relative path needed in the script
        relative_path = _calculate_relative_path(archive_script_path, archived_path)

        # --- Safer Replacement Strategy ---
        # We need to replace the string *as it appears in the script*. This might be
        # the `original_path` (unevaluated) or the `evaluated_path` or something else
        # if expressions were complex.
        # The most reliable way requires the original manifest data alongside the archive map.
        # Lacking that, we primarily target replacing the `evaluated_path` string,
        # assuming it's likely present literally.

        # Path string to search for in the script content (use normalized forward slashes)
        path_to_find_in_script = normalize_path(original_eval_path)
        escaped_path_to_find = re.escape(path_to_find_in_script)

        # Regex patterns to match common Nuke knob syntaxes
        patterns_to_try = [
            # 1. `knob_name {/path/to/file}` (Most common, includes potential whitespace)
            re.compile(r'(\b\w+\s*\{)(' + escaped_path_to_find + r')(\})'),
            # 2. `knob_name "/path/to/file"` (Double quotes)
            re.compile(r'(\b\w+\s*")(' + escaped_path_to_find + r')(")')
            # 3. `knob_name '/path/to/file'` (Single quotes - less common for paths but possible)
            # re.compile(r'(\b\w+\s*\')(' + escaped_path_to_find + r')(\')')
            # 4. `knob_name /path/to/file` (Unquoted - RISKY, avoid if possible or use very careful regex)
            # Example (needs refinement): re.compile(r'(\b(?:file|proxy|vfield_file)\s+)(' + escaped_path_to_find + r')(\s|$)')
        ]

        found_this_path = False
        num_replaced_this_path = 0

        working_content = current_content # Use copy for replacements for *this* path
        for i, pattern in enumerate(patterns_to_try):
            replace_occurrences = 0
            def replacer(match):
                nonlocal replace_occurrences
                replace_occurrences += 1
                # Group 1 is the prefix (e.g., 'file {'), Group 3 is the suffix (e.g., '}')
                return match.group(1) + relative_path + match.group(3)

            new_working_content = pattern.sub(replacer, working_content)

            if replace_occurrences > 0:
                 log.debug(f"  Replaced {replace_occurrences} instance(s) using pattern {i+1} for '{path_to_find_in_script}' -> '{relative_path}'")
                 working_content = new_working_content # Update working copy
                 found_this_path = True
                 num_replaced_this_path += replace_occurrences

        if found_this_path:
            current_content = working_content # Commit changes from working copy
            repath_count += num_replaced_this_path
        else:
             # Log if the path we expected to replace wasn't found literally
             log.warning(f"Evaluated path '{path_to_find_in_script}' not found literally in script using standard knob patterns. It might be generated by expressions or have unusual formatting.")
             paths_not_found_in_script.append(path_to_find_in_script)


    log.info(f"Script repathing complete. Performed {repath_count} literal path replacements.")
    if paths_not_found_in_script:
         log.warning(f"{len(paths_not_found_in_script)} evaluated paths were not found literally in the script and could not be automatically repathed.")
         log.debug(f"Paths not found literally: {paths_not_found_in_script}")

    # Return the final modified content
    return current_content