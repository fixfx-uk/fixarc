"""
Functions designed to be executed within a Nuke (-t) environment.
This script is called by utils.run_nuke_action.
It uses command-line arguments to determine which action to perform
and prints results (like JSON data) to stdout for the calling process.
"""

import nuke
import os
import sys
import json
import traceback
import argparse
from pathlib import Path

# --- Constants (Copied for self-containment within Nuke env) ---
# Node classes considered as potential final outputs
WRITE_NODE_CLASSES = ["Write", "WriteGeo", "DeepWrite"]
# Add custom WriteFix check logic below

# Node classes that can have file dependencies
READ_NODE_CLASSES = [
    "Read", "ReadGeo2", "DeepRead", "Camera3", "Camera2", "Axis3", "Axis2",
    "OCIOFileTransform", "Vectorfield", "GenerateLUT", "BlinkScript",
]

# --- Helper Functions (Inside Nuke Env) ---

def is_valid_writefix(node):
    """Check if a Group node is a 'WriteFix' gizmo we care about."""
    if node.Class() != 'Group':
        return False
    # Check for a specific knob that identifies it as WriteFix
    if not node.knob('writefix'): # Assuming a knob named 'writefix' exists
        return False
    # Check if profile is 'QuickReview' and ignore if so
    profile_knob = node.knob('profile')
    if profile_knob and profile_knob.value() == 'QuickReview':
        print(f"  Ignoring WriteFix node '{node.fullName()}' with profile 'QuickReview'")
        return False
    return True

def _get_render_path_internal(node):
    """Internal helper to get render path from Write or WriteFix."""
    node_class = node.Class()
    evaluated_path = None
    error_msg = None

    try:
        if node_class in WRITE_NODE_CLASSES:
            file_knob = node.knob("file")
            if file_knob:
                evaluated_path = file_knob.evaluate()
        elif is_valid_writefix(node):
            # Logic specific to WriteFix gizmo structure
            profile_knob = node.knob('profile')
            if not profile_knob:
                 raise ValueError("WriteFix node missing 'profile' knob")
            profile = profile_knob.value()
            if not profile:
                 raise ValueError("WriteFix node has empty 'profile' value")

            # Assuming knobs like 'mov_location', 'mov_file' exist based on profile
            location_knob_name = f'{profile}_location'
            file_knob_name = f'{profile}_file'

            location_knob = node.knob(location_knob_name)
            file_knob = node.knob(file_knob_name)

            # Handle potential knob name variations if needed (e.g., some profiles might use different naming)
            if not location_knob: location_knob = node.knob(f'WriteFix.{location_knob_name}') # Check with prefix
            if not file_knob: file_knob = node.knob(f'WriteFix.{file_knob_name}')

            if not location_knob or not file_knob:
                # Try finding knobs without prefix as fallback
                if not location_knob: location_knob = node.knob(location_knob_name.split('.')[-1])
                if not file_knob: file_knob = node.knob(file_knob_name.split('.')[-1])

                if not location_knob or not file_knob:
                     raise ValueError(f"WriteFix node missing expected knobs for profile '{profile}': {location_knob_name}, {file_knob_name}")


            location_val = location_knob.evaluate() # Evaluate paths
            file_val = file_knob.evaluate()

            if not location_val or not file_val:
                 # Sometimes paths might be intentionally empty, but log warning
                 print(f"Warning: WriteFix evaluated paths might be empty for profile '{profile}' Node: {node.fullName()}")
                 # Decide if this is an error or okay. Let's allow empty for now.
                 # evaluated_path = "" # Or handle as error?
                 # Let's assume combining might work if one part is missing, adjust logic as needed.
                 evaluated_path = os.path.join(location_val or "", file_val or "").replace("\\", "/")
                 if not evaluated_path: # If still empty, likely an issue
                      raise ValueError(f"WriteFix resulted in empty path for profile '{profile}'")


            # Combine location and file - ensure proper separator
            # Handle cases where location might already include trailing slash
            if location_val and file_val:
                 # Simple join might add extra slash if location ends with one
                 location_val = location_val.rstrip('/\\')
                 evaluated_path = f"{location_val}/{file_val}".replace("\\", "/")
            elif location_val: # Only location provided (unlikely for file output)
                 evaluated_path = location_val.replace("\\", "/")
            elif file_val: # Only file provided (implies relative path?)
                 evaluated_path = file_val.replace("\\", "/")
            else: # Both empty after evaluation
                 raise ValueError(f"WriteFix evaluated paths resulted in empty strings for profile '{profile}'")


        if evaluated_path and not os.path.isabs(evaluated_path):
             # Resolve relative to the script *this node lives in*. If it's inside a group,
             # this might be complex. Safest is to resolve relative to root script.
             script_dir = os.path.dirname(nuke.root().name())
             evaluated_path = os.path.abspath(os.path.join(script_dir, evaluated_path)).replace("\\", "/")

    except Exception as e:
        error_msg = f"Error getting render path for node '{node.fullName()}': {e}\n{traceback.format_exc()}"
        print(f"  Error getting render path: {error_msg}") # Print error clearly

    return evaluated_path, error_msg


