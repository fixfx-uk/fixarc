# Fix Archive Tool (`fixarc`)

**Version:** 0.2.0

## Overview

`fixarc` is a command-line utility designed for the FixFX pipeline to reliably prepare Nuke scripts (`.nk`) and their associated file dependencies for archival or final delivery. It streamlines the process into a single Nuke execution followed by robust file copying.

**Key Steps:**

1.  **Identify Target Outputs & Dependencies:** Loads the original Nuke script, identifies final write nodes, and traces all upstream dependencies (nodes required for the output). Includes associated backdrops.
2.  **In-Memory Processing (Optional):**
    *   **Bake Gizmos:** If requested (`--bake-gizmos`), converts non-native gizmos within the required node set into standard Nuke Groups.
    *   **Repath Files:** If requested (`--update-script`), calculates the final destination paths for dependencies within the archive and modifies the file paths on the required nodes *in memory* to be relative to the final script location.
3.  **Save Pruned/Processed Script:** Selects only the required (and potentially baked/repathed) nodes and saves this *minimal* script directly to its final calculated destination within the archive structure (e.g., `.../{shot}/project/nuke/{shot}_archive.nk`).
4.  **Collect Dependency Map:** The Nuke process determines the mapping between the original absolute paths of all required dependencies and their intended final absolute paths within the archive structure.
5.  **Robust File Copying:** After the Nuke process completes successfully, the main Python script uses the dependency map to copy the required source files/sequences to their final archive locations using efficient tools like `robocopy` (Windows) or `rsync` (Linux/Mac), with a fallback to standard Python copying.

The primary goal is to create self-contained, minimal, efficiently processed, and specification-compliant packages (targeting **SPT Post Production Guide v3.2.0**) for long-term storage or delivery.

## Use Case

*   **Final Delivery:** Packaging shots/sequences according to SPT or client standards with minimal necessary data.
*   **Project Archival:** Creating lean, robust backups.
*   **Handoffs:** Transferring minimal project components.
*   **Cleanup:** Generating simplified script versions.

## Core Features

*   **Targeted Pruning:** Identifies final writes, traces dependencies, includes backdrops.
*   **Single Nuke Session:** Performs pruning, optional baking, optional repathing, and saving in one `nuke -t` call for efficiency.
*   **Direct Archive Save:** Saves the final processed script directly to its archive location.
*   **Accurate Dependency Collection:** Gathers required file paths *before* repathing occurs.
*   **Robust File Copying:** Uses `robocopy`/`rsync` where available for efficient and reliable transfer of dependencies.
*   **SPT v3.2.0 Structure:** Creates the standardized folder hierarchy.
*   **Metadata Driven:** Uses metadata (inferred or CLI) for structure.
*   **Relative Repathing (Optional):** Modifies paths *before* saving the final script.
*   **Gizmo Baking (Optional):** Bakes gizmos *before* repathing/saving.
*   **Reporting (Optional):** Generates JSON manifest.
*   **Dry Run Mode:** Simulates Nuke processing and file mapping, skips saving and copying.
*   **Logging:** Comprehensive logging.

## The Archival Process (Streamlined)

1.  **CLI Input & Config:** Parses args, prepares metadata.
2.  **Execute Nuke Process (`cli.py` -> `utils.execute_nuke_archive_process` -> `_nuke_executor.py`):**
    *   `nuke -t` is launched with `_nuke_executor.py`.
    *   **Load Original Script.**
    *   **Find Writes & Trace Dependencies:** Identifies required nodes (`Write` -> upstream -> backdrops).
    *   **Collect Original Paths:** Records evaluated absolute paths of dependencies needed by required nodes.
    *   **Bake Gizmos (Optional):** Executes `node.makeGroup()` on required non-native gizmos *in memory*.
    *   **Calculate Final Paths & Repath (Optional):** If `--update-script`, determines final archive locations for script & dependencies, calculates relative paths, and updates node knobs *in memory*.
    *   **Save Final Script:** Selects required nodes (now potentially baked/repathed) and saves the current Nuke state *directly* to the calculated final archive path (e.g., `.../project/nuke/SHOT_archive.nk`).
    *   **Output JSON:** Prints JSON containing `{status, final_script_path, dependencies_to_copy{orig_abs: dest_abs}, errors}` to stdout.
3.  **Parse Nuke Results (`cli.py`):** Reads and parses the JSON output from the Nuke process. Checks for success status.
4.  **Copy Dependencies (`cli.py` -> `utils.copy_files_robustly`):**
    *   If Nuke process succeeded, iterates through the `dependencies_to_copy` map.
    *   Uses `robocopy`/`rsync`/`shutil` to copy each original dependency file/sequence to its specified final archive destination.
5.  **Reporting & Cleanup (`cli.py`):** Generates optional JSON report; no temporary script files to clean (unless Nuke crashes unexpectedly).

## Usage (Command Line Interface)

```bash
# Recommended: Use the wrapper script if provided
fixarc "path/to/script.nk" --archive-root "path/to/archive" --vendor "MyVendor" [options]

# Or run as module:
python -m fixarc.cli "path/to/script.nk" --archive-root "path/to/archive" --vendor "MyVendor" [options]