# fixarc/_nuke_executor.py
"""
Core Nuke script executed via `nuke -t` by the fixarc tool.

Performs loading, pruning, dependency collection, baking, repathing, and saving
within a single Nuke session based on command-line arguments.

Outputs results and dependency information as JSON to stdout.
"""

# --- IMPORTANT ---
# This script runs entirely within the Nuke environment.
# It should only import standard Python libraries and the 'nuke' module.
# Do NOT import other modules from the 'fixarc' package directly here.
# All necessary data is passed via command-line arguments.
# All results are returned via JSON printed to stdout.
# --- ----------- ---

import nuke
import os
import sys
import json
import traceback
import argparse
from pathlib import Path # Use pathlib for path manipulation within Nuke
from typing import Dict, List, Set, Optional, Tuple, Any # Use standard typing
import tempfile
import logging
import re # Added for regex matching

# Set up logging to stderr for the wrapper to capture
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s [%(levelname)s] %(message)s',
                    stream=sys.stderr)
log = logging.getLogger(__name__)

def log_nuke_path_on_load():
    """Logs the NUKE_PATH environment variable as seen by Nuke."""
    nuke_path = os.environ.get('NUKE_PATH', 'Not Set')
    log.debug(f"NUKE_PATH inside Nuke (onScriptLoad): {nuke_path}")
    
    # Also check for other plugins in the path
    log.debug(f"Nuke plugin path: {nuke.pluginPath()}")
    
    # Check if OCIOColorSpace exists
    try:
        if 'OCIO' in os.environ:
            log.debug(f"OCIO: {os.environ['OCIO']}")
        ocio_plugin = nuke.plugins(nuke.ALL | nuke.NODIR)
        plugin_list = ", ".join(ocio_plugin)
        log.debug(f"Nuke plugins: {plugin_list[:200]}...")
    except Exception as e:
        log.debug(f"Error checking OCIO: {e}")

# Register the callback to run before the script loads
nuke.addOnScriptLoad(log_nuke_path_on_load)

# --- Simple Placeholder Exceptions (Internal) ---
class PruningError(Exception): pass
class ConfigurationError(Exception): pass
class ArchiverError(Exception): pass

# --- Constants (Duplicated for self-containment) ---
WRITE_NODE_CLASSES = frozenset(["Write", "WriteGeo", "DeepWrite"])
READ_NODE_CLASSES = frozenset([
    "Read", "ReadGeo", "ReadGeo2", "DeepRead", "Camera", "Camera2", "Camera3",
    "Axis", "Axis2", "Axis3", "OCIOFileTransform", "Vectorfield",
    "GenerateLUT", "BlinkScript", "ParticleCache", "PointCloudGenerator", "STMap",
])
# Placeholder for category, mirroring simplified mapping logic below
ELEMENTS_REL = 'elements'

# Constants for relative paths
PROJECT_REL = 'project'
SCRIPTS_REL = 'scripts'
NUKE_REL = 'nuke'

# --- Helper Functions (Internal to this script) ---

def _log_print(level: str, message: str) -> None:
    """Simple print-based logging mimic for Nuke environment."""
    # Output format matches basic logger for parsing by main process if needed
    timestamp = traceback.extract_stack()[-2].name # Function name isn't useful here
    print(f"[{level.upper():<7}] [NukeExecutor] {message}")

def _is_valid_writefix(node: nuke.Node) -> bool:
    """Check if a Group node is a WriteFix gizmo excluding 'QuickReview'."""
    if node.Class() != 'Group': return False
    if not node.knob('writefix'): return False # Check for identifying knob
    profile_knob = node.knob('profile')
    if profile_knob and profile_knob.value() == 'QuickReview':
        _log_print("debug", f"Ignoring WriteFix '{node.fullName()}' (QuickReview profile)")
        return False
    return True

# --- Action: Get Write Nodes (Copied and adapted from nuke_ops.py) ---
def get_write_nodes_action() -> Dict[str, List[str]]:
    """
    Finds Write and WriteFix nodes at the root level of the Nuke script only.
    Does not recurse into groups to find nested write nodes.
    """
    writes = []
    # Only search root level nodes (no recurseGroups)
    nodes = nuke.allNodes()
    _log_print("info", f"Checking {len(nodes)} root level nodes for target writes...")
    count = 0
    for node in nodes:
        is_write = False
        node_class = node.Class()
        if node_class in WRITE_NODE_CLASSES:
             is_write = True
        elif _is_valid_writefix(node):
             is_write = True

        if is_write:
            # Check if the write node is disabled
            disable_knob = node.knob('disable')
            if disable_knob and disable_knob.value():
                 _log_print("debug", f"Ignoring disabled write node: {node.fullName()}")
                 continue
            _log_print("debug", f"Found valid write node: {node.fullName()} (Class: {node_class})")
            writes.append(node.fullName())
            count += 1
    _log_print("info", f"Found {count} valid root level write nodes.")
    return {"write_nodes": writes}