# --- Action: Get Write Nodes ---
def get_write_nodes_action():
    """Finds all relevant Write and WriteFix nodes."""
    writes = []
    nodes = nuke.allNodes(recurseGroups=True)
    print(f"Checking {len(nodes)} total nodes for writes...")
    count = 0
    for node in nodes:
        is_write = False
        node_class = node.Class()
        if node_class in WRITE_NODE_CLASSES:
             is_write = True
        elif is_valid_writefix(node): # Check our specific WriteFix conditions
             is_write = True

        if is_write:
            # Optionally check if the write node is disabled
            disable_knob = node.knob('disable')
            if disable_knob and disable_knob.value():
                 print(f"  Ignoring disabled write node: {node.fullName()}")
                 continue
            print(f"  Found valid write node: {node.fullName()} (Class: {node_class})")
            writes.append(node.fullName())
            count += 1
    print(f"Found {count} valid write nodes.")
    return {"write_nodes": writes}

# --- Action: Get Render Path ---
def get_render_path_action(node_name):
    """Gets the resolved render path for a single write node."""
    node = nuke.toNode(node_name)
    if not node:
        print(f"Error: Node '{node_name}' not found.")
        return {"node_name": node_name, "render_path": None, "error": f"Node '{node_name}' not found."}

    path, error = _get_render_path_internal(node)
    if error: print(f"Error retrieving render path for {node_name}: {error}")
    return {
        "node_name": node_name,
        "render_path": path,
        "error": error # Will be None if successful
    }

# --- Action: Get Dependencies (Recursive) ---
def get_all_dependent_nodes_action(target_node_names):
    """Finds all upstream nodes connected to the target nodes."""
    if not target_node_names:
        print("Error: No target node names provided for dependency trace.")
        return {"dependent_nodes": [], "error": "No target node names provided."}

    all_deps = set()
    nodes_to_process = []
    initial_targets_found = 0

    print(f"Starting dependency trace from {len(target_node_names)} target(s)...")
    for name in target_node_names:
        node = nuke.toNode(name)
        if node:
            nodes_to_process.append(node)
            all_deps.add(node.fullName()) # Include target nodes themselves
            initial_targets_found += 1
        else:
            print(f"Warning: Target node '{name}' not found for dependency trace.")

    if initial_targets_found == 0:
         print("Error: None of the specified target nodes were found.")
         return {"dependent_nodes": [], "error": "None of the specified target nodes were found."}

    # Limit recursion depth to prevent infinite loops in complex/broken scripts
    MAX_DEPTH = 1000 # Maximum number of nodes to process in queue (safety break)
    processed_nodes = set() # Keep track of nodes already visited

    nodes_processed_count = 0
    while nodes_to_process and nodes_processed_count < MAX_DEPTH:
        current_node = nodes_to_process.pop(0) # FIFO queue
        current_name = current_node.fullName()

        if current_name in processed_nodes:
            continue
        processed_nodes.add(current_name)
        nodes_processed_count += 1

        # print(f"  Tracing dependencies for: {current_name}") # Can be very verbose

        # Include expression links, but be aware they can cause issues/slowness
        try:
            # Get standard connected inputs first
            dependencies = current_node.dependencies(nuke.INPUTS | nuke.HIDDEN_INPUTS)
            # Optionally add expression dependencies - use with caution
            try:
               # dependencies() can fail on certain node types or expressions
               expression_deps = current_node.dependencies(nuke.EXPRESSIONS)
               if expression_deps:
                    # print(f"    Found {len(expression_deps)} expression dependencies for {current_name}") # Verbose
                    dependencies.extend(expression_deps)
            except Exception as expr_e:
               # Don't print warning for every node, maybe just once?
               # print(f"Warning: Could not get expression dependencies for {current_name}: {expr_e}")
               pass # Silently ignore expression errors for now

            # Use set for efficient adding and uniqueness check
            unique_new_deps = set()
            for dep_node in dependencies:
                if not dep_node: continue # Skip if dependency is None

                dep_name = dep_node.fullName()
                # Add to overall set and check if it needs processing
                if dep_name not in all_deps:
                    all_deps.add(dep_name)
                    unique_new_deps.add(dep_node) # Add node object

            # Add newly found unique dependencies to the processing queue
            nodes_to_process.extend(list(unique_new_deps))

        except Exception as e:
             print(f"Error getting dependencies for node '{current_name}': {e}\n{traceback.format_exc()}")
             # Continue processing other nodes even if one fails

    if nodes_processed_count >= MAX_DEPTH:
        print(f"Warning: Dependency trace reached maximum processing limit ({MAX_DEPTH}). Result may be incomplete.")

    print(f"Dependency trace complete. Found {len(all_deps)} total dependent nodes.")
    return {"dependent_nodes": sorted(list(all_deps))}

