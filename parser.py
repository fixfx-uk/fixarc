"""
Parses dependencies from a given Nuke script (typically a pruned one).
"""
from typing import Dict, Any, Optional, Tuple, List
import os
from pathlib import Path

from . import log, utils
from .exceptions import ParsingError, DependencyError, ArchiveError

def parse_script_dependencies(script_path: str, frame_range_override: Optional[Tuple[int, int]] = None) -> Dict[str, Any]:
    """
    Parses a Nuke script using nuke_ops.py to extract file dependencies.

    Args:
        script_path: Path to the .nk script (should be the pruned script).
        frame_range_override: Optional tuple (start, end).

    Returns:
        The dependency manifest dictionary, mapping 'node.knob' keys to dependency data.

    Raises:
        ParsingError: If parsing fails or returns invalid data.
        DependencyError: If essential files are missing post-parsing (optional check).
    """
    log.info(f"Requesting dependency parsing from script: {script_path}")
    utils.validate_path_exists(script_path, "Nuke script for parsing") # Validate input script exists

    try:
        # Action: Parse dependencies via Nuke
        log.debug("Running Nuke action: parse")
        parse_results = utils.run_nuke_action(
            actions=['parse'],
            script_path=script_path, # Load the script to be parsed
            frame_range=frame_range_override # Pass override tuple
        )

        # --- Check Results ---
        if parse_results.get('execution_error') or parse_results.get('load_error'):
             raise ParsingError(f"Nuke execution failed during parsing: {parse_results.get('execution_error') or parse_results.get('load_error')}")

        action_result = parse_results.get('parse', {})
        raw_manifest = action_result.get('dependency_manifest')
        error = action_result.get('error') # Check action specific error

        if error:
            raise ParsingError(f"Nuke action 'parse' reported an error: {error}")
        if raw_manifest is None:
             # Could be an empty script or actual failure
             if len(action_result) == 0 and not error:
                  log.warning(f"Parsing returned no dependencies for script '{script_path}'. Assuming it's empty or has no file nodes.")
                  return {} # Return empty manifest for empty script
             raise ParsingError("Nuke action 'parse' did not return a 'dependency_manifest'.")

        log.info(f"Received raw manifest with {len(raw_manifest)} file references from Nuke.")

        # Post-process the manifest (Validation, Disk Scan for Frame Range)
        processed_manifest = _post_process_manifest(raw_manifest, script_path)

        return processed_manifest

    except ArchiveError as e: # Catch errors from run_nuke_action itself
        raise ParsingError(f"Nuke execution failed during parsing process: {e}") from e
    except Exception as e:
        # Catch any other unexpected errors during parsing or post-processing
        log.exception("Unexpected error during dependency parsing.")
        raise ParsingError(f"Unexpected error parsing dependencies: {e}") from e


def _post_process_manifest(raw_manifest: Dict[str, Any], script_path_context: str) -> Dict[str, Any]:
    """Validates paths and resolves frame ranges in the raw manifest."""
    log.debug("Post-processing dependency manifest...")
    processed = {}
    script_dir = Path(script_path_context).parent # For resolving relative paths if needed

    for manifest_key, data in raw_manifest.items(): # key is node.knob
        node_name = data.get("node_name")
        eval_path = data.get("evaluated_path")

        # Basic check for essential data
        if not eval_path or not node_name:
            log.warning(f"Manifest entry '{manifest_key}' missing node_name or evaluated_path. Skipping.")
            continue

        # --- Path Normalization & Resolution ---
        try:
            norm_eval_path = utils.normalize_path(eval_path) # Ensure forward slashes

            # Double-check if path is absolute (Nuke should handle this, but verify)
            if not Path(norm_eval_path).is_absolute():
                 resolved_path = str(script_dir / norm_eval_path)
                 log.warning(f"Path '{norm_eval_path}' from Nuke was not absolute. Resolved relative to script '{script_path_context}': {resolved_path}")
                 norm_eval_path = utils.normalize_path(resolved_path)

            data["evaluated_path"] = norm_eval_path # Update with potentially resolved path
        except Exception as path_e:
             log.error(f"Error processing path '{eval_path}' for {manifest_key}: {path_e}")
             data["validation_error"] = f"Path processing error: {path_e}"
             processed[manifest_key] = data # Store entry with error
             continue # Skip further processing for this entry

        # --- Validation ---
        is_seq = data.get("is_sequence", False)
        # Start with any evaluation error reported by Nuke
        data["validation_error"] = data.get("evaluation_error")

        # Basic existence check
        path_to_validate_obj = Path(norm_eval_path)
        # For sequences, check the directory; for files, check the file itself.
        check_target_exists = path_to_validate_obj.parent.is_dir() if is_seq else path_to_validate_obj.is_file()

        if not check_target_exists:
            error_msg = f"{'Sequence directory' if is_seq else 'File'} not found at expected location: {path_to_validate_obj.parent if is_seq else path_to_validate_obj}"
            log.warning(f"{error_msg} (Source: {manifest_key})")
            # Append error or set if new
            current_error = data.get("validation_error")
            data["validation_error"] = f"{current_error} {error_msg}".strip() if current_error else error_msg
            # Don't skip yet, allow archiver to decide based on error status

        # --- Frame Range Resolution (if needed and path seems valid) ---
        # Only scan if sequence, source is 'scan_required', and basic validation passed
        if is_seq and data.get("frame_range_source") == "scan_required" and not data.get("validation_error"):
            log.debug(f"Attempting disk scan for frame range: {norm_eval_path}")
            try:
                disk_range = utils.find_sequence_range_on_disk(norm_eval_path)
                if disk_range:
                    data["first_frame"], data["last_frame"] = disk_range
                    data["frame_range_source"] = "disk_scan"
                    log.info(f"Found frame range via disk scan for {manifest_key}: {disk_range}")
                else:
                    log.warning(f"Could not determine frame range via disk scan: {norm_eval_path} (Source: {manifest_key})")
                    err_msg = "Could not determine frame range from disk."
                    current_error = data.get("validation_error")
                    data["validation_error"] = f"{current_error} {err_msg}".strip() if current_error else err_msg
            except Exception as scan_e:
                 log.error(f"Error during disk scan for {manifest_key}: {scan_e}")
                 err_msg = f"Error scanning disk for frame range: {scan_e}"
                 current_error = data.get("validation_error")
                 data["validation_error"] = f"{current_error} {err_msg}".strip() if current_error else err_msg


        processed[manifest_key] = data

    log.info(f"Manifest post-processing complete. Processed {len(processed)} entries.")
    return processed