def _get_upstream_nodes(target_nodes: List[nuke.Node]) -> Set[nuke.Node]:
    """Traces all upstream dependencies for a list of target nodes."""
    all_deps_set: Set[nuke.Node] = set(target_nodes) # Start with targets
    nodes_to_process: List[nuke.Node] = list(target_nodes)
    processed_nodes: Set[str] = set(n.fullName() for n in target_nodes) # Track by name

    MAX_DEPTH = 5000 # Safety break
    count = 0

    while nodes_to_process and count < MAX_DEPTH:
        count += 1
        current_node = nodes_to_process.pop(0)

        try:
            # Combine input types for broader dependency check
            input_types = nuke.INPUTS | nuke.HIDDEN_INPUTS | nuke.EXPRESSIONS
            dependencies = current_node.dependencies(input_types)

            for dep_node in dependencies:
                if not dep_node: continue
                dep_name = dep_node.fullName()
                if dep_name not in processed_nodes:
                    processed_nodes.add(dep_name)
                    all_deps_set.add(dep_node)
                    nodes_to_process.append(dep_node) # Add to queue
        except Exception as e:
             _log_print("warning", f"Error getting dependencies for '{current_node.fullName()}': {e}")
             # Continue processing other nodes

    if count >= MAX_DEPTH:
        _log_print("warning", f"Dependency trace reached max depth ({MAX_DEPTH}). Results may be incomplete.")

    _log_print("info", f"Dependency trace found {len(all_deps_set)} upstream nodes (including targets).")
    return all_deps_set

def _find_associated_backdrops(nodes_to_check: Set[nuke.Node]) -> Set[nuke.Node]:
    """Finds backdrops containing any of the nodes in the provided set."""
    if not nodes_to_check: return set()

    all_bd_nodes = nuke.allNodes('BackdropNode', recurseGroups=True)
    containing_backdrops: Set[nuke.Node] = set()
    _log_print("debug", f"Checking {len(all_bd_nodes)} backdrops for association...")

    # Pre-calculate node geometries
    node_geoms: Dict[str, Tuple[float, float, float, float]] = {}
    for node in nodes_to_check:
        try:
             # Screen width/height can be 0 right after creation/load? Use defaults.
             nx, ny = node.xpos(), node.ypos()
             nw = node.screenWidth() or 80.0
             nh = node.screenHeight() or 18.0
             node_geoms[node.fullName()] = (nx, ny, nw, nh)
        except ValueError:
             _log_print("warning", f"Could not get geometry for node '{node.fullName()}'")

    for bd in all_bd_nodes:
        try:
            bx, by = bd.xpos(), bd.ypos()
            bw = bd['bdwidth'].value()
            bh = bd['bdheight'].value()
            bl, br, bt, bb = bx, bx + bw, by, by + bh

            # Check if any target node's center is within this backdrop
            for node_name, (nx, ny, nw, nh) in node_geoms.items():
                 node_center_x = nx + nw / 2.0
                 node_center_y = ny + nh / 2.0
                 if bl <= node_center_x < br and bt <= node_center_y < bb:
                     containing_backdrops.add(bd)
                     # _log_print("debug", f"Node '{node_name}' found inside backdrop '{bd.fullName()}'") # Verbose
                     break # Found one node inside, add backdrop and check next backdrop
        except (ValueError, TypeError):
             _log_print("warning", f"Could not get geometry for backdrop '{bd.fullName()}'.")
             continue

    _log_print("info", f"Found {len(containing_backdrops)} associated backdrops.")
    return containing_backdrops

def _collect_dependency_paths(nodes: Set[nuke.Node]) -> Dict[str, Dict[str, Any]]:
    """
    Iterates through nodes and collects evaluated file paths from relevant knobs.
    Returns: {'node_name.knob_name': {'evaluated_path': ..., 'original_path': ...}}
    """
    dependency_paths: Dict[str, Dict[str, Any]] = {}
    _log_print("info", f"Collecting dependency paths from {len(nodes)} nodes...")

    for i, node in enumerate(nodes): # Added index for logging
        node_name = node.fullName()
        node_class = node.Class()
        # _log_print("debug", f"Processing node {i+1}/{len(nodes)}: '{node_name}' (Class: {node_class})") # Log node being processed
        # Define relevant knobs per class or check common ones
        knobs_to_check: Dict[str, nuke.Knob] = {}
        if node_class in READ_NODE_CLASSES | WRITE_NODE_CLASSES: # Check both for file knobs
             knobs_to_check['file'] = node.knob('file')
             knobs_to_check['proxy'] = node.knob('proxy')
             # Add other known file knobs
             if node_class == "OCIOFileTransform": knobs_to_check['cccid'] = node.knob('cccid')
             if node_class == "Vectorfield": knobs_to_check['vfield_file'] = node.knob('vfield_file')
             # ... add more specific knobs ...

        for knob_name, knob in knobs_to_check.items():
            if not knob: continue

            original_path = None
            evaluated_path = None
            error_msg = None
            _log_print("debug", f"  Checking knob: '{knob_name}' on node '{node_name}'") # Log knob being checked
            try:
                original_path = knob.value()
                if not original_path: continue # Skip empty knobs

                evaluated_path = knob.evaluate()
                if not evaluated_path:
                     _log_print("warning", f"Evaluated path for '{node_name}.{knob_name}' is empty. Original: '{original_path}'")
                     continue # Skip empty evaluated paths

                # Resolve relative paths against current script path
                if not os.path.isabs(evaluated_path):
                     script_dir = os.path.dirname(nuke.root().name())
                     evaluated_path = os.path.abspath(os.path.join(script_dir, evaluated_path))

                # Normalize slashes
                evaluated_path = evaluated_path.replace("\\", "/")

            except Exception as e:
                error_msg = f"Error evaluating '{knob_name}' for '{node_name}': {e}"
                _log_print("error", error_msg)

            # Store result even if error occurred during evaluation
            manifest_key = f"{node_name}.{knob_name}"
            dependency_paths[manifest_key] = {
                "original_path": original_path,
                "evaluated_path": evaluated_path, # Store absolute, normalized path
                "error": error_msg
            }
            if error_msg: _log_print("debug", f"Stored entry for {manifest_key} with error.")
            # else: _log_print("debug", f"Stored dependency: {manifest_key} -> {evaluated_path}") # Verbose

    _log_print("info", f"Collected {len(dependency_paths)} potential file dependency paths.")
    return dependency_paths