# --- Action: Get Backdrops ---
def get_backdrops_action(node_names):
    """Finds backdrops containing any of the specified nodes."""
    if not node_names:
        print("No node names provided to find associated backdrops.")
        return {"backdrops": []}

    target_nodes = []
    for name in node_names:
        node = nuke.toNode(name)
        if node:
            target_nodes.append(node)
        else:
            print(f"Warning: Node '{name}' not found while searching for backdrops.")

    if not target_nodes:
        print("None of the specified nodes found. Cannot find backdrops.")
        return {"backdrops": []}

    all_bd_nodes = nuke.allNodes('BackdropNode', recurseGroups=True)
    containing_backdrops = set()

    print(f"Checking {len(all_bd_nodes)} backdrops for association with {len(target_nodes)} target nodes...")

    # Pre-calculate node geometries once
    node_geometries = {}
    for node in target_nodes:
        try:
            # Use screenWidth/Height which might be more reliable after node placement changes
            nw = node.screenWidth() or 80 # Provide a default non-zero width
            nh = node.screenHeight() or 18 # Provide a default non-zero height
            nx = node.xpos()
            ny = node.ypos()
            node_geometries[node.fullName()] = (nx, ny, nw, nh)
        except ValueError:
            print(f"Warning: Could not get geometry info for node {node.fullName()}")

    if not node_geometries:
         print("Could not get geometry for any target nodes. Cannot associate backdrops.")
         return {"backdrops": []}

    for bd in all_bd_nodes:
        try:
            # backdrop coordinates
            bx = bd.xpos()
            by = bd.ypos()
            bw = bd['bdwidth'].value()
            bh = bd['bdheight'].value()
            bl, br, bt, bb = bx, bx + bw, by, by + bh

            # Check nodes associated with this backdrop
            for node_name, (nx, ny, nw, nh) in node_geometries.items():
                 # Check if node center point is within backdrop bounds
                 node_center_x = nx + nw / 2.0
                 node_center_y = ny + nh / 2.0

                 # Check inclusion: left <= center_x < right AND top <= center_y < bottom
                 if bl <= node_center_x < br and bt <= node_center_y < bb:
                     containing_backdrops.add(bd.fullName())
                     # print(f"  Node {node_name} is inside backdrop {bd.fullName()}") # Verbose
                     # Optimization: Once a backdrop is found containing *any* target node, add it and break inner loop
                     break # Move to the next backdrop node
        except (ValueError, TypeError): # Catch potential errors getting bd values
             print(f"Warning: Could not get geometry for backdrop {bd.fullName()}. Skipping.")
             continue

    found_count = len(containing_backdrops)
    print(f"Found {found_count} associated backdrops.")
    return {"backdrops": sorted(list(containing_backdrops))}

