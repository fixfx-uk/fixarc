"""
Handles the script pruning process.
"""
import tempfile
from pathlib import Path
import os
from typing import List # Add import

from . import log, utils
# Ensure PruningError is defined in exceptions.py
from .exceptions import PruningError, ArchiveError

def find_nodes_to_keep(script_path: str) -> List[str]:
    """
    Determines the list of nodes required for final writes by calling Nuke operations.

    Args:
        script_path: Path to the original Nuke script.

    Returns:
        List of fully qualified node names to keep (including dependencies and associated backdrops).

    Raises:
        PruningError: If write nodes cannot be found or dependency tracing fails via Nuke.
    """
    log.info(f"Identifying target write nodes and dependencies in: {script_path}")
    try:
        # Action 1: Get Write Nodes
        log.debug("Running Nuke action: get_writes")
        write_results = utils.run_nuke_action(actions=['get_writes'], script_path=script_path)

        # Robust error checking
        if write_results.get('execution_error') or write_results.get('load_error'):
            raise PruningError(f"Nuke execution failed while getting writes: {write_results.get('execution_error') or write_results.get('load_error')}")
        action_result = write_results.get('get_writes', {})
        if action_result.get('error'):
            raise PruningError(f"Nuke action 'get_writes' failed: {action_result['error']}")

        target_writes = action_result.get('write_nodes', [])

        if not target_writes:
            raise PruningError("No valid Write or WriteFix nodes found in the script to target for pruning.")
        log.info(f"Found target write nodes: {target_writes}")

        # Action 2: Get Dependencies for these writes
        log.debug("Running Nuke action: get_deps")
        dep_results = utils.run_nuke_action(actions=['get_deps'], script_path=script_path, target_nodes=target_writes)

        if dep_results.get('execution_error') or dep_results.get('load_error'):
             raise PruningError(f"Nuke execution failed while getting dependencies: {dep_results.get('execution_error') or dep_results.get('load_error')}")
        action_result = dep_results.get('get_deps', {})
        if action_result.get('error'):
             raise PruningError(f"Nuke action 'get_deps' failed: {action_result['error']}")

        dependent_nodes = action_result.get('dependent_nodes', [])

        if not dependent_nodes:
             log.warning("Dependency tracing returned no nodes (should include targets). Using target writes only.")
             dependent_nodes = target_writes

        log.info(f"Identified {len(dependent_nodes)} dependent nodes for pruning.")

        # Action 3: Get Associated Backdrops
        log.debug("Running Nuke action: get_backdrops")
        backdrop_results = utils.run_nuke_action(actions=['get_backdrops'], script_path=script_path, target_nodes=dependent_nodes)

        associated_backdrops = [] # Default to empty list
        if backdrop_results.get('execution_error') or backdrop_results.get('load_error'):
             log.warning(f"Nuke execution failed while getting backdrops: {backdrop_results.get('execution_error') or backdrop_results.get('load_error')}")
        else:
             action_result = backdrop_results.get('get_backdrops', {})
             if action_result.get('error'):
                  log.warning(f"Nuke action 'get_backdrops' failed: {action_result['error']}")
             else:
                  associated_backdrops = action_result.get('backdrops', [])
                  if associated_backdrops:
                       log.info(f"Identified {len(associated_backdrops)} associated backdrops.")

        # Combine dependencies and backdrops, ensure uniqueness
        nodes_to_keep = sorted(list(set(dependent_nodes + associated_backdrops)))
        log.info(f"Total nodes identified to keep: {len(nodes_to_keep)}")
        return nodes_to_keep

    except ArchiveError as e: # Catch errors from run_nuke_action specifically
        raise PruningError(f"Nuke execution failed during node identification: {e}") from e
    except Exception as e:
        # Catch any other unexpected errors
        log.exception("Unexpected error during node identification.")
        raise PruningError(f"Unexpected error identifying nodes to keep: {e}") from e


def save_pruned_script(script_path: str, nodes_to_keep: List[str]) -> str:
    """
    Calls Nuke operation to save a new script containing only specified nodes to a temporary location.

    Args:
        script_path: Path to the *original* Nuke script (needed for Nuke context).
        nodes_to_keep: List of fully qualified node names to include.

    Returns:
        Path to the temporary pruned script file.

    Raises:
        PruningError: If saving the pruned script fails.
    """
    log.info(f"Requesting Nuke to save pruned script (keeping {len(nodes_to_keep)} nodes)...")

    temp_pruned_path = None
    try:
        # Use mkstemp for unique temporary file name generation
        fd, temp_pruned_path = tempfile.mkstemp(suffix="_pruned.nk", prefix="fixarc_", text=True)
        os.close(fd) # Close descriptor, we just need the path name
        log.debug(f"Generated temporary path for pruned script: {temp_pruned_path}")
    except Exception as e:
         raise PruningError(f"Failed to create temporary file path for pruned script: {e}") from e

    try:
        # Action: Save Pruned Script via Nuke
        log.debug("Running Nuke action: save_pruned")
        save_results = utils.run_nuke_action(
            actions=['save_pruned'],
            script_path=script_path, # Load original script context first
            target_nodes=nodes_to_keep,
            output_path=temp_pruned_path # Tell Nuke where to save the pruned result
        )

        # --- Check Results ---
        if save_results.get('execution_error') or save_results.get('load_error'):
             raise PruningError(f"Nuke execution failed while saving pruned script: {save_results.get('execution_error') or save_results.get('load_error')}")

        action_result = save_results.get('save_pruned', {})
        saved_path = action_result.get('saved_path')
        error = action_result.get('error')

        # Verify outcome
        if error or not saved_path:
             raise PruningError(f"Nuke action 'save_pruned' failed: {error or 'No saved path returned'}")
        if not Path(saved_path).exists():
             raise PruningError(f"Nuke action 'save_pruned' reported success, but output file '{saved_path}' not found.")
        if Path(saved_path).stat().st_size == 0:
             raise PruningError(f"Nuke action 'save_pruned' created an empty output file: '{saved_path}'")

        log.info(f"Successfully saved pruned script to temporary location: {saved_path}")

        # Return the path Nuke confirmed it saved to
        return saved_path

    except (ArchiveError, PruningError) as e: # Catch specific errors first
        # Clean up temp file if save failed critically
        if temp_pruned_path and Path(temp_pruned_path).exists():
            try: os.remove(temp_pruned_path)
            except OSError: log.warning(f"Could not remove temp file after error: {temp_pruned_path}")
        raise # Re-raise the caught error
    except Exception as e:
        log.exception("Unexpected error saving pruned script.")
        if temp_pruned_path and Path(temp_pruned_path).exists():
            try: os.remove(temp_pruned_path)
            except OSError: log.warning(f"Could not remove temp file after unexpected error: {temp_pruned_path}")
        raise PruningError(f"Unexpected error saving pruned script: {e}") from e