def _bake_gizmos(nodes_to_check: Set[nuke.Node]) -> Tuple[int, Set[nuke.Node]]:
    """
    Bakes non-native gizmos within the provided set of nodes *in place*.
    Returns the count of baked gizmos and the potentially updated set of nodes
    (replacing gizmos with the groups created).
    """
    _log_print("info", "Starting gizmo baking process...")
    baked_count = 0
    try:
        native_plugins = set(nuke.plugins(nuke.ALL | nuke.NODIR))
        _log_print("debug", f"Using {len(native_plugins)} native plugins for exclusion.")
    except Exception as e:
        _log_print("warning", f"Could not get native plugins list: {e}. Exclusion less accurate.")
        native_plugins = set()

    current_nodes = list(nodes_to_check) # Iterate over a copy
    updated_node_set = set(nodes_to_check) # Set to store final nodes

    processed_for_baking: Set[str] = set()

    for node in current_nodes:
        # Check if node still exists (might have been replaced by baking earlier in loop?)
        # Using node name check is safer than object identity after potential replacement
        if not nuke.exists(node.fullName()) or node.fullName() in processed_for_baking:
            continue

        node_name = node.fullName()
        node_class = node.Class()
        can_be_baked = hasattr(node, 'makeGroup')

        if not can_be_baked: continue

        is_gizmo_file_based = node.knob('gizmo_file') is not None
        is_likely_native = node_class in native_plugins

        # --- Determine if baking is needed ---
        should_bake = False
        if is_gizmo_file_based:
             # Check if it's in standard Nuke plugin paths
             in_nuke_plugins_dir = False
             try:
                  gizmo_filename = node.filename()
                  if gizmo_filename:
                       nuke_install_dir = Path(nuke.env['ExecutablePath']).parent.parent # Go up two levels typically
                       if Path(gizmo_filename).is_relative_to(nuke_install_dir / 'plugins'):
                            in_nuke_plugins_dir = True
             except Exception as path_e:
                  _log_print("warning", f"Error checking path for gizmo {node_name}: {path_e}")

             if not in_nuke_plugins_dir:
                  should_bake = True
        # Decide if non-file-based, non-native nodes should be baked (risky)
        # elif not is_likely_native:
        #      _log_print("warning", f"Node {node_name} ({node_class}) is non-native but not file-based. Baking not attempted.")

        # --- Perform Bake ---
        if should_bake:
             _log_print("info", f"Baking gizmo: {node_name} (Class: {node_class})")
             try:
                  # Deselect all, select target? Safer without selection changes? Try without first.
                  # for n in nuke.allNodes(recurseGroups=True): n.setSelected(False)
                  # node.setSelected(True)
                  baked_group = node.makeGroup() # Perform the bake

                  if baked_group:
                      baked_name = baked_group.fullName()
                      _log_print("info", f"Successfully baked '{node_name}' to Group '{baked_name}'")
                      baked_count += 1
                      # Update the working set: remove original node, add baked group
                      updated_node_set.discard(node) # Remove original node object
                      updated_node_set.add(baked_group) # Add the new group object
                      processed_for_baking.add(node_name) # Mark original name as processed
                      processed_for_baking.add(baked_name) # Mark new group as processed (don't try to bake it)
                  else:
                      _log_print("warning", f"Failed to bake gizmo '{node_name}'. makeGroup() returned None.")
                      processed_for_baking.add(node_name) # Mark as processed even if failed

             except Exception as bake_error:
                  _log_print("error", f"Error baking gizmo '{node_name}': {bake_error}\n{traceback.format_exc()}")
                  processed_for_baking.add(node_name) # Mark as processed even on error

    _log_print("info", f"Gizmo baking finished. Baked {baked_count} gizmos.")
    return baked_count, updated_node_set


def _calculate_relative_path_nuke(source_script_abs: str, target_dependency_abs: str) -> str:
    """Calculates relative path within Nuke env, falling back to absolute."""
    try:
        norm_script_path = Path(str(source_script_abs).replace("\\", "/"))
        norm_target_path = Path(str(target_dependency_abs).replace("\\", "/"))
        source_dir = norm_script_path.parent
        # Use os.path.relpath for cross-drive compatibility if needed
        relative = os.path.relpath(norm_target_path, source_dir)
        nuke_relative_path = relative.replace("\\", "/")
        _log_print("debug", f"Calculated relative path: '{nuke_relative_path}' (from '{source_dir}' to '{norm_target_path}')")
        return nuke_relative_path
    except ValueError as e: # Handles different drives on Windows
        abs_target_nuke = str(target_dependency_abs).replace("\\", "/")
        _log_print("warning", f"Could not make relative path ('{source_script_abs}' -> '{target_dependency_abs}'): {e}. Using absolute: {abs_target_nuke}")
        return abs_target_nuke
    except Exception as e:
        abs_target_nuke = str(target_dependency_abs).replace("\\", "/")
        _log_print("error", f"Unexpected error calculating relative path ('{source_script_abs}' -> '{target_dependency_abs}'): {e}. Using absolute: {abs_target_nuke}")
        return abs_target_nuke


