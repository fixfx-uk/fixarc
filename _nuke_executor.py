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
from typing import Dict, List, Set, Optional, Tuple, Any, Union # Use standard typing
import logging
import re # Added for regex matching

# Configure logging based on NUKE_VERBOSITY environment variable
# This ensures the executor script respects the verbosity level set by the parent process
verbosity_level = os.environ.get("NUKE_VERBOSITY", "1")  # Default to INFO level
try:
    verbosity_level = int(verbosity_level)
except ValueError:
    verbosity_level = 1  # Default to INFO if parsing fails

# Set up logging to stderr for the wrapper to capture
if verbosity_level >= 2:
    log_level = logging.DEBUG
    log_format = '%(asctime)s [%(levelname)s] %(message)s'
elif verbosity_level == 1:
    log_level = logging.INFO
    log_format = '%(asctime)s [%(levelname)s] %(message)s'
else:
    log_level = logging.WARNING
    log_format = '%(asctime)s [%(levelname)s] %(message)s'

logging.basicConfig(level=log_level,
                    format=log_format,
                    stream=sys.stderr)
log = logging.getLogger(__name__)
log.debug(f"Nuke executor logging initialized at level: {logging.getLevelName(log_level)} (NUKE_VERBOSITY={verbosity_level})")

def _log_print(level: str, message: str) -> None:
    """Simple print-based logging mimic for Nuke environment, now targets stderr."""
    # Output format matches basic logger for parsing by main process if needed
    # Using a direct print to sys.stderr for robustness in Nuke -t environment.
    try:
        # Basic sanitization for the message to avoid print errors with special chars.
        safe_message = str(message).replace('\n', '\\n') # Escape newlines for single-line log output
        print(f"[{level.upper():<7}] [NukeExecutor_LogPrintDirect] {safe_message}", file=sys.stderr)
        sys.stderr.flush() # Ensure it gets written out immediately
    except Exception as e:
        # Fallback if printing the formatted message fails
        try:
            print(f"[ERROR] [NukeExecutor_LogPrintDirect] Error in _log_print itself: {e}", file=sys.stderr)
            sys.stderr.flush()
        except:
            pass # If even this fails, suppress further errors

def get_frame_padding_pattern(path: Union[str, Path]) -> Optional[str]:
    """
    Detect frame padding patterns in a file path string.
    Identifies standard patterns: %04d, ####, $F4, etc.
    Returns the matched pattern or None if no pattern found.
    """
    if not path:
        return None
        
    path_str = str(path).replace("\\", "/")
    
    # Check for %0Nd pattern (e.g., %04d)
    percent_match = re.search(r"(%0*(\d*)d)", path_str)
    if percent_match:
        return percent_match.group(1)
    
    # Check for one or more # characters
    hash_match = re.search(r"(#+)", path_str)
    if hash_match:
        return hash_match.group(1)
    
    # Check for $F pattern (e.g., $F, $F4)
    f_match = re.search(r"(\$F\d*)", path_str)
    if f_match:
        return f_match.group(1)
        
    return None

def is_sequence_pattern(path: Union[str, Path]) -> bool:
    """
    Check if a path contains a frame sequence pattern.
    """
    return get_frame_padding_pattern(path) is not None

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

# --- Constants (Mirrored from fixarc.constants for self-containment) ---
# SPT v3.2.0 Folder Names (Placeholders for format())
VENDOR_DIR: str = "{vendor}"
SHOW_DIR: str = "{show}"
EPISODE_DIR: str = "{episode}"
SHOT_DIR: str = "{episode}_{sequence}_{shot}_{tag}"

# Relative Archive Paths
PROJECT_FILES_REL: str = "project/nuke" # For where .nk scripts are typically stored
ELEMENTS_REL: str = "elements"
PUBLISH_REL: str = "publish"

# Asset Handling
ASSETS_REL: str = "assets"
LIBRARY_ROOTS: List[str] = [ # Example, this might need to be configurable if dynamic
    "Z:/fxlb/",
    "/mnt/fxlb/",
]

# Nuke Node Classes
READ_NODE_CLASSES: frozenset[str] = frozenset([
    "Read", "ReadGeo", "ReadGeo2", "DeepRead", "Camera", "Camera2", "Camera3",
    "Axis", "Axis2", "Axis3", "OCIOFileTransform", "Vectorfield",
    "GenerateLUT", "BlinkScript", "ParticleCache", "PointCloudGenerator", "STMap",
])
WRITE_NODE_CLASSES: frozenset[str] = frozenset(["Write", "WriteGeo", "DeepWrite"])
# --- End Mirrored Constants ---


# --- SPT Directory Format Constants (mirroring fixarc.constants) ---
# VENDOR_DIR = "{vendor}" # Now defined above
# SHOW_DIR = "{show}" # Now defined above
# EPISODE_DIR = "{episode}" # Now defined above
# SHOT_DIR = "{episode}_{sequence}_{shot}_{tag}" # Key constant for shot directory naming # Now defined above
# PROJECT_FILES_REL = "project/nuke" # For where .nk scripts are typically stored in archive # Now defined above

# --- Helper Functions (Internal to this script) ---

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

def _collect_dependency_paths(
    nodes: Set[nuke.Node],
    metadata_dict: Optional[Dict[str, Any]],
    library_roots_config: List[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Iterates through nodes and collects file paths from relevant knobs.
    Determines category, source item on disk, and other characteristics for each dependency.
    Returns:
    {
        "NodeName.knobName": {
            "original_script_value": str,
            "resolved_path_in_nuke": str,
            "source_item_on_disk": str,
            "dependency_category": str,
            "matched_library_root": Optional[str],
            "is_source_directory": bool,
            "exists_on_disk": bool,
            "error": Optional[str]
        }, ...
    }
    """
    dependency_details: Dict[str, Dict[str, Any]] = {}
    _log_print("info", f"Collecting dependency paths from {len(nodes)} nodes...")
    script_dir = None
    current_script_name = "Root"

    if nodes:
        try:
            current_script_name = nuke.root().name()
            if current_script_name and current_script_name != "Root":
                script_dir = os.path.dirname(current_script_name)
            else:
                _log_print("warning", "Script has no name or is 'Root'. Relative paths may not resolve correctly initially.")
        except RuntimeError as e:
            _log_print("warning", f"Could not get script name for resolving relative paths: {e}")

    project_specific_asset_roots: List[str] = []
    if metadata_dict and metadata_dict.get('show'):
        project_name = str(metadata_dict['show'])
        try:
            project_asset_base_prefixes = ["Z:/proj/", "/mnt/proj/"]
            for prefix_str in project_asset_base_prefixes:
                prefix_path = Path(prefix_str.replace("\\", "/")) # Corrected: single backslash
                proj_assets_path = prefix_path / project_name / "assets"
                project_specific_asset_roots.append(str(proj_assets_path).replace("\\", "/") + "/") # Corrected: single backslash
                _log_print("debug", f"Derived project-specific asset root: {str(proj_assets_path)}/")
        except Exception as e:
            _log_print("warning", f"Could not construct project-specific asset root paths for project '{project_name}': {e}")

    all_library_roots = [Path(p.replace("\\", "/")) for p in library_roots_config] + \
                        [Path(p.replace("\\", "/")) for p in project_specific_asset_roots] # Corrected: single backslash for elements of project_specific_asset_roots
    _log_print("debug", f"Effective library/asset roots for categorization: {all_library_roots}")

    for i, node in enumerate(nodes):
        node_name = node.fullName()
        node_class = node.Class()
        knobs_to_process: List[Tuple[str, nuke.Knob, str]] = []

        if node_class in READ_NODE_CLASSES:
            read_knobs_to_check_map: Dict[str, nuke.Knob] = {}
            read_knobs_to_check_map['file'] = node.knob('file')
            read_knobs_to_check_map['proxy'] = node.knob('proxy')
            if node_class == "OCIOFileTransform": read_knobs_to_check_map['cccid'] = node.knob('cccid')
            if node_class == "Vectorfield": read_knobs_to_check_map['vfield_file'] = node.knob('vfield_file')
            for knob_name, knob_obj in read_knobs_to_check_map.items():
                if knob_obj:
                    knobs_to_process.append((knob_name, knob_obj, ELEMENTS_REL))
        elif node_class in WRITE_NODE_CLASSES:
            file_knob = node.knob('file')
            if file_knob:
                knobs_to_process.append(('file', file_knob, PUBLISH_REL))
            proxy_knob = node.knob('proxy')
            if proxy_knob and proxy_knob.value():
                knobs_to_process.append(('proxy', proxy_knob, PUBLISH_REL))
        elif _is_valid_writefix(node):
            profile_knob = node.knob('profile')
            if profile_knob:
                profile_value = profile_knob.value()
                if profile_value:
                    location_knob_name = f"{profile_value.lower()}_location"
                    location_knob = node.knob(location_knob_name)
                    if location_knob:
                        knobs_to_process.append((location_knob_name, location_knob, PUBLISH_REL))
                    else:
                        _log_print("warning", f"WriteFix '{node_name}': Could not find location knob '{location_knob_name}' for profile '{profile_value}'.")

        for knob_name, knob, initial_category_hint in knobs_to_process:
            entry_key = f"{node_name}.{knob_name}"
            data_dict: Dict[str, Any] = {
                "original_script_value": None,
                "resolved_path_in_nuke": None,
                "source_item_on_disk": None,
                "dependency_category": initial_category_hint,
                "is_source_directory": False,
                "exists_on_disk": False,
                "error": None,
                "matched_library_root": None
            }

            try:
                original_script_value = knob.value()
                data_dict["original_script_value"] = str(original_script_value).replace("\\", "/") if original_script_value else None # Corrected: single backslash

                if not original_script_value:
                    _log_print("debug", f"  Knob '{knob_name}' on '{node_name}' is empty. Skipping.")
                    dependency_details[entry_key] = data_dict
                    continue

                resolved_path_in_nuke_str = None
                if isinstance(knob, nuke.Text_Knob):
                    resolved_path_in_nuke_str = original_script_value
                elif hasattr(knob, 'evaluate'):
                    try:
                        original_has_pattern = is_sequence_pattern(original_script_value)
                        resolved_path = knob.evaluate()
                        if original_has_pattern and resolved_path: # Ensure resolved_path is not None
                            resolved_path_parent = Path(resolved_path).parent
                            original_filename = Path(original_script_value).name
                            resolved_path_in_nuke_str = str(resolved_path_parent / original_filename)
                            _log_print("debug", f"    Preserved original sequence pattern: '{original_script_value}' -> '{resolved_path_in_nuke_str}'")
                        else:
                            resolved_path_in_nuke_str = resolved_path
                    except Exception as eval_e:
                        _log_print("warning", f"    Error evaluating knob '{knob_name}' on '{node_name}': {eval_e}. Falling back.")
                        resolved_path_in_nuke_str = original_script_value
                else:
                    resolved_path_in_nuke_str = original_script_value

                if not resolved_path_in_nuke_str:
                    _log_print("debug", f"  Knob '{knob_name}' on '{node_name}' produced no resolved path. Skipping.")
                    dependency_details[entry_key] = data_dict
                    continue
                
                resolved_path_in_nuke_str = str(resolved_path_in_nuke_str).replace("\\", "/") # Corrected: single backslash
                data_dict["resolved_path_in_nuke"] = resolved_path_in_nuke_str
                
                path_for_checks_str = resolved_path_in_nuke_str
                if script_dir and not os.path.isabs(path_for_checks_str):
                    path_for_checks_str = os.path.abspath(os.path.join(script_dir, path_for_checks_str))
                    path_for_checks_str = str(path_for_checks_str).replace("\\", "/") # Corrected: single backslash
                    _log_print("debug", f"    Absolutized '{resolved_path_in_nuke_str}' to '{path_for_checks_str}' for checks.")
                elif not os.path.isabs(path_for_checks_str):
                     _log_print("warning", f"    Path '{path_for_checks_str}' is relative but script_dir unavailable. Checks might be inaccurate.")

                path_for_checks_obj = Path(path_for_checks_str)
                is_potential_sequence = is_sequence_pattern(data_dict["original_script_value"]) or \
                                        is_sequence_pattern(resolved_path_in_nuke_str)
                if is_potential_sequence:
                    _log_print("debug", f"    Detected sequence pattern in '{path_for_checks_str}' (Original: '{data_dict['original_script_value']}', ResolvedNuke: '{resolved_path_in_nuke_str}')")

                # Step 1: Determine final dependency_category and matched_library_root
                data_dict["dependency_category"] = initial_category_hint
                data_dict["matched_library_root"] = None
                
                path_to_categorize_obj = path_for_checks_obj
                for lib_root in all_library_roots:
                    try:
                        normalized_lib_root_str = str(lib_root).replace("\\", "/").rstrip("/") # Corrected: single backslash
                        normalized_path_to_categorize_str = str(path_to_categorize_obj).replace("\\", "/") # Corrected: single backslash
                        if normalized_path_to_categorize_str.lower().startswith(normalized_lib_root_str.lower() + "/"):
                            data_dict["dependency_category"] = ASSETS_REL
                            data_dict["matched_library_root"] = str(lib_root)
                            _log_print("debug", f"    Categorized '{path_for_checks_str}' as '{ASSETS_REL}' based on root '{lib_root}'")
                            break
                    except Exception as e_cat:
                        _log_print("warning", f"    Error during library root comparison for '{path_to_categorize_obj}' against '{lib_root}': {e_cat}")
                
                if data_dict["dependency_category"] == initial_category_hint:
                     _log_print("debug", f"    Path '{path_for_checks_str}' not in library roots. Using initial hint: '{initial_category_hint}'")

                # Step 2: Determine source_item_on_disk and is_source_directory
                data_dict["source_item_on_disk"] = path_for_checks_str
                data_dict["is_source_directory"] = path_for_checks_obj.is_dir()

                # Rule: For input sequences (ASSETS_REL or ELEMENTS_REL), target their parent directory.
                if is_potential_sequence and data_dict["dependency_category"] != PUBLISH_REL:
                    if not path_for_checks_obj.is_dir(): # Only if the path itself isn't already a directory
                        parent_dir = path_for_checks_obj.parent
                        data_dict["source_item_on_disk"] = str(parent_dir).replace("\\", "/") # Corrected: single backslash
                        data_dict["is_source_directory"] = True
                        _log_print("info", f"    Input sequence '{path_for_checks_str}' (Cat: {data_dict['dependency_category']}). Targeting parent dir for archive: '{data_dict['source_item_on_disk']}'.")

                # Step 3: Determine exists_on_disk for the (potentially updated) source_item_on_disk
                source_item_to_check_obj = Path(data_dict["source_item_on_disk"])
                if data_dict["is_source_directory"]:
                    data_dict["exists_on_disk"] = source_item_to_check_obj.is_dir()
                    if not data_dict["exists_on_disk"]:
                        if is_potential_sequence and data_dict["dependency_category"] != PUBLISH_REL and data_dict["source_item_on_disk"] != path_for_checks_str: # i.e. we changed it to parent
                             _log_print("warning", f"    Targeted parent directory '{data_dict['source_item_on_disk']}' for INPUT sequence '{path_for_checks_str}' does not exist or is not a directory.")
                        else:
                             _log_print("debug", f"    Targeted directory '{data_dict['source_item_on_disk']}' does not exist or is not a directory.")
                else:
                    data_dict["exists_on_disk"] = source_item_to_check_obj.exists()
                    if not data_dict["exists_on_disk"]:
                         _log_print("debug", f"    File/Pattern '{data_dict['source_item_on_disk']}' does not exist on disk.")
                
                _log_print("debug", f"  Collected for '{entry_key}': "
                                   f"Orig='{data_dict['original_script_value']}', "
                                   f"ResolvedNuke='{data_dict['resolved_path_in_nuke']}', "
                                   f"SourceDisk='{data_dict['source_item_on_disk']}', "
                                   f"Cat='{data_dict['dependency_category']}', "
                                   f"MatchedRoot='{data_dict['matched_library_root']}', "
                                   f"IsDir='{data_dict['is_source_directory']}', "
                                   f"Exists='{data_dict['exists_on_disk']}'")

            except Exception as e:
                error_msg = f"Error processing knob '{knob_name}' for '{node_name}': {e}"
                _log_print("error", error_msg)
                _log_print("error", traceback.format_exc())
                data_dict["error"] = error_msg
            
            dependency_details[entry_key] = data_dict

    _log_print("info", f"Collected details for {len(dependency_details)} file dependency paths.")
    try:
        _log_print("debug", f"Full dependency_details collected: {json.dumps(dependency_details, indent=2)}")
    except TypeError:
        _log_print("warning", "Could not serialize dependency_details to JSON for full logging.")

    return dependency_details


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
    The dependency_map now contains rich info: {resolved_path_in_nuke: {destination_path: ..., ...}}
    Returns the number of successful repath operations.
    """
    _log_print("info", f"Starting repathing process for {len(nodes_to_repath)} nodes...")
    repath_count = 0
    failed_repaths: List[str] = []

    script_dir = None # Initialize script_dir
    # Get script_dir once if there are nodes to process, as nuke.root().name() might be slow
    if nodes_to_repath:
        try:
            current_script_name = nuke.root().name()
            if current_script_name and current_script_name != "Root": # Ensure script has a name
                 script_dir = os.path.dirname(current_script_name)
            else:
                _log_print("warning", "Script has no name or is 'Root' during repathing. Relative paths may not resolve correctly.")
        except RuntimeError as e:
            _log_print("warning", f"Could not get script name for resolving relative paths during repathing: {e}")

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
             # For WriteFix, the specific location knob (e.g. 'comp_location') would need to be identified here
             # However, repathing WriteFix output paths is less common. Current collection gets them into dependency_info.
             # If repathing them becomes a requirement, this section needs more specific logic for WriteFix.

        for knob_name, knob in knobs_to_check.items():
            if not knob: continue

            current_knob_value_path = None # Path from knob.value()
            current_resolved_path_for_knob = None # Path after .evaluate() or special handling

            try:
                current_knob_value_path = knob.value() # This is the 'original_path'
                if not current_knob_value_path: continue

                # Determine the resolved path for this specific knob, similar to collection logic
                if isinstance(knob, nuke.Text_Knob):
                    current_resolved_path_for_knob = current_knob_value_path
                elif hasattr(knob, 'evaluate'):
                    try:
                        current_resolved_path_for_knob = knob.evaluate()
                    except Exception:
                        current_resolved_path_for_knob = current_knob_value_path # Fallback
                else:
                    current_resolved_path_for_knob = current_knob_value_path


                if not current_resolved_path_for_knob: continue # Skip if no resolved path

                # Resolve if relative and normalize (using current_resolved_path_for_knob)
                path_to_check_in_map = ""
                if script_dir and not os.path.isabs(current_resolved_path_for_knob): 
                     path_to_check_in_map = os.path.abspath(os.path.join(script_dir, current_resolved_path_for_knob))
                elif not os.path.isabs(current_resolved_path_for_knob) and not script_dir:
                     # Cannot resolve, but keep it to see if it's in the map as a relative key (unlikely for repath map)
                     path_to_check_in_map = current_resolved_path_for_knob 
                     _log_print("warning", f"Cannot resolve relative path '{current_resolved_path_for_knob}' for '{node_name}.{knob_name}' during repath as script directory is unavailable. Path kept as original for map lookup.")
                else: # Is absolute or already resolved
                     path_to_check_in_map = current_resolved_path_for_knob

                path_to_check_in_map = str(path_to_check_in_map).replace("\\", "/")

                # Check if this resolved path is one we archived and needs repathing
                if path_to_check_in_map in dependency_map:
                    dependency_details = dependency_map[path_to_check_in_map]
                    final_archived_path = dependency_details.get("destination_path") # Get from dict
                    source_on_disk_for_repath = dependency_details.get("source_item_on_disk")
                    is_dir_for_repath = dependency_details.get("is_source_directory")

                    if final_archived_path:
                        # If the original knob value pointed to a directory (e.g. a folder knob, or a sequence we decided to copy as parent dir),
                        # and repathing is turning it into a relative path to that directory, that's usually fine.
                        # If the original knob was for a file/pattern, and final_archived_path is a directory (because we archived parent for sequence),
                        # we need to be careful. The repathing should point to the *original item within that directory* if it was a file/pattern.
                        # However, the current _calculate_relative_path_nuke expects final_archived_path to be the specific item.

                        # If the source_item_on_disk (which determined the final_archived_path structure) was a directory,
                        # but the knob originally pointed to a file/pattern *inside* it (e.g. seq pattern), then
                        # we need to reconstruct the relative path to that pattern *within* the archived directory structure.
                        path_to_set_on_knob = ""

                        if is_dir_for_repath and Path(source_on_disk_for_repath) == Path(path_to_check_in_map).parent and not Path(path_to_check_in_map).is_dir():
                            # This means: we archived the parent directory (source_on_disk_for_repath)
                            # because the knob pointed to a sequence (path_to_check_in_map, which is not a dir itself).
                            # The final_archived_path corresponds to this parent directory.
                            # We need the knob to point to the sequence pattern *relative to* the script location, but *within* the archived parent dir structure.
                            # Example: script at archive/proj/nuke/script.nk
                            #          archived dir at archive/FixFX/elements/my_seq_folder/
                            #          original sequence was Z:/shot/my_seq_folder/img.####.exr
                            #          knob should be repathed to ../../FixFX/elements/my_seq_folder/img.####.exr

                            original_filename = Path(path_to_check_in_map).name # e.g., img.####.exr
                            archived_item_specific_path = Path(final_archived_path) / original_filename
                            path_to_set_on_knob = _calculate_relative_path_nuke(final_script_archive_path, str(archived_item_specific_path))
                            _log_print("debug", f"  Repath detail: Knob was sequence pattern '{path_to_check_in_map}', parent dir '{source_on_disk_for_repath}' archived to '{final_archived_path}'. Repathing to specific item '{path_to_set_on_knob}'")
                        else:
                            # Standard case: final_archived_path is the direct counterpart to path_to_check_in_map (file or dir)
                            path_to_set_on_knob = _calculate_relative_path_nuke(final_script_archive_path, final_archived_path)

                        knob.setValue(path_to_set_on_knob)
                        _log_print("debug", f"Repathed '{node_name}.{knob_name}': Original Script Value='{current_knob_value_path}', ResolvedToMapKey='{path_to_check_in_map}' -> New Script Value='{path_to_set_on_knob}'")
                        repath_count += 1
                    else:
                        _log_print("warning", f"Skipping repath for '{node_name}.{knob_name}': Resolved path '{path_to_check_in_map}' found in map, but no valid 'destination_path' provided or archive failed.")
                        failed_repaths.append(f"{node_name}.{knob_name} (no valid destination_path in map or archive failed for resolved path)")
                # else:
                     # _log_print("debug", f"Path '{path_to_check_in_map}' (from resolved '{current_resolved_path_for_knob}') not in archive map for {node_name}.{knob_name}. Skipping repath.")

            except Exception as e:
                 _log_print("error", f"Error during repathing '{node_name}.{knob_name}' (Original Script Value: {current_knob_value_path}, Resolved Attempted: {current_resolved_path_for_knob}): {e}")
                 _log_print("error", traceback.format_exc())
                 failed_repaths.append(f"{node_name}.{knob_name} (error: {e})")

    _log_print("info", f"Repathing finished. Set {repath_count} knob values.")
    if failed_repaths:
         _log_print("warning", f"Encountered {len(failed_repaths)} issues during repathing. Check logs.")
    return repath_count

# --- Main Executor Function and Task-Specific Functions ---
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
        raise ConfigurationError("Final script archive path is required for saving.")
    
    if not archive_root:
        raise ConfigurationError("Archive root is required for saving (for temp operations).")
    
    # Backup Root node settings
    root_data = nuke.root().writeKnobs(nuke.WRITE_ALL | nuke.TO_SCRIPT)
    _log_print("debug", "Root settings serialized successfully")

    # Deselect all and select only target nodes
    for n_iter in nuke.allNodes(recurseGroups=True): # Renamed loop variable
        n_iter.setSelected(False)

    final_node_names = [n.fullName() for n in nodes if nuke.exists(n.fullName())]
    nodes_selected_count = 0
    missing_final_nodes = []
    for name in final_node_names:
        node_to_select = nuke.toNode(name)
        if node_to_select:
            try:
                node_to_select.setSelected(True)
                nodes_selected_count += 1
            except Exception as sel_e:
                _log_print("warning", f"Could not select final node '{name}': {sel_e}")
        else:
            _log_print("warning", f"Required node '{name}' not found in final state before saving.")
            missing_final_nodes.append(name)

    if nodes_selected_count == 0:
        if not final_node_names and not nodes: # nodes is the original set passed to function
             _log_print("warning", "Save operation called with an empty set of nodes initially. Resulting script will be empty but retain root settings.")
             # This case will lead to an empty script being saved, which is acceptable.
        else:
            # This case means nodes were expected (based on the 'nodes' input set or 'final_node_names' derived from it), 
            # but none were selectable or found after processing. This is an error.
            raise PruningError("No nodes were selected for saving. Pruning, baking might have removed all nodes, or selection failed for all expected nodes.")

    _log_print("info", f"Selected {nodes_selected_count} final nodes for saving.")
    if missing_final_nodes:
        _log_print("warning", f"Missing {len(missing_final_nodes)} required nodes in final state: {', '.join(missing_final_nodes)}")

    temp_nodes_file = None
    try:
        temp_dir = os.path.join(archive_root, ".tmp") # Use archive_root for temp
        os.makedirs(temp_dir, exist_ok=True)
        _log_print("debug", f"Using custom temp directory for node copy: {temp_dir}")
        
        import uuid # Make sure uuid is imported if not already global for this script
        temp_filename = f"nodes_for_pruned_script_{uuid.uuid4().hex}.nk"
        temp_nodes_file = os.path.join(temp_dir, temp_filename)
        
        _log_print("debug", f"Saving selected nodes to custom temp file: {temp_nodes_file}")
        if nodes_selected_count > 0: # Only copy if there are nodes selected
            nuke.nodeCopy(temp_nodes_file)
        else:
            _log_print("info", "No nodes selected to copy to temp file; proceeding to save effectively empty script (with root settings).")
            # Create an empty temp file so the rest of the logic doesn't break, ensuring it contains valid Nuke script header if needed by nodePaste
            with open(temp_nodes_file, 'w') as f_temp:
                f_temp.write("# Root settings preserved for empty script.\\nversion {}\nRoot {{\n inputs 0\n name Root\n}}\n")


        nuke.scriptClear()
        
        try:
            nuke.root().readKnobs(root_data)
            _log_print("debug", "Root settings restored successfully")
        except Exception as e_read_knobs:
            _log_print("warning", f"Failed to fully restore root settings: {e_read_knobs}")
        
        # Only paste if there were nodes copied.
        # If nodes_selected_count was 0, temp_nodes_file was created empty (or with minimal header)
        # and nuke.nodePaste on such a file might be benign or raise an error depending on Nuke version.
        # It's safer to only paste if we actually copied nodes.
        if nodes_selected_count > 0 and os.path.exists(temp_nodes_file) and os.path.getsize(temp_nodes_file) > 0:
            _log_print("debug", "Pasting nodes from custom temp file")
            nuke.nodePaste(temp_nodes_file)
        elif nodes_selected_count > 0 : 
            # This case: nodes were expected, nodeCopy was called, but temp file is bad
            _log_print("warning", f"Custom temp file '{temp_nodes_file}' is missing or empty after nodeCopy attempt despite having nodes selected. Resulting script might be missing nodes.")
        else:
            # nodes_selected_count == 0, script will be empty (plus root settings)
            _log_print("info", "No nodes were pasted as no nodes were originally selected for copy.")
            
        final_script_dir = os.path.dirname(final_script_path)
        if final_script_dir: # Ensure directory exists only if path is not just a filename
            os.makedirs(final_script_dir, exist_ok=True)
            _log_print("info", f"Ensured final script directory exists: {final_script_dir}")
        
        nuke.scriptSaveAs(filename=final_script_path, overwrite=1)
        
        # Verification after save
        if not os.path.exists(final_script_path):
            raise ArchiverError(f"Final save failed: Output file '{final_script_path}' does not exist after save attempt.")
        
        if os.path.getsize(final_script_path) == 0 and nodes_selected_count > 0:
            # If nodes were selected, an empty file is an error.
            raise ArchiverError(f"Final save produced an unexpectedly empty file: Output file '{final_script_path}' is empty despite {nodes_selected_count} nodes being selected.")
        elif os.path.getsize(final_script_path) == 0 and nodes_selected_count == 0:
            _log_print("warning", f"Final saved script '{final_script_path}' is empty, but this was expected as no nodes were selected/kept. Root settings should be present.")

        _log_print("info", "Final script saved successfully.")
        return final_script_path
        
    finally:
        if temp_nodes_file and os.path.exists(temp_nodes_file):
            try:
                os.remove(temp_nodes_file)
                _log_print("debug", f"Removed custom temp file: {temp_nodes_file}")
            except Exception as e_remove:
                _log_print("warning", f"Failed to remove custom temp file {temp_nodes_file}: {e_remove}")
                
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
    return _collect_dependency_paths(nodes, None, LIBRARY_ROOTS)

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

def generate_dependency_map(dependency_info: Dict[str, Dict[str, Any]], archive_root: str, metadata_dict: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Generates the final dependency map for copying files.
    Uses 'source_item_on_disk' from dependency_info as the key to avoid redundancy
    and ensure correct handling of files vs. directories (e.g., sequence parent dirs).
    Constructs archive paths preserving relative structure after the shot folder.
    Uses 'dependency_category' from dependency_info to determine target SPT subfolder.
    The output dictionary value will contain 'destination_path', 'is_directory', and 'exists_on_disk'.
    """
    dependencies_to_copy: Dict[str, Dict[str, Any]] = {}
    _log_print("debug", "Generating final dependency map for copying...")
    temp_metadata = metadata_dict
    
    shot_code_parts = [
        temp_metadata.get('episode'),
        temp_metadata.get('sequence'),
        temp_metadata.get('shot'),
        temp_metadata.get('tag')
    ]
    if not all(shot_code_parts[:3]):
        _log_print("error", "Cannot construct shot code for map generation: Missing episode, sequence, or shot in metadata.")
        return {}
    shot_code = '_'.join(filter(None, shot_code_parts))
    _log_print("debug", f"Constructed shot code for path splitting: {shot_code}")

    comp_work_images_re = re.compile(r"Comp/work/[^/]+/images/(.*)", re.IGNORECASE)

    for node_knob_identifier, data in dependency_info.items():
        source_path_for_copy = data.get("source_item_on_disk")

        if not source_path_for_copy:
            _log_print("debug", f"Skipping mapping for item key \'{node_knob_identifier}\': Missing \'source_item_on_disk\'. Data: {data}")
            continue

        if data.get("error"):
            _log_print("debug", f"Skipping mapping for item key \'{node_knob_identifier}\' (\'{source_path_for_copy}\'): Error encountered during collection. Data: {data}")
            continue

        normalized_source_path_for_copy = str(source_path_for_copy).replace("\\", "/")

        if normalized_source_path_for_copy in dependencies_to_copy:
            _log_print("debug", f"Skipping mapping for item key \'{node_knob_identifier}\': Source path \'{normalized_source_path_for_copy}\' already processed.")
            continue

        dependency_category = data.get("dependency_category", ELEMENTS_REL)
        is_directory_to_copy = data.get("is_source_directory", False)
        exists_on_disk = data.get("exists_on_disk", False)

        _log_print("debug", f"generate_dependency_map: Processing SourceDisk=\'{normalized_source_path_for_copy}\', Category=\'{dependency_category}\', IsDirToCopy=\'{is_directory_to_copy}\', Exists=\'{exists_on_disk}\' (from item key: {node_knob_identifier})")

        try:
            category_spt_path = _get_spt_path(
                str(archive_root),
                temp_metadata,
                dependency_category
            )

            source_path_obj = Path(normalized_source_path_for_copy)
            path_parts = normalized_source_path_for_copy.split('/')
            
            final_relative_part = ""
            shot_code_found_in_path = False
            try:
                shot_code_idx = -1
                # For ASSETS_REL, we need to use the matched library root to determine the relative part.
                if dependency_category == ASSETS_REL and data.get("matched_library_root"):
                    matched_root_str = str(data["matched_library_root"]).replace("\\", "/").rstrip("/")
                    source_path_str = normalized_source_path_for_copy.replace("\\", "/")
                    if source_path_str.lower().startswith(matched_root_str.lower() + "/"):
                        final_relative_part = source_path_str[len(matched_root_str) + 1:] # Get the part after the root + '/'
                        _log_print("debug", f"  Derived ASSET relative part '{final_relative_part}' from source '{normalized_source_path_for_copy}' relative to matched root '{matched_root_str}'.")
                    else:
                        _log_print("warning", f"  ASSET '{normalized_source_path_for_copy}' did not start with its matched_library_root '{matched_root_str}' as expected. Falling back to item name.")
                        final_relative_part = source_path_obj.name # Fallback
                else: # Original logic for non-ASSETS_REL or if matched_library_root is missing
                    for i, part in enumerate(path_parts):
                        if part == shot_code:
                            shot_code_idx = i
                            break
                    
                    if shot_code_idx != -1:
                        shot_code_found_in_path = True
                        final_relative_part = "/".join(path_parts[shot_code_idx + 1:])
                        _log_print("debug", f"  Derived relative part '{final_relative_part}' from source '{normalized_source_path_for_copy}' after shot code '{shot_code}'.")
                    else:
                        final_relative_part = source_path_obj.name
                        _log_print("debug", f"  Shot code '{shot_code}' not found in source path '{normalized_source_path_for_copy}'. Using item name '{final_relative_part}' as relative part under category '{dependency_category}'.")

            except ValueError: # This was for the shot_code splitting, might be less relevant if ASSETS_REL uses direct relative pathing.
                 _log_print("warning", f"  Could not split path based on shot code for: {normalized_source_path_for_copy}. Falling back to item name.")
                 final_relative_part = source_path_obj.name
            
            if not final_relative_part and is_directory_to_copy:
                 if source_path_obj.name:
                     final_relative_part = source_path_obj.name
                     _log_print("debug", f"  Relative part was empty for directory \'{normalized_source_path_for_copy}\', using its name \'{final_relative_part}\'.")

            if dependency_category == ELEMENTS_REL and shot_code_found_in_path:
                comp_match = comp_work_images_re.match(final_relative_part)
                if comp_match:
                    _log_print("debug", f"  Applying Comp/work/images rule to (elements): \'{final_relative_part}\'")
                    final_relative_part = comp_match.group(1)
                    _log_print("debug", f"  Resulting relative path after Comp/work rule (elements): \'{final_relative_part}\'")
            
            elif dependency_category == PUBLISH_REL:
                publish_prefix = "publish/"
                temp_final_relative_part_lower = final_relative_part.lower().lstrip('/')
                if temp_final_relative_part_lower.startswith(publish_prefix):
                    actual_publish_prefix_idx = final_relative_part.lower().find(publish_prefix)
                    if actual_publish_prefix_idx != -1:
                        final_relative_part = final_relative_part[actual_publish_prefix_idx + len(publish_prefix):]
                        _log_print("debug", f"  Stripped leading \'{publish_prefix}\' (case-insensitive) from publish path. New final_relative_part: \'{final_relative_part}\'")

            final_relative_part = final_relative_part.lstrip('/')

            dest_path = category_spt_path / final_relative_part
            dest_path_str = str(dest_path).replace("\\", "/")

            dependencies_to_copy[normalized_source_path_for_copy] = {
                "destination_path": dest_path_str,
                "is_directory": is_directory_to_copy,
                "exists_on_disk": exists_on_disk
            }
            _log_print("debug", f"  Mapped dependency (Cat: {dependency_category}): \'{normalized_source_path_for_copy}\' -> Dest: \'{dest_path_str}\', IsDir: {is_directory_to_copy}, Exists: {exists_on_disk}")

        except Exception as map_e:
            _log_print("error", f"Could not calculate destination for copying \'{normalized_source_path_for_copy}\': {map_e} (from item key: {node_knob_identifier})")
            _log_print("debug", f"Exception details: {traceback.format_exc()}")

    _log_print("info", f"Collected mapping for {len(dependencies_to_copy)} unique file system items.")
    if dependencies_to_copy:
        try:
            _log_print("debug", f"Full dependencies_to_copy map: {json.dumps(dependencies_to_copy, indent=2)}")
        except TypeError:
            _log_print("warning", "Could not serialize dependencies_to_copy to JSON for full logging.")
    else:
        _log_print("info", "dependencies_to_copy map is empty.")

    return dependencies_to_copy

def _get_spt_path(
    archive_root_str: str,
    metadata_dict: Dict[str, Any],
    relative_category_path_str: str
) -> Path:
    """
    Constructs SPT path within _nuke_executor.py, mirroring archive_utils.py logic.
    Structure: {archive_root}/{vendor}/{show}/{episode}/{SHOT_DIR_fmt}/{relative_category_path}
    Assumes metadata_dict contains 'vendor', 'show', 'episode', 'sequence', 'shot', 'tag'.
    Does not perform deep sanitization like ensure_ltfs_safe as that's external.
    If relative_category_path_str is ASSETS_REL, path is {archive_root}/{vendor}/assets.
    """
    try:
        # --- Extract metadata (caller should ensure keys exist) ---
        vendor = str(metadata_dict['vendor'])

        # --- Format directory components using locally defined constants ---
        vendor_fmt = VENDOR_DIR.format(vendor=vendor)

        # Handle ASSETS_REL category separately for a vendor-level path
        if relative_category_path_str == ASSETS_REL:
            final_category_path = Path(archive_root_str) / vendor_fmt / ASSETS_REL
            _log_print("debug", f"Constructed SPT ASSETS category path: {final_category_path}")
            return final_category_path

        # --- Continue with existing logic for project/shot specific paths ---
        show = str(metadata_dict['show'])
        episode = str(metadata_dict['episode'])
        sequence = str(metadata_dict['sequence'])
        shot_num = str(metadata_dict['shot'])
        tag = str(metadata_dict['tag'])

        # --- Format directory components using locally defined constants ---
        show_fmt = SHOW_DIR.format(show=show)
        episode_fmt = EPISODE_DIR.format(episode=episode)
        # Use the SHOT_DIR constant for the shot-level directory name
        shot_dir_fmt = SHOT_DIR.format(episode=episode, sequence=sequence, shot=shot_num, tag=tag)

        # --- Construct Path ---
        # Path: archive_root / vendor / show / episode / formatted_shot_dir / category
        base_shot_path = Path(archive_root_str) / vendor_fmt / show_fmt / episode_fmt / shot_dir_fmt
        
        final_category_path = base_shot_path
        if relative_category_path_str:
            # Normalize slashes for the relative category path and remove leading/trailing
            clean_relative_path = relative_category_path_str.replace("\\", "/").strip('/')
            if '..' in clean_relative_path.split('/'):
                 _log_print("warning", f"Relative category path '{relative_category_path_str}' for SPT construction contains '..'. This might be unsafe.")
            final_category_path = base_shot_path / clean_relative_path
        
        _log_print("debug", f"Constructed SPT category path in Nuke Executor: {final_category_path}")
        return final_category_path

    except KeyError as e:
        _log_print("error", f"Missing metadata key for SPT path construction in Nuke Executor: {e}. Metadata: {metadata_dict}")
        raise ConfigurationError(f"Missing metadata key for SPT path construction in Nuke Executor: {e}")
    except Exception as e:
        _log_print("error", f"Unexpected error constructing SPT path in Nuke Executor: {e}")
        raise ArchiverError(f"Unexpected error constructing SPT path in Nuke Executor: {e}")

def run_nuke_tasks(args: argparse.Namespace) -> Dict[str, Any]:
    """
    Performs the core Nuke logic: load, prune, collect deps, bake, repath, save.
    """
    results: Dict[str, Any] = {"status": "failure"}  # Default status
    errors = []
    _log_print("info", "--- Starting Nuke Task Execution ---") # Start Task Log
    # Log relevant environment variables
    _log_print("debug", f"NUKE_PATH env: {os.environ.get('NUKE_PATH', 'Not Set')}")

    # Parse metadata_json once here
    metadata_dict: Optional[Dict[str, Any]] = None
    try:
        if args.metadata_json:
            metadata_dict = json.loads(args.metadata_json)
        else:
            errors.append("metadata_json was not provided to run_nuke_tasks.")
            _log_print("error", "metadata_json is missing.")
            # Depending on strictness, could raise ConfigurationError here
    except json.JSONDecodeError as jde:
        errors.append(f"Failed to parse metadata_json: {jde}")
        _log_print("error", f"JSON parsing error for metadata: {jde}")
        # Depending on strictness, could raise ConfigurationError here

    if metadata_dict is None: # If parsing failed or was not provided
        results["status"] = "failure"
        results["errors"] = errors
        _log_print("error", "--- Nuke Task Execution FAILED due to metadata issues (metadata_dict is None) ---")
        return results

    try:
        # Assume success unless an operation sets it to failure and adds to errors list
        results["status"] = "success"

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
        _log_print("info", "Step 6: Collecting Dependency Paths (Inputs from required nodes + Outputs from all Write/WriteFix)...")
        
        # Identify all relevant Write and WriteFix nodes for output path collection
        all_target_output_nodes_set: Set[nuke.Node] = set()
        root_nodes = nuke.allNodes(group=nuke.root()) # Get only nodes at the root level initially
        _log_print("debug", f"Scanning {len(root_nodes)} root level nodes for explicit output path collection.")

        for node in root_nodes: # Iterate over root nodes
            # Check if it's a Write node type OR a valid WriteFix gizmo
            if node.Class() in WRITE_NODE_CLASSES or _is_valid_writefix(node):
                disable_knob = node.knob('disable')
                if disable_knob and disable_knob.value():
                    _log_print("debug", f"Skipping disabled output node for explicit path collection: {node.fullName()}")
                    continue
                all_target_output_nodes_set.add(node)
                _log_print("debug", f"Added node '{node.fullName()}' (Class: {node.Class()}) to explicit output collection set.")
        
        _log_print("info", f"Found {len(all_target_output_nodes_set)} active root Write/WriteFix nodes for explicit output path collection.")

        # Combine required_nodes (for script integrity and their inputs) 
        # with all_target_output_nodes_set (for their outputs).
        # The _collect_dependency_paths function will categorize paths correctly based on node type.
        nodes_for_path_collection = required_nodes.union(all_target_output_nodes_set)
        _log_print("info", f"Total unique nodes for path collection (required_nodes + explicit_outputs): {len(nodes_for_path_collection)}")
        
        dependency_info = _collect_dependency_paths(nodes_for_path_collection, metadata_dict, LIBRARY_ROOTS)
        results["original_dependencies"] = dependency_info # This now contains inputs and outputs with categories
        _log_print("info", f"Step 6: Collect Dependency Paths COMPLETED. Found {len(dependency_info)} potential paths from combined set.")
        
        # 7. Bake Gizmos (Optional) - Operates on required_nodes that are kept in the script
        _log_print("info", "Step 7: Processing Gizmo Baking (Optional)...")
        baked_count, required_nodes = process_gizmo_baking(required_nodes, args.bake_gizmos)
        results["gizmos_baked_count"] = baked_count
        _log_print("info", f"Step 7: Process Gizmo Baking COMPLETED. Baked {baked_count} gizmos. Node count now {len(required_nodes)}.")
        
        # 8. Generate the dependency map (for copying and potentially repathing)
        # This map is {resolved_path_in_nuke: {destination_path, source_item_on_disk, ...}}
        _log_print("info", "Step 8: Generating Full Dependency Map (for copy and repath)... ")
        # Initialize map_for_copy_and_repath to an empty dictionary to ensure it's always defined
        map_for_copy_and_repath: Dict[str, Dict[str, Any]] = {}
        if results["status"] == "success": # Should always be true here if no prior critical errors
            map_for_copy_and_repath = generate_dependency_map(
                dependency_info, # Output from _collect_dependency_paths
                args.archive_root,
                metadata_dict
            )
            results["dependencies_to_copy"] = map_for_copy_and_repath # This is the map for the main process
            _log_print("info", f"Step 8: Generate Full Dependency Map COMPLETED. Found {len(map_for_copy_and_repath)} items for potential copy/repath.")
        else:
            _log_print("warning", "Skipping full dependency map generation due to earlier status not being 'success'.")
            results["dependencies_to_copy"] = {} # Ensure it exists


        # 9. Repath Knobs (Optional) - Operates on required_nodes (potentially after baking)
        _log_print("info", "Step 9: Repathing Script Knobs (Optional)... ")
        repath_count = 0
        if args.repath_script:
            if not args.final_script_archive_path:
                # This should have been caught by arg parser, but double check
                _log_print("error", "Final script archive path is required for repathing but not provided.")
                results["status"] = "failure" # Mark failure
                errors.append("Repathing error: final_script_archive_path missing.")
            elif results["status"] == "success": # Only repath if everything else is okay
                if not map_for_copy_and_repath:
                    _log_print("warning", "Repathing skipped: The dependency map (map_for_copy_and_repath) is empty.")
                else:
                    _log_print("info", "--- Starting Repath Script Knobs --- ")
                    repath_count = _repath_nodes(
                        required_nodes, 
                        map_for_copy_and_repath, # Pass the rich map
                        args.final_script_archive_path
                    )
                    _log_print("info", f"--- Finished Repath Script Knobs ({repath_count} paths updated) --- ")                    
            else:
                _log_print("warning", "Skipping repath due to earlier errors or status not being 'success'.")
        else:
            _log_print("info", "Skipping script repathing as per arguments.")
        results["repath_count"] = repath_count
        _log_print("info", f"Step 9: Repath Script Knobs COMPLETED. Repathed {repath_count} knobs.")

        # 10. Select Required Nodes and Save Final Script
        _log_print("info", "Step 10: Saving Pruned Script...")
        final_saved_script_path = ""
        if results["status"] == "success": # Only save if no critical errors before this point
            final_saved_script_path = save_pruned_script(required_nodes, args.final_script_archive_path, args.archive_root)
            results["final_saved_script_path"] = final_saved_script_path
            _log_print("info", "Step 10: Save Pruned Script COMPLETED.")
        else:
            _log_print("error", "Skipping final script save due to earlier errors or status not being 'success'.")
            # Ensure final_saved_script_path is in results for consistent structure, even if empty
            results["final_saved_script_path"] = ""
        
        # The status is now success by default, only changed to failure upon explicit error or exception.
        if results.get("status") == "success":
            _log_print("info", "--- All Nuke Tasks Assumed Successful (no explicit failures reported by tasks) ---")
        else: # Status was set to failure by a task or exception
            _log_print("error", "--- Nuke Task Execution FAILED (status was set to failure by a task or exception) ---")

    except PruningError as pe:
        results["status"] = "failure"
        error_msg = f"Pruning Error: {pe}\n{traceback.format_exc()}"
        errors.append(error_msg)
        _log_print("error", f"--- Nuke Task Execution FAILED (PruningError) ---")
        _log_print("error", error_msg)
    except ConfigurationError as ce:
        results["status"] = "failure"
        error_msg = f"Configuration Error: {ce}\n{traceback.format_exc()}"
        errors.append(error_msg)
        _log_print("error", f"--- Nuke Task Execution FAILED (ConfigurationError) ---")
        _log_print("error", error_msg)
    except ArchiverError as ae:
        results["status"] = "failure"
        error_msg = f"Archiver Error: {ae}\n{traceback.format_exc()}"
        errors.append(error_msg)
        _log_print("error", f"--- Nuke Task Execution FAILED (ArchiverError) ---")
        _log_print("error", error_msg)
    except Exception as e:
        # Catch all other errors during the process
        results["status"] = "failure"
        error_msg = f"Error during Nuke processing: {e}\n{traceback.format_exc()}"
        errors.append(error_msg)
        _log_print("error", f"--- Nuke Task Execution FAILED --- ") # Failure Log
        _log_print("error", error_msg)
    
    # Ensure that if the status is failure, the errors list is not empty
    if results.get("status") == "failure" and not errors: # `errors` is the local list from this function
        diagnostic_msg = "Nuke executor tasks resulted in a failure status, but no specific error messages were recorded by the task handler. This may indicate an unhandled logical path or a silent failure within the tasks."
        errors.append(diagnostic_msg)
        _log_print("error", f"DIAGNOSTIC: {diagnostic_msg}")

    results["errors"] = errors
    _log_print("info", f"--- Finishing Nuke Task Execution (Status: {results.get('status', 'unknown')}) --- ") # End Task Log
    return results


# --- Main Execution Block ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Internal Nuke Executor for Fix Archive")
    parser.add_argument("--input-script-path", required=True, help="Source .nk script")
    parser.add_argument("--archive-root", required=True, help="Archive destination root")
    parser.add_argument("--final-script-archive-path", required=True, help="Absolute path where final script should be saved")
    parser.add_argument("--metadata-json", required=True, help="JSON string of metadata (vendor, show, etc.)")
    parser.add_argument("--bake-gizmos", action="store_true", help="Flag to enable gizmo baking")
    parser.add_argument("--repath-script", action="store_true", help="Flag to enable repathing")

    exit_code = 1 # Default to error
    final_results: Dict[str, Any] = {"status": "failure", "errors": []} # Initialize
    try:
        args = parser.parse_args()
        _log_print("info", f"Nuke Executor started with args: {vars(args)}")
        final_results = run_nuke_tasks(args) # This will populate status and errors
        if final_results.get("status") == "success":
            exit_code = 0
        else:
            _log_print("error", "Nuke processing tasks reported failure. Check JSON output for error details.")

    except Exception as e:
        _log_print("error", f"--- NUKE EXECUTOR FATAL ERROR (before or during run_nuke_tasks) ---")
        err_msg = f"A top-level error occurred in Nuke execution: {e}\n{traceback.format_exc()}"
        _log_print("error", err_msg)
        # Ensure errors list exists and append
        if not isinstance(final_results.get("errors"), list):
            final_results["errors"] = []
        final_results["errors"].append(err_msg)
        final_results["status"] = "failure" # Explicitly set status to failure

    finally:
        json_start_tag_message = "--- NUKE EXECUTOR FINAL RESULTS ---"
        try:
            print(json_start_tag_message, file=sys.stdout)
            sys.stdout.flush()
        except Exception as e_print_tag:
            _log_print("error", f"CRITICAL: Failed to print json_start_tag to stdout: {e_print_tag}")
            try:
                print(json.dumps({"status": "failure", "errors": ["Failed to print JSON start tag", str(e_print_tag)]}, indent=4), file=sys.stdout)
                sys.stdout.flush()
            except: pass

        data_to_serialize = {}
        if final_results.get("status") == "failure":
            data_to_serialize["status"] = "failure"
            collected_errors = final_results.get("errors", [])
            if not isinstance(collected_errors, list):
                collected_errors = [str(collected_errors)] # Ensure it's a list
            
            stringified_errors = [str(err) for err in collected_errors if err is not None and str(err).strip()]
            
            if not stringified_errors:
                stringified_errors = ["An unspecified error occurred in the Nuke executor."]
            data_to_serialize["errors"] = stringified_errors
        else: # Success
            data_to_serialize = final_results.copy() # Operate on a copy
            if "nodes_kept" in data_to_serialize and isinstance(data_to_serialize.get("nodes_kept"), list):
                data_to_serialize["nodes_kept"] = len(data_to_serialize["nodes_kept"])
            # Ensure status is success if somehow not set (should be by run_nuke_tasks)
            data_to_serialize["status"] = final_results.get("status", "success")

        try:
            json_output = json.dumps(data_to_serialize, indent=4)
            print(json_output, file=sys.stdout)
            sys.stdout.flush()
        except TypeError as json_e:
            _log_print("error", f"CRITICAL: Error serializing final results to JSON: {json_e}")
            
            # Fallback serialization with a guaranteed simple structure
            original_errors_from_final_results = final_results.get("errors", [])
            if not isinstance(original_errors_from_final_results, list):
                original_errors_from_final_results = [str(original_errors_from_final_results)]
            
            cleaned_original_errors = [str(e) for e in original_errors_from_final_results if e is not None and str(e).strip()]
            if not cleaned_original_errors:
                 cleaned_original_errors = ["No specific error messages were collected prior to serialization failure."]

            fallback_output = {
                "status": "failure",
                "errors": cleaned_original_errors + [f"Additionally, a JSON serialization error occurred: {str(json_e)}"],
                "serialization_error_details": str(json_e)
            }
            try:
                print(json.dumps(fallback_output, indent=4), file=sys.stdout)
                sys.stdout.flush()
            except Exception as final_fallback_e:
                 _log_print("error", f"CRITICAL: Failed to print even fallback JSON: {final_fallback_e}")

        _log_print("info", f"--- NUKE EXECUTOR SCRIPT END (Exit Code: {exit_code}) ---")
        sys.exit(exit_code)