# --- Action: Save Pruned Script ---
def save_pruned_action(node_names_to_keep, output_path):
    """Copies specified nodes to a new script and saves it."""
    if not node_names_to_keep:
        print("Error: No node names provided to keep for pruning.")
        return {"error": "No node names provided to keep.", "saved_path": None}

    print(f"Attempting to prune script, keeping {len(node_names_to_keep)} nodes.")

    # --- IMPORTANT: Nuke's clipboard functions work on the *current* script state.
    # We need the original script loaded when this action is called.
    # The caller (utils.run_nuke_action) ensures the original script is loaded first.

    try:
        # Deselect all first to ensure clean selection state
        for n in nuke.allNodes(recurseGroups=True): n.setSelected(False)

        # Select the nodes to keep
        nodes_selected_count = 0
        missing_nodes = []
        for name in node_names_to_keep:
            node = nuke.toNode(name)
            if node:
                try:
                     node.setSelected(True)
                     nodes_selected_count += 1
                except Exception as sel_e:
                     print(f"Warning: Could not select node '{name}': {sel_e}")
            else:
                print(f"Warning: Node '{name}' not found during selection for pruning.")
                missing_nodes.append(name)

        if nodes_selected_count == 0:
             err_msg = f"None of the specified nodes to keep were found or could be selected."
             if missing_nodes: err_msg += f" Missing: {missing_nodes}"
             print(f"Error: {err_msg}")
             return {"error": err_msg, "saved_path": None}

        print(f"Selected {nodes_selected_count} nodes for copying.")

        # Copy selected nodes to clipboard
        nuke.nodeCopy('%clipboard%')

        # Create a new, empty script *in memory* by clearing the current state
        nuke.scriptClear()
        print("Cleared current script state.")

        # Paste the nodes into the new empty script state
        # Note: Pasting might re-select nodes, which is usually fine.
        pasted_nodes = nuke.nodePaste('%clipboard%')

        # Check if pasting actually added nodes (more robust check)
        if not nuke.allNodes(): # Check if the root context has nodes now
            print("Error: Pasting nodes failed. The new script state is empty after paste.")
            return {"error": "Failed to paste nodes into new script state.", "saved_path": None}

        print(f"Pasted nodes into new script state (nuke.nodePaste returned: {type(pasted_nodes)}).")

        # Save the new script state to the specified path
        print(f"Attempting to save pruned script to: {output_path}")
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                print(f"Created output directory: {output_dir}")
            except OSError as e:
                 raise OSError(f"Failed to create output directory '{output_dir}': {e}") from e

        nuke.scriptSaveAs(filename=output_path, overwrite=1)
        # Verify file was actually written and has content
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
             raise RuntimeError(f"scriptSaveAs executed but output file '{output_path}' is missing or empty.")

        print(f"Successfully saved pruned script to: {output_path}")
        return {"saved_path": output_path, "error": None}

    except Exception as e:
        error_msg = f"Error during pruned script save process: {e}\n{traceback.format_exc()}"
        print(error_msg)
        return {"error": error_msg, "saved_path": None}