def _repath_nodes(
    nodes_to_repath: Set[nuke.Node],
    dependency_map: Dict[str, str], # {original_evaluated_abs: final_archived_abs}
    final_script_archive_path: str
) -> int:
    """
    Repaths file knobs within the given set of nodes *in memory*.
    Uses relative paths calculated against the final script destination.
    Returns the number of successful repath operations.
    """
    _log_print("info", f"Starting repathing process for {len(nodes_to_repath)} nodes...")
    repath_count = 0
    failed_repaths: List[str] = []

    # Create a reverse map for faster lookup if needed, but iterating nodes is likely clearer
    # archived_to_original = {v: k for k, v in dependency_map.items() if v}

    for node in nodes_to_repath:
        node_name = node.fullName()
        node_class = node.Class()
        knobs_to_check = {}
        # Identify potential file knobs on this node
        if node_class in READ_NODE_CLASSES | WRITE_NODE_CLASSES:
             knobs_to_check['file'] = node.knob('file')
             knobs_to_check['proxy'] = node.knob('proxy')
             if node_class == "OCIOFileTransform": knobs_to_check['cccid'] = node.knob('cccid')
             if node_class == "Vectorfield": knobs_to_check['vfield_file'] = node.knob('vfield_file')
             # Add more knobs as needed

        for knob_name, knob in knobs_to_check.items():
            if not knob: continue

            current_eval_path = None
            try:
                current_eval_path_raw = knob.evaluate()
                if not current_eval_path_raw: continue # Skip empty knobs

                # Resolve if relative and normalize
                if not os.path.isabs(current_eval_path_raw):
                     script_dir = os.path.dirname(nuke.root().name())
                     current_eval_path = os.path.abspath(os.path.join(script_dir, current_eval_path_raw))
                else:
                     current_eval_path = current_eval_path_raw
                current_eval_path = current_eval_path.replace("\\", "/")

                # Check if this evaluated path is one we archived
                if current_eval_path in dependency_map:
                    final_archived_path = dependency_map[current_eval_path]
                    if final_archived_path: # Ensure it was successfully mapped/archived
                        # Calculate the new relative path
                        relative_path = _calculate_relative_path_nuke(final_script_archive_path, final_archived_path)
                        # Set the knob value *in memory*
                        knob.setValue(relative_path)
                        _log_print("debug", f"Repathed '{node_name}.{knob_name}': '{current_eval_path}' -> '{relative_path}'")
                        repath_count += 1
                    else:
                        # Path was in manifest but failed archiving - don't repath
                        _log_print("warning", f"Skipping repath for '{node_name}.{knob_name}': Original path '{current_eval_path}' failed archiving.")
                        failed_repaths.append(f"{node_name}.{knob_name} (archive failed)")
                # else: # Path not in our map, leave it alone
                     # _log_print("debug", f"Path '{current_eval_path}' not in archive map for {node_name}.{knob_name}. Skipping repath.")

            except Exception as e:
                 _log_print("error", f"Error during repathing '{node_name}.{knob_name}' (Path: {current_eval_path}): {e}")
                 failed_repaths.append(f"{node_name}.{knob_name} (error: {e})")

    _log_print("info", f"Repathing finished. Set {repath_count} knob values.")
    if failed_repaths:
         _log_print("warning", f"Encountered {len(failed_repaths)} issues during repathing. Check logs.")
    return repath_count

# --- Main Executor Function and Task-Specific Functions ---

def load_input_script(script_path: str) -> None:
    """
    Loads the input Nuke script.
    """
    _log_print("info", f"Loading input script: {script_path}")
    nuke.scriptClear()
    nuke.scriptOpen(script_path)
    _log_print("info", "Input script loaded successfully.")

def identify_target_writes() -> List[nuke.Node]:
    """
    Identifies target write nodes in the script.
    Returns a list of target write nodes.
    """
    _log_print("info", "Identifying target write nodes...")
    write_node_names = get_write_nodes_action().get("write_nodes", [])
    if not write_node_names:
        raise PruningError("No valid Write/WriteFix nodes found to initiate pruning.")
    
    target_write_nodes = [nuke.toNode(name) for name in write_node_names if nuke.toNode(name)]
    _log_print("info", f"Found {len(target_write_nodes)} target write nodes for dependency tracing.")
    return target_write_nodes

def trace_node_dependencies(target_nodes: List[nuke.Node]) -> Set[nuke.Node]:
    """
    Traces dependencies for the given target nodes.
    Returns a set of required compute nodes.
    """
    _log_print("info", "Tracing node dependencies...")
    required_compute_nodes = _get_upstream_nodes(target_nodes)
    return required_compute_nodes

