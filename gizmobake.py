"""
Handles baking of non-native Gizmos by calling the Nuke operation.
"""
import tempfile
from pathlib import Path
import os
from typing import Optional, Tuple

from . import log, utils
from .exceptions import GizmoError, ArchiveError # Make sure ArchiveError is imported

def bake_gizmos_in_script(script_path: str, dry_run: bool = False) -> str:
    """
    Uses nuke_ops.py to attempt baking non-native gizmos in a script.

    Args:
        script_path: Path to the input .nk script (e.g., the pruned script).
        dry_run: If True, simulates the process.

    Returns:
        Path to the new script with baked gizmos (can be a temporary path),
        or the original script_path if no baking occurred, dry_run=True, or an error happened during Nuke execution
        but wasn't critical enough to halt the overall process (e.g., failure to save baked script).

    Raises:
        GizmoError: If a critical error occurs preventing baking (e.g., cannot create temp file, Nuke process crashes hard).
    """
    log.info(f"Requesting gizmo baking for script: {script_path}")
    # Validate input script exists before proceeding
    try:
        utils.validate_path_exists(script_path, "Nuke script for baking")
    except DependencyError as e:
        raise GizmoError(f"Input script for baking not found: {e}") from e

    if dry_run:
        log.info("[DRY RUN] Gizmo baking step simulated.")
        return script_path # Return original path, indicating no change in dry run

    # Prepare a temporary output path for Nuke to save the baked script *if* baking occurs
    temp_baked_path = None
    try:
        fd, temp_baked_path = tempfile.mkstemp(suffix="_baked.nk", prefix="fixarc_", text=True)
        os.close(fd) # Close descriptor, Nuke will handle writing
        log.debug(f"Generated temporary path for potential baked script: {temp_baked_path}")
    except Exception as e:
         # Critical error if we can't even create a temp file path
         raise GizmoError(f"Failed to create temporary file path for baked script: {e}") from e

    try:
        # Action: Bake Gizmos via Nuke
        log.debug("Running Nuke action: bake")
        bake_results = utils.run_nuke_action(
            actions=['bake'],
            script_path=script_path, # Load the input script
            output_path=temp_baked_path # Tell Nuke where to save *if* baking happens
        )

        # --- Process Results ---
        # Check for critical execution errors first
        if bake_results.get('execution_error') or bake_results.get('load_error'):
            raise GizmoError(f"Nuke execution failed during baking process: {bake_results.get('execution_error') or bake_results.get('load_error')}")

        action_result = bake_results.get('bake', {})
        baked_script_path_from_nuke = action_result.get('baked_script_path')
        baked_count = action_result.get('baked_count', 0)
        error = action_result.get('error') # Specific error reported by bake action

        if error:
            # An error occurred *within* the Nuke baking logic (e.g., couldn't save file)
            log.error(f"Nuke action 'bake' reported an error: {error}")
            # Clean up the potentially unused/failed temp file
            if Path(temp_baked_path).exists():
                 try: os.remove(temp_baked_path)
                 except OSError: log.warning(f"Could not remove temp file after bake error: {temp_baked_path}")
            # Return original path - baking failed, proceed without it
            return script_path

        if baked_count > 0:
            # Baking occurred
            if baked_script_path_from_nuke and Path(baked_script_path_from_nuke).exists():
                 # Nuke reported saving, and file exists
                 log.info(f"Gizmo baking successful ({baked_count} baked). Using temporary baked script: {baked_script_path_from_nuke}")
                 # Verify it saved where expected
                 if baked_script_path_from_nuke != temp_baked_path:
                      log.warning(f"Nuke saved baked script to '{baked_script_path_from_nuke}', differs from expected temp path '{temp_baked_path}'. Using Nuke's path.")
                      # Clean up original temp placeholder if it somehow still exists
                      if Path(temp_baked_path).exists():
                           try: os.remove(temp_baked_path)
                           except OSError: pass
                      return baked_script_path_from_nuke # Return the path Nuke used
                 return temp_baked_path # Return the expected temp path
            else:
                 # Nuke reported baking but file is missing - treat as error
                 log.error(f"Nuke reported baking {baked_count} gizmos but output file '{baked_script_path_from_nuke or temp_baked_path}' is missing or invalid.")
                 if Path(temp_baked_path).exists(): os.remove(temp_baked_path)
                 # Return original path, baking effectively failed
                 return script_path
        else:
            # No baking occurred (baked_count == 0)
            log.info("No non-native gizmos required baking.")
            # Clean up the unused temporary file
            if Path(temp_baked_path).exists():
                 try: os.remove(temp_baked_path)
                 except OSError: log.warning(f"Could not remove unused temp bake file: {temp_baked_path}")
            return script_path # Return the original path

    except ArchiveError as e: # Catch specific errors from run_nuke_action
        log.error(f"Nuke execution failed during baking request: {e}")
        # Clean up temp file if it exists
        if temp_baked_path and Path(temp_baked_path).exists():
            try: os.remove(temp_baked_path)
            except OSError: log.warning(f"Could not remove temp file after Nuke execution error: {temp_baked_path}")
        # Return original path - treat as non-critical failure for baking step? Or raise?
        # Let's return original path, allowing process to potentially continue without baked script.
        return script_path
    except Exception as e:
        # Catch unexpected errors
        log.exception("Unexpected error during gizmo baking process.")
        if temp_baked_path and Path(temp_baked_path).exists():
            try: os.remove(temp_baked_path)
            except OSError: log.warning(f"Could not remove temp file after unexpected error: {temp_baked_path}")
        # Treat unexpected errors as potentially critical? Raise GizmoError.
        raise GizmoError(f"Unexpected error during baking: {e}") from e