# --- Action: Parse Dependencies ---
def parse_dependencies_action(frame_range_override_str=None):
    """Parses file dependencies from the *currently loaded* script."""
    dependency_manifest = {}
    # Assumes the script (original or pruned) is already loaded
    nodes_to_parse = nuke.allNodes(recurseGroups=True)
    print(f"Parsing dependencies for {len(nodes_to_parse)} nodes in current script...")

    # Parse frame range override string ("start-end" or "frame")
    frame_range_override = None
    if frame_range_override_str:
         try:
              if '-' in frame_range_override_str:
                   start, end = map(int, frame_range_override_str.split('-'))
              else:
                   start = end = int(frame_range_override_str)
              frame_range_override = (start, end)
              print(f"Using frame range override: {frame_range_override}")
         except ValueError:
              print(f"Warning: Invalid frame range override format '{frame_range_override_str}'. Ignoring.")

    parsed_count = 0
    for node in nodes_to_parse:
        node_name = node.fullName()
        node_class = node.Class()
        # Define classes or specific knobs that hold file paths
        # Expand this list as needed
        applicable_classes = READ_NODE_CLASSES + WRITE_NODE_CLASSES # Check writes too for LUTs etc.

        if node_class in applicable_classes:
            # print(f"Processing node: {node_name} (Class: {node_class})") # Verbose
            file_knob = node.knob("file")
            proxy_knob = node.knob("proxy")
            # Add checks for other common file knobs
            other_file_knobs = {}
            if node_class == "OCIOFileTransform": other_file_knobs['cccid'] = node.knob('cccid')
            if node_class == "Vectorfield": other_file_knobs['vfield_file'] = node.knob('vfield_file')
            # Add more specific knobs here based on plugins/gizmos used

            knobs_to_check = {'file': file_knob, 'proxy': proxy_knob, **other_file_knobs}

            for knob_name, knob_instance in knobs_to_check.items():
                if not knob_instance: continue # Skip if knob doesn't exist

                error_msg = None
                evaluated_path = None
                original_path = None

                try:
                    original_path = knob_instance.value()
                    if not original_path:
                        # print(f"  Node '{node_name}' knob '{knob_name}' is empty. Skipping.") # Verbose
                        continue # Skip empty knobs

                    evaluated_path = knob_instance.evaluate()
                    # print(f"  Knob '{knob_name}' Original Path: {original_path}") # Verbose
                    # print(f"  Knob '{knob_name}' Evaluated Path: {evaluated_path}") # Verbose

                    if not evaluated_path:
                         # Path evaluated to empty string, could be intentional or error
                         print(f"  Warning: Evaluated path for '{node_name}.{knob_name}' is empty. Original: '{original_path}'")
                         # Decide if we should still record this? Let's skip if evaluated is empty.
                         continue
                         # evaluated_path = original_path # Or Fallback? Skipping seems safer.

                    # Make absolute if relative, use forward slashes
                    if not os.path.isabs(evaluated_path):
                         script_dir = os.path.dirname(nuke.root().name()) # Path of current script
                         abs_eval_path = os.path.abspath(os.path.join(script_dir, evaluated_path)).replace("\\", "/")
                         # print(f"  Relative path resolved to: {abs_eval_path}") # Verbose
                         evaluated_path = abs_eval_path
                    else:
                         # Ensure consistent separators even if absolute
                         evaluated_path = evaluated_path.replace("\\", "/")


                except Exception as e:
                    error_msg = f"Error evaluating '{knob_name}' knob for '{node_name}': {e}"
                    print(f"  Error evaluating knob: {error_msg}") # Log clearly
                    # Still record the entry with the error? Yes.

                # Skip if evaluated path ended up invalid after potential resolution/error
                if not evaluated_path and not error_msg: continue

                # Frame range logic - Apply ONLY to 'file' knob sequences typically
                first_frame, last_frame = None, None
                frame_range_source = None
                # More robust sequence check (handles different padding styles)
                is_seq = ('%' in (evaluated_path or '')) or \
                         ('#' in (evaluated_path or '')) or \
                         ('$F' in (evaluated_path or '')) and \
                         knob_name == 'file' # Usually only 'file' knobs are sequences

                if is_seq:
                    # Try reading frame range knobs from the node
                    first_knob = node.knob("first")
                    last_knob = node.knob("last")
                    use_limit_knob = node.knob("use_limit")
                    use_limit = use_limit_knob.value() if use_limit_knob else True # Assume used if absent

                    if first_knob and last_knob and use_limit:
                        try:
                            first_frame = int(first_knob.value())
                            last_frame = int(last_knob.value())
                            # Basic sanity check
                            if last_frame < first_frame:
                                 print(f"Warning: Node '{node_name}' frame range has last < first ({first_frame}-{last_frame}). Using as is.")
                            frame_range_source = "node_knobs"
                        except ValueError: pass # Ignore if knobs invalid

                    # Apply override if available and valid
                    if frame_range_override:
                        first_frame, last_frame = frame_range_override
                        frame_range_source = "override"
                    elif first_frame is None: # If no valid knobs and no override
                        frame_range_source = "scan_required" # Mark for later disk scan

                # Use a unique key for the manifest based on node and knob
                manifest_key = f"{node_name}.{knob_name}"
                dependency_manifest[manifest_key] = {
                    "node_name": node_name,
                    "knob_name": knob_name,
                    "node_class": node_class,
                    "original_path": original_path,
                    "evaluated_path": evaluated_path,
                    "first_frame": first_frame,
                    "last_frame": last_frame,
                    "frame_range_source": frame_range_source,
                    "evaluation_error": error_msg,
                    "is_sequence": is_seq,
                }
                parsed_count += 1

    print(f"Finished parsing dependencies. Found {parsed_count} file references.")
    return {"dependency_manifest": dependency_manifest}


# --- Action: Bake Gizmos ---
def bake_gizmos_action(output_path):
    """Bakes non-native gizmos in the *currently loaded* script and saves to output_path."""
    baked_count = 0
    native_plugins = set()
    try:
        native_plugins = set(nuke.plugins(nuke.ALL | nuke.NODIR))
        print(f"Found {len(native_plugins)} native Nuke plugins/node classes for exclusion check.")
    except Exception as e:
        print(f"Warning: Could not get native plugins list: {e}. Gizmo exclusion check might be less accurate.")

    # Operate on the currently loaded script state
    nodes_to_check = nuke.allNodes(recurseGroups=True)
    print(f"Checking {len(nodes_to_check)} nodes for potential gizmo baking...")

    processed_nodes_for_baking = set() # Avoid trying to bake a node created by baking earlier

    for node in nodes_to_check:
        node_name = node.fullName()
        if node_name in processed_nodes_for_baking: continue

        node_class = node.Class()
        can_be_baked = hasattr(node, 'makeGroup')

        if not can_be_baked: continue # Cannot bake if no makeGroup method

        # --- Refined Gizmo Identification & Exclusion ---
        is_gizmo_file_based = node.knob('gizmo_file') is not None
        is_likely_native = node_class in native_plugins

        is_target_gizmo = False
        if is_gizmo_file_based:
             # Check if it's in the default Nuke plugins directory structure
             in_nuke_plugins_dir = False
             try:
                  gizmo_filename = node.filename()
                  if gizmo_filename:
                       nuke_exec_dir = Path(nuke.env['ExecutablePath']).parent
                       # Check relative to the Nuke installation directory more broadly
                       if Path(gizmo_filename).is_relative_to(nuke_exec_dir / 'plugins'):
                            in_nuke_plugins_dir = True
                       # Also consider user's .nuke directory? Might be too broad.
                       # user_nuke_dir = Path.home() / ".nuke"
                       # if Path(gizmo_filename).is_relative_to(user_nuke_dir):
                       #     in_nuke_plugins_dir = True # Or maybe treat user gizmos as bakeable? Decide policy.
             except Exception as path_e:
                  print(f"Warning: Error checking path for gizmo {node_name}: {path_e}")

             if not in_nuke_plugins_dir:
                  is_target_gizmo = True # File-based and not in default Nuke plugins
             else:
                  print(f"  Skipping default/plugin path gizmo: {node_name}")
        elif not is_likely_native:
             # It's not file-based and not in the native list - could be C++ plugin or internal group?
             # Baking these might be undesirable or impossible. Let's skip non-file-based for safety.
             print(f"  Skipping non-file-based, non-native node (might be C++ plugin): {node_name} (Class: {node_class})")


        if is_target_gizmo:
             print(f"Found non-native gizmo to bake: {node_name} (Class: {node_class})")
             try:
                 # Deselect all before baking - safer?
                 for n in nuke.allNodes(recurseGroups=True): n.setSelected(False)
                 node.setSelected(True) # Select the target node

                 # Perform the bake using makeGroup()
                 baked_group = node.makeGroup()

                 if baked_group:
                     print(f"  Successfully baked '{node_name}' to Group '{baked_group.fullName()}'")
                     baked_count += 1
                     # Add the new group to the processed set to avoid processing it again
                     processed_nodes_for_baking.add(baked_group.fullName())
                 else:
                     # makeGroup can return None if it fails
                     print(f"  Warning: Failed to bake gizmo '{node_name}'. makeGroup() returned None.")

             except Exception as bake_error:
                 print(f"  Error baking gizmo '{node_name}': {bake_error}\n{traceback.format_exc()}")
             finally:
                 # Ensure node is deselected after attempt
                 try: node.setSelected(False)
                 except: pass # Node might have been replaced

    # --- Saving ---
    if baked_count > 0:
        # Save the *current Nuke state* (which now contains baked groups)
        print(f"Saving script with {baked_count} baked gizmos to: {output_path}")
        try:
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            nuke.scriptSaveAs(filename=output_path, overwrite=1)
            # Verify save
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                raise RuntimeError(f"scriptSaveAs executed but output file '{output_path}' is missing or empty.")

            print("Baked script saved successfully.")
            return {"baked_script_path": output_path, "baked_count": baked_count, "error": None}
        except Exception as e:
            error_msg = f"Failed to save baked script: {e}\n{traceback.format_exc()}"
            print(error_msg)
            return {"baked_script_path": None, "baked_count": baked_count, "error": error_msg}
    else:
        print("No non-native gizmos found requiring baking. No new script saved.")
        return {"baked_script_path": None, "baked_count": 0, "error": None}


# --- Main Execution Logic (Inside Nuke) ---
def main():
    # Argument parser for actions within Nuke
    parser = argparse.ArgumentParser(description="Nuke Operations for Fix Archive")
    parser.add_argument("--action", required=True, nargs='+', help="Action(s) to perform",
                        choices=['get_writes', 'get_render_path', 'get_deps', 'get_backdrops', 'save_pruned', 'parse', 'bake'])
    parser.add_argument("--script-path", help="Path to the Nuke script to load (required for most actions)")
    parser.add_argument("--target-nodes", nargs='*', help="List of target node names (for get_deps, get_backdrops, save_pruned)")
    parser.add_argument("--node-name", help="Single node name (for get_render_path)")
    parser.add_argument("--output-path", help="Output file path (for save_pruned, bake)")
    parser.add_argument("--frame-range", help="Frame range override for parsing (e.g., 1001-1100 or 1050)")

    args = parser.parse_args() # Parses args passed via run_nuke_action

    results = {}
    script_loaded = False
    loaded_script_path = None # Track the path currently considered loaded in Nuke state

    # --- Script Loading ---
    # Determine if *any* action requires a script to be loaded initially.
    actions_requiring_load = ['get_writes', 'get_deps', 'get_backdrops', 'save_pruned', 'parse', 'bake']
    load_is_needed = any(action in args.action for action in actions_requiring_load)

    if load_is_needed:
        if not args.script_path:
             results["fatal_error"] = f"--script-path is required for action(s): {args.action}"
             # Print error and exit immediately if essential input missing
             print(results["fatal_error"])
             print(json.dumps(results))
             sys.exit(1)

        script_to_load = args.script_path
        if os.path.exists(script_to_load):
            try:
                print(f"Loading script for actions: {script_to_load}")
                nuke.scriptClear() # Clear any existing state first
                nuke.scriptOpen(script_to_load)
                script_loaded = True
                loaded_script_path = script_to_load
                print("Script loaded successfully.")
            except Exception as e:
                results["load_error"] = f"Failed to load script {script_to_load}: {e}\n{traceback.format_exc()}"
                # Exit early if script load fails, as subsequent actions depend on it
                print(results["load_error"])
                print(json.dumps(results))
                sys.exit(1)
        else:
            results["load_error"] = f"Script path not found: {script_to_load}"
            print(results["load_error"])
            print(json.dumps(results))
            sys.exit(1) # Exit if script not found


    # --- Execute actions sequentially ---
    # Actions operate on the *current* Nuke state. Some actions modify this state.
    for action_index, action in enumerate(args.action):
        print(f"\n--- Executing Action {action_index + 1}/{len(args.action)}: {action} ---")
        # Check if script should be loaded for this specific action
        if action in actions_requiring_load and not script_loaded:
             results[f"{action}_error"] = f"Required script ('{loaded_script_path or args.script_path}') is not loaded (previous step may have failed)."
             print(results[f"{action}_error"])
             continue # Skip this action if script isn't considered loaded

        try:
            action_result_data = None # Store result of the current action call

            if action == 'get_writes':
                action_result_data = get_write_nodes_action()
            elif action == 'get_render_path':
                if not args.node_name: raise ValueError("--node-name required for get_render_path.")
                action_result_data = get_render_path_action(args.node_name)
            elif action == 'get_deps':
                if not args.target_nodes: raise ValueError("--target-nodes required for get_deps.")
                action_result_data = get_all_dependent_nodes_action(args.target_nodes)
            elif action == 'get_backdrops':
                if not args.target_nodes: raise ValueError("--target-nodes required for get_backdrops.")
                action_result_data = get_backdrops_action(args.target_nodes)
            elif action == 'save_pruned':
                # This action modifies the current Nuke state (clears, pastes) and saves it.
                # Requires original script to be loaded when called.
                if loaded_script_path != args.script_path:
                     # Safety check: ensure the expected original script is loaded
                     raise RuntimeError(f"save_pruned action called, but Nuke state might not be the original script ({args.script_path}). Current state is based on '{loaded_script_path}'.")
                if not args.target_nodes: raise ValueError("--target-nodes required for save_pruned.")
                if not args.output_path: raise ValueError("--output-path required for save_pruned.")
                action_result_data = save_pruned_action(args.target_nodes, args.output_path)
                # Update state tracking if successful
                if action_result_data.get('saved_path'):
                     loaded_script_path = action_result_data['saved_path'] # Nuke state is now the pruned script
                     script_loaded = True
                else:
                     script_loaded = False # Saving failed, state uncertain
            elif action == 'parse':
                 # Operates on the currently loaded script state (original or pruned or baked)
                 action_result_data = parse_dependencies_action(args.frame_range)
            elif action == 'bake':
                 # Operates on the currently loaded script state, saves potentially modified version
                 if not args.output_path: raise ValueError("--output-path required for bake.")
                 action_result_data = bake_gizmos_action(args.output_path)
                 # Update state tracking if successful bake occurred
                 if action_result_data.get('baked_script_path'):
                      loaded_script_path = action_result_data['baked_script_path']
                      script_loaded = True
                 elif action_result_data.get('error'):
                      script_loaded = False # Baking failed, state uncertain

            # Store the result for this action
            results[action] = action_result_data
            print(f"--- Action '{action}' completed ---")

        except Exception as e:
            # Catch errors during the action call itself
            error_key = f"{action}_error"
            results[error_key] = f"Critical error during action '{action}': {e}\n{traceback.format_exc()}"
            print(results[error_key])
            # Stop processing further actions in this run if one critically fails? Safer.
            print("Stopping further actions due to critical error.")
            script_loaded = False # Mark state as uncertain
            break # Exit the action loop

    # --- Final Output ---
    print("\n--- NUKE OPS FINAL RESULTS ---")
    try:
        # Include the path of the script reflecting the final Nuke state
        results["final_script_state_path"] = loaded_script_path if script_loaded else None
        print(json.dumps(results, indent=2))
    except TypeError as e:
        print(f"Error serializing results: {e}")
        # Attempt to serialize with errors replaced for debugging
        print(json.dumps(results, indent=2, default=lambda o: f"<not serializable: {type(o)}>"))

    print("--- NUKE OPS SCRIPT END ---")

if __name__ == "__main__":
    exit_code = 1 # Default to error
    try:
        main()
        exit_code = 0 # Set to success if main completes without exception
    except Exception as e:
        # Catch unexpected errors in main or arg parsing
        print("--- NUKE OPS FATAL ERROR ---")
        print(f"An unexpected error occurred in main execution: {e}\n{traceback.format_exc()}")
        try:
            # Try to output JSON even on fatal error
            print(json.dumps({"fatal_error": str(e)}, indent=2))
        except Exception:
             # Fallback if error itself can't be serialized
             print(f'{{"fatal_error": "Failed to serialize fatal error: {str(e)}"}}')
    finally:
         # Ensure Nuke exits with the determined code
         print(f"Exiting Nuke with code {exit_code}")
         # nuke.scriptExit() # Might interfere with stdout/stderr capture?
         sys.exit(exit_code) # Use standard Python exit