def find_backdrop_nodes(compute_nodes: Set[nuke.Node]) -> Set[nuke.Node]:
    """
    Finds backdrop nodes associated with the given compute nodes.
    Returns a set of associated backdrop nodes.
    """
    _log_print("info", "Finding associated backdrops...")
    return _find_associated_backdrops(compute_nodes)

def collect_required_nodes(compute_nodes: Set[nuke.Node], backdrop_nodes: Set[nuke.Node]) -> Tuple[Set[nuke.Node], List[str]]:
    """
    Combines compute nodes and backdrop nodes to get the final set of required nodes.
    Returns the combined set and a sorted list of node names.
    """
    required_nodes = compute_nodes.union(backdrop_nodes)
    required_node_names = sorted([n.fullName() for n in required_nodes])
    _log_print("info", f"Total nodes required (including backdrops): {len(required_nodes)}")
    return required_nodes, required_node_names

def collect_dependency_paths_from_nodes(nodes: Set[nuke.Node]) -> Dict[str, Dict[str, Any]]:
    """
    Collects file dependencies from the given nodes.
    Returns a dictionary of dependency information.
    """
    _log_print("info", "Collecting dependency file paths from required nodes...")
    return _collect_dependency_paths(nodes)

def process_gizmo_baking(nodes: Set[nuke.Node], should_bake: bool) -> Tuple[int, Set[nuke.Node]]:
    """
    Bakes gizmos if requested.
    Returns the count of baked gizmos and the potentially updated set of nodes.
    """
    baked_count = 0
    if should_bake:
        _log_print("info", "--- Starting Optional Step: Bake Gizmos ---")
        baked_count, nodes = _bake_gizmos(nodes)
        _log_print("info", "--- Finished Optional Step: Bake Gizmos ---")
    else:
        _log_print("info", "Skipping gizmo baking.")
    
    return baked_count, nodes

def repath_script_knobs(
    nodes: Set[nuke.Node], 
    dependency_info: Dict[str, Dict[str, Any]],
    should_repath: bool,
    archive_root: str,
    final_script_path: str,
    metadata_json: str
) -> Tuple[Dict[str, str], int]:
    """
    Repaths script knobs if requested.
    Returns the dependency map for repathing and the count of repathed knobs.
    """
    dependency_map_for_repath: Dict[str, str] = {}
    repath_count = 0
    
    if not should_repath:
        _log_print("info", "Skipping script repathing.")
        return dependency_map_for_repath, repath_count
        
    _log_print("info", "--- Starting Optional Step: Repath Script ---")
    if not final_script_path:
        raise ConfigurationError("Final script archive path is required for repathing.")
    if not archive_root:
        raise ConfigurationError("Archive root path is required for repathing.")

    # For each dependency path collected earlier, calculate its final destination.
    _log_print("debug", "Calculating final archive paths for repathing...")
    temp_metadata = json.loads(metadata_json)
    
    # First process each dependency to map to archive destination
    for node_knob, data in dependency_info.items():
        orig_eval = data.get("evaluated_path")
        if orig_eval and not data.get("error"):  # Only map valid, evaluated paths
            # Simulate mapping using standard SPT structure
            try:
                # Use consistent approach for all file paths
                filename = Path(orig_eval).name
                # Use elements as default category
                category = ELEMENTS_REL
                # Construct standard path
                base = Path(archive_root) / temp_metadata['vendor'] / temp_metadata['show']
                base /= temp_metadata['episode'] / temp_metadata['shot']
                dest_path = base / category / filename
                
                # Store with normalized paths
                dependency_map_for_repath[orig_eval] = str(dest_path).replace("\\","/")
                _log_print("debug", f"Mapped '{orig_eval}' → '{dependency_map_for_repath[orig_eval]}'")
            except Exception as map_e:
                _log_print("error", f"Could not calculate destination for repathing '{orig_eval}': {map_e}")

    # Now repath the knobs in memory
    repath_count = _repath_nodes(nodes, dependency_map_for_repath, final_script_path)
    _log_print("info", f"--- Finished Optional Step: Repath Script ({repath_count} paths updated) ---")
    
    return dependency_map_for_repath, repath_count

def save_pruned_script(nodes: Set[nuke.Node], final_script_path: str, archive_root: str) -> str:
    """
    Saves a new Nuke script containing only the specified nodes while retaining
    the original script's Root settings like format, frame range, and color settings.

    Args:
        nodes: A set of nuke.Node instances to keep.
        final_script_path: Path where the new script should be saved.
        archive_root: Root directory for the archive, used for temp file storage.

    Returns:
        Path to the saved .nk file.
    """
    _log_print("info", "Starting pruned script save process.")

    if not final_script_path:
        raise ConfigurationError("Final script archive path is required.")
    
    if not archive_root:
        raise ConfigurationError("Archive root is required.")
    
    # Backup Root node settings
    root_data = nuke.root().writeKnobs(nuke.WRITE_ALL | nuke.TO_SCRIPT)
    _log_print("debug", "Root settings serialized successfully")

    # Deselect all and select only target nodes
    for n in nuke.allNodes(recurseGroups=True):
        n.setSelected(False)

    final_node_names = [n.fullName() for n in nodes if nuke.exists(n.fullName())]
    nodes_selected_count = 0
    missing_final_nodes = []
    for name in final_node_names:
        node = nuke.toNode(name)
        if node:
            try:
                node.setSelected(True)
                nodes_selected_count += 1
            except Exception as sel_e:
                _log_print("warning", f"Could not select final node '{name}': {sel_e}")
        else:
            _log_print("warning", f"Required node '{name}' not found in final state before saving.")
            missing_final_nodes.append(name)

    if nodes_selected_count == 0:
        raise PruningError("No nodes were selected for saving. Pruning or baking might have removed everything.")

    _log_print("info", f"Selected {nodes_selected_count} final nodes for saving.")
    if missing_final_nodes:
        _log_print("warning", f"Missing {len(missing_final_nodes)} required nodes in final state.")

    # Create a custom temp directory under archive_root
    temp_nodes_file = None
    try:
        # Create .tmp directory under archive_root if it doesn't exist
        temp_dir = os.path.join(archive_root, ".tmp")
        os.makedirs(temp_dir, exist_ok=True)
        _log_print("debug", f"Using custom temp directory: {temp_dir}")
        
        # Generate a unique filename for the temp file
        import uuid
        temp_filename = f"nodes_{uuid.uuid4().hex}.nk"
        temp_nodes_file = os.path.join(temp_dir, temp_filename)
        
        # Copy selected nodes to temp file
        _log_print("debug", f"Saving selected nodes to custom temp file: {temp_nodes_file}")
        nuke.nodeCopy(temp_nodes_file)
        
        # Clear and rebuild
        nuke.scriptClear()
        
        # Restore root settings
        try:
            nuke.root().readKnobs(root_data)
            _log_print("debug", "Root settings restored successfully")
        except Exception as e:
            _log_print("warning", f"Failed to fully restore root settings: {e}")
        
        # Paste nodes from temp file
        if os.path.exists(temp_nodes_file) and os.path.getsize(temp_nodes_file) > 0:
            _log_print("debug", "Pasting nodes from custom temp file")
            nuke.nodePaste(temp_nodes_file)
        else:
            raise PruningError(f"Failed to save nodes to custom temp file: {temp_nodes_file}")
            
        # Ensure output directory exists
        final_script_dir = os.path.dirname(final_script_path)
        if final_script_dir:
            os.makedirs(final_script_dir, exist_ok=True)
            _log_print("info", f"Ensured final script directory exists: {final_script_dir}")
        
        # Save the script
        nuke.scriptSaveAs(filename=final_script_path, overwrite=1)
        
        # Final verification
        if not os.path.exists(final_script_path) or os.path.getsize(final_script_path) == 0:
            raise ArchiverError(f"Final save failed: Output file '{final_script_path}' is missing or empty.")
        
        _log_print("info", "Final script saved successfully.")
        return final_script_path
        
    finally:
        # Clean up temporary file
        if temp_nodes_file and os.path.exists(temp_nodes_file):
            try:
                os.remove(temp_nodes_file)
                _log_print("debug", f"Removed custom temp file: {temp_nodes_file}")
            except Exception as e:
                _log_print("warning", f"Failed to remove custom temp file {temp_nodes_file}: {e}")

def generate_dependency_map(dependency_info: Dict[str, Dict[str, Any]], archive_root: str, metadata_json: str) -> Dict[str, str]:
    """
    Generates the final dependency map for copying files.
    Constructs archive paths preserving relative structure after the shot folder.
    """
    dependencies_to_copy = {}
    _log_print("debug", "Generating final dependency map for copying...")
    temp_metadata = json.loads(metadata_json)
    # Construct the expected shot code pattern (e.g., BOB_101_00X_010_WIG)
    # Use metadata which should be reliable
    shot_code_parts = [
        temp_metadata.get('episode'),
        temp_metadata.get('sequence'),
        temp_metadata.get('shot'),
        temp_metadata.get('tag') # Assuming 'tag' is part of the shot code dir name
    ]
    if not all(shot_code_parts[:3]): # Episode, Sequence, Shot are essential
        _log_print("error", "Cannot construct shot code: Missing episode, sequence, or shot in metadata.")
        return {}
        
    # Filter out None or empty parts before joining
    shot_code = '_'.join(filter(None, shot_code_parts)) 
    _log_print("debug", f"Constructed shot code for path splitting: {shot_code}")

    # Regex for the Comp/work/user/images pattern
    comp_work_images_re = re.compile(r"Comp/work/[^/]+/images/(.*)", re.IGNORECASE)

    # Base archive path construction (common part)
    try:
        archive_root_str = str(archive_root)
        vendor_str = str(temp_metadata['vendor'])
        show_str = str(temp_metadata['show'])
        episode_str = str(temp_metadata['episode'])
        shot_str = str(temp_metadata['shot']) # Using the short shot number here
        
        # Build the base path using Path objects (VENDOR/SHOW/EPISODE/SHOT)
        base_archive_path = Path(archive_root_str) / vendor_str / show_str / episode_str / shot_str / ELEMENTS_REL
    except KeyError as ke:
         _log_print("error", f"Cannot build base archive path: Missing metadata key '{ke}'. Metadata: {temp_metadata}")
         return {}
    except Exception as base_path_e:
         _log_print("error", f"Error building base archive path: {base_path_e}")
         return {}
         
    _log_print("debug", f"Base archive path for elements: {base_archive_path}")

    for node_knob, data in dependency_info.items():
        original_path = data.get("original_path")
        if not original_path or data.get("error"):
            _log_print("debug", f"Skipping mapping for {node_knob}: No original path or error encountered.")
            continue

        try:
            # Normalize the original path first
            normalized_original_path = original_path.replace("\\\\", "/")
            original_path_obj = Path(normalized_original_path)

            # Find the relative path after the shot_code directory
            path_parts = normalized_original_path.split('/')
            relative_elements_path_str = None

            try:
                 # Find the index of the directory matching the constructed shot_code
                 shot_code_index = -1
                 for i, part in enumerate(path_parts):
                     if part == shot_code:
                          shot_code_index = i
                          break
                          
                 if shot_code_index != -1 and shot_code_index < len(path_parts) - 1:
                     # Join the parts *after* the shot_code directory
                     relative_elements_path_str = "/".join(path_parts[shot_code_index + 1:])
                 else:
                      # Fallback: Use the full filename if shot_code not found or is the last element
                      _log_print("warning", f"Shot code '{shot_code}' not found correctly in path '{normalized_original_path}'. Falling back to filename only.")
                      relative_elements_path_str = original_path_obj.name
                      
            except ValueError:
                 _log_print("warning", f"Could not split path based on shot code '{shot_code}' for: {normalized_original_path}. Falling back to filename.")
                 relative_elements_path_str = original_path_obj.name


            if not relative_elements_path_str:
                 _log_print("warning", f"Could not determine relative element path for: {normalized_original_path}")
                 continue

            # Apply the Comp/work/images rule
            comp_match = comp_work_images_re.match(relative_elements_path_str)
            if comp_match:
                _log_print("debug", f"Applying Comp/work/images rule to: {relative_elements_path_str}")
                relative_elements_path_str = comp_match.group(1) # Get the part after images/
                _log_print("debug", f"Resulting relative path after rule: {relative_elements_path_str}")


            # Construct the final destination path
            # Ensure the relative part doesn't start with / if base_archive_path handled it
            final_relative_part = relative_elements_path_str.lstrip('/') 
            dest_path = base_archive_path / final_relative_part

            # Convert final path to string with forward slashes
            dest_path_str = str(dest_path).replace("\\\\", "/")

            dependencies_to_copy[normalized_original_path] = dest_path_str
            _log_print("debug", f"Mapped dependency: {normalized_original_path} -> {dest_path_str}")

        except Exception as map_e:
            _log_print("error", f"Could not calculate destination for copying '{normalized_original_path}': {map_e}")
            _log_print("debug", f"Exception details: {traceback.format_exc()}")

    return dependencies_to_copy

def run_nuke_tasks(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Performs the core Nuke logic: load, prune, collect deps, bake, repath, save.
    """
    results: Dict[str, Any] = {"status": "failure"}  # Default status
    errors = []
    _log_print("info", "--- Starting Nuke Task Execution ---") # Start Task Log
    # Log relevant environment variables
    _log_print("debug", f"NUKE_PATH env: {os.environ.get('NUKE_PATH', 'Not Set')}")

    try:
        # 1. Load Input Script
        _log_print("info", "Step 1: Loading Input Script...")
        load_input_script(args.input_script_path)
        _log_print("info", "Step 1: Load Input Script COMPLETED.")
        
        # 2. Identify Target Writes
        _log_print("info", "Step 2: Identifying Target Writes...")
        target_write_nodes = identify_target_writes()
        _log_print("info", f"Step 2: Identify Target Writes COMPLETED. Found {len(target_write_nodes)} targets.")
        
        # 3. Trace Dependencies
        _log_print("info", "Step 3: Tracing Node Dependencies...")
        required_compute_nodes = trace_node_dependencies(target_write_nodes)
        _log_print("info", f"Step 3: Trace Node Dependencies COMPLETED. Found {len(required_compute_nodes)} compute nodes.")
        
        # 4. Find Associated Backdrops
        _log_print("info", "Step 4: Finding Associated Backdrops...")
        associated_backdrops = find_backdrop_nodes(required_compute_nodes)
        _log_print("info", f"Step 4: Find Associated Backdrops COMPLETED. Found {len(associated_backdrops)} backdrops.")
        
        # 5. Final Set of Nodes to Keep
        _log_print("info", "Step 5: Collecting Final Required Nodes...")
        required_nodes, required_node_names = collect_required_nodes(required_compute_nodes, associated_backdrops)
        results["nodes_kept"] = required_node_names
        _log_print("info", f"Step 5: Collect Final Required Nodes COMPLETED. Total {len(required_nodes)} nodes.")
        
        # 6. Collect Dependency Paths
        _log_print("info", "Step 6: Collecting Dependency Paths...")
        dependency_info = collect_dependency_paths_from_nodes(required_nodes)
        results["original_dependencies"] = dependency_info
        _log_print("info", f"Step 6: Collect Dependency Paths COMPLETED. Found {len(dependency_info)} potential paths.")
        
        # 7. Bake Gizmos (Optional)
        _log_print("info", "Step 7: Processing Gizmo Baking (Optional)...")
        baked_count, required_nodes = process_gizmo_baking(required_nodes, args.bake_gizmos)
        results["gizmos_baked_count"] = baked_count
        _log_print("info", f"Step 7: Process Gizmo Baking COMPLETED. Baked {baked_count} gizmos. Node count now {len(required_nodes)}.")
        
        # 8. Calculate Final Paths and Repath Knobs (Optional)
        _log_print("info", "Step 8: Repathing Script Knobs (Optional)...")
        dependency_map_for_repath, repath_count = repath_script_knobs(
            required_nodes, 
            dependency_info, 
            args.repath_script,
            args.archive_root, 
            args.final_script_archive_path,
            args.metadata_json
        )
        results["repath_count"] = repath_count
        _log_print("info", f"Step 8: Repath Script Knobs COMPLETED. Repathed {repath_count} knobs.")
        
        # 9. Select Required Nodes and Save Final Script
        _log_print("info", "Step 9: Saving Pruned Script...")
        final_saved_script_path = save_pruned_script(required_nodes, args.final_script_archive_path, args.archive_root)
        _log_print("info", "Step 9: Save Pruned Script COMPLETED.")
        
        # Mark as success after all operations complete
        results["status"] = "success"
        results["final_saved_script_path"] = final_saved_script_path
        _log_print("info", "--- All Nuke Tasks Completed Successfully (pre-dependency map) ---") # Success Log pre-map
        
        # Generate the dependency map for copying files
        _log_print("info", "Step 10: Generating Final Dependency Map for Copying...")
        if results["status"] == "success":
            dependencies_to_copy = generate_dependency_map(
                dependency_info, 
                args.archive_root, 
                args.metadata_json
            )
            results["dependencies_to_copy"] = dependencies_to_copy
            _log_print("info", f"Step 10: Generate Final Dependency Map COMPLETED. Found {len(dependencies_to_copy)} files to copy.")
        else:
            _log_print("warning", "Skipping final dependency map generation due to earlier failure.")

    except Exception as e:
        # Catch all errors during the process
        results["status"] = "failure"
        error_msg = f"Error during Nuke processing: {e}\n{traceback.format_exc()}"
        errors.append(error_msg)
        _log_print("error", f"--- Nuke Task Execution FAILED ---") # Failure Log
        _log_print("error", error_msg)
    
    results["errors"] = errors
    _log_print("info", f"--- Finishing Nuke Task Execution (Status: {results.get('status', 'unknown')}) ---") # End Task Log
    return results


# --- Main Execution Block ---
if __name__ == "__main__":
    # This block runs when script executed with `nuke -t _nuke_executor.py ...`
    parser = argparse.ArgumentParser(description="Internal Nuke Executor for Fix Archive")
    # Define expected arguments passed by the wrapper
    parser.add_argument("--input-script-path", required=True, help="Source .nk script")
    parser.add_argument("--archive-root", required=True, help="Archive destination root")
    parser.add_argument("--final-script-archive-path", required=True, help="Absolute path where final script should be saved")
    parser.add_argument("--metadata-json", required=True, help="JSON string of metadata (vendor, show, etc.)")
    parser.add_argument("--bake-gizmos", action="store_true", help="Flag to enable gizmo baking")
    parser.add_argument("--repath-script", action="store_true", help="Flag to enable repathing")
    # Add other necessary args like frame_range_override if needed by internal funcs

    exit_code = 1 # Default to error
    final_results = {"status": "failure", "errors": []}
    try:
        args = parser.parse_args() # Parse args passed from command line
        _log_print("info", f"Nuke Executor started with args: {vars(args)}")
        final_results = run_nuke_tasks(args)
        if final_results["status"] == "success":
             exit_code = 0
        else:
             _log_print("error", "Nuke processing tasks reported failure.")

    except Exception as e:
        # Catch unexpected errors during argument parsing or main task execution
        _log_print("error", f"--- NUKE EXECUTOR FATAL ERROR ---")
        err_msg = f"An unexpected error occurred in Nuke execution: {e}\n{traceback.format_exc()}"
        _log_print("error", err_msg)
        final_results["errors"] = final_results.get("errors", []) + [err_msg]
        # Ensure status reflects failure
        final_results["status"] = "failure"

    finally:
        # --- Output final JSON results to stdout ---
        _log_print("info", "--- NUKE EXECUTOR FINAL RESULTS ---")

        # display nodes_kept count for brevity
        if "nodes_kept" in final_results:
            final_results["nodes_kept"] = len(final_results["nodes_kept"])

        try:
            # Pretty print with indent
            json_output = json.dumps(final_results, indent=4)
            print(json_output)
        except TypeError as json_e:
            # Fallback if results (already without nodes_kept) contain other non-serializable data
            _log_print("error", f"Error serializing final results: {json_e}")

            current_errors = final_results.get("errors", [])
            if not isinstance(current_errors, list): # Ensure errors is a list
                current_errors = [str(current_errors)]

            fallback_errors_list = current_errors + [f"Serialization error: {json_e}"]

            fallback_results = {
                 "status": "failure",
                 "errors": fallback_errors_list,
                 "serialization_fallback": True
            }
            # Also pretty print fallback
            print(json.dumps(fallback_results, indent=4))

        _log_print("info", f"--- NUKE EXECUTOR SCRIPT END (Exit Code: {exit_code}) ---")
        # Nuke automatically exits after -t script finishes, but set code explicitly
        sys.exit(exit_code)