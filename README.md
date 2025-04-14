# Fix Archive Tool

A tool for archiving Nuke scripts and their dependencies.

## Installation

1. Clone this repository
2. Install the package:
   ```
   pip install -e .
   ```

## Usage

### Using the Command-Line Wrapper

The easiest way to use the Fix Archive tool is with the command-line wrapper:

#### On Windows:
```
fixarchive.bat [args]
```

#### On Unix-like systems (Linux, macOS):
```
./fixarchive.sh [args]
```

#### Using the Python wrapper (works on all platforms):
```
python fixarchive [args]
```

### Using the Module Directly

You can also run the tool directly as a Python module:

```
python -m fix-archive.cli [args]
```

### Example

```
fixarchive "Z:/proj/bob01/shots/BOB_100/BOB_100_000/BOB_100_000_050_MTS/publish/nuke/BOB_100_000_050_MTS_Comp_v007.nk" \
    --archive-root "W:\proj\bob01\delivery\archive" \
    --vendor "FixFX"
```

## Command-Line Arguments

- `script_path`: Path to the source Nuke script (.nk) to archive.
- `--archive-root`: Root directory where the archive structure will be created.
- `--vendor`: Vendor name (e.g., '123 VFX Company').
- `--show`: Show name (e.g., 'EXAMPLE').
- `--season`: Season identifier (e.g., 'Season 1', '1').
- `--episode`: Episode identifier (e.g., '100', 'E01').
- `--shot`: Shot identifier (e.g., 'EXA100_010_010').
- `--bake-gizmos`: Bake non-native gizmos into Group nodes before archiving.
- `--update-script`: Save the final archived Nuke script with repathed file nodes.
- `--frame-range`: Specify frame range for sequences (e.g., '1001-1100' or '1050').
- `--report-json`: Write a JSON manifest detailing the archive process and file mappings.
- `--dry-run`: Simulate the process without copying files or writing the final script/report.
- `-v, --verbose`: Increase logging verbosity (-v for INFO, -vv for DEBUG).
- `--version`: Show the version and exit.

## Making the Wrapper Executable

### On Unix-like systems (Linux, macOS):

1. Make the wrapper executable:
   ```
   chmod +x fixarchive.sh
   ```

2. Create a symbolic link in a directory that's in your PATH:
   ```
   ln -s /path/to/fixarchive.sh /usr/local/bin/fixarchive
   ```

### On Windows:

1. Add the directory containing `fixarchive.bat` to your PATH environment variable.

2. Or create a shortcut to `fixarchive.bat` on your desktop or in a convenient location.

## Overview

`fix-archive` is a command-line utility designed for the FixFX pipeline to reliably prepare Nuke scripts (`.nk`) and their associated file dependencies for archival or final delivery. It automates the process of:

1.  **Identifying Target Outputs:** Locating specified or all valid output nodes (`Write`, `WriteFix`, etc.) within the Nuke script.
2.  **Pruning the Script:** Tracing dependencies backwards from the target outputs to identify only the necessary nodes (including relevant Backdrops) required for the render.
3.  **Saving a Cleaned Script:** Creating a new, temporary `.nk` file containing only the essential nodes.
4.  **Parsing Dependencies:** Analyzing the *pruned* script to identify all external file inputs (Read nodes, geometry, LUTs, etc.) required by the essential nodes.
5.  **Collecting & Validating Dependencies:** Locating these required files and verifying their existence.
6.  **Structuring Archive:** Creating a clean, standardized output directory based on delivery specifications (specifically targeting **SPT Post Production Guide v3.2.0, Section 3.5.2**).
7.  **Copying Files:** Copying the *pruned* script and all its *required* dependencies into the designated archive structure.
8.  **(Optionally) Baking Gizmos:** Converting non-native `.gizmo` nodes into standard Nuke `Group` nodes within the *pruned and archived* script.
9.  **(Optionally) Repathing Files:** Modifying file paths within the *pruned and archived* Nuke script to be relative to its new location within the archive structure.

The primary goal is to create self-contained, minimal, easily understandable, and specification-compliant packages for long-term storage or delivery.

## Use Case

This tool is essential for:

*   **Final Delivery:** Packaging shots or sequences according to client or studio delivery standards (like SPT), ensuring only necessary data is included.
*   **Project Archival:** Creating lean, robust backups of completed work.
*   **Handoffs:** Preparing minimal project components for transfer.
*   **Cleanup:** Generating simplified versions of complex scripts for review or specific tasks.

## Core Features

*   **Targeted Pruning:** Identifies final write nodes and traces dependencies backwards to include only necessary nodes and associated backdrops.
*   **Clean Script Generation:** Saves a new temporary script containing only the essential node graph.
*   **Contextual Dependency Parsing:** Analyzes the *pruned* script to find required files via the Nuke Python API (`nuke -t`).
*   **SPT v3.2.0 Structure:** Creates the standardized folder hierarchy (`{Vendor}/{Show}/{Season}/{Episode}/{Shot}/elements/`, `project/nuke/`, etc.).
*   **Metadata Driven:** Uses show, episode, shot, etc., metadata (inferred from the source path via `fixfx.data` or provided via CLI) to build the correct archive structure.
*   **Relative Repathing (Optional):** Modifies file paths within the final archived script.
*   **Gizmo Baking (Optional):** Converts non-native gizmos within the final archived script.
*   **Reporting (Optional):** Generates a JSON manifest mapping original dependency paths to their final archived locations.
*   **Dry Run Mode:** Simulates the entire process without modifying the filesystem.
*   **Logging:** Comprehensive logging provided by `fixfx.core.logger` (or basic fallback).

## The Archival Process (Revised)

1.  **Input & Configuration:** Parses CLI args (`script_path`, `--archive-root`, options), infers/validates metadata (using `fixfx.data` if available).
2.  **Identify Writes & Dependencies (`prune.py` -> `utils.run_nuke_action` -> `nuke_ops.py`):**
    *   Executes `nuke -t` loading the *original* script.
    *   `nuke_ops.py` identifies target `Write`/`WriteFix` nodes.
    *   Traces dependencies backwards (`node.dependencies()`) from targets.
    *   Identifies associated `BackdropNode`s.
    *   Returns a list of `nodes_to_keep`.
3.  **Save Pruned Script (`prune.py` -> `utils.run_nuke_action` -> `nuke_ops.py`):**
    *   Executes `nuke -t` loading the *original* script again.
    *   `nuke_ops.py` selects `nodes_to_keep`, performs `nuke.nodeCopy()`, `nuke.scriptClear()`, `nuke.nodePaste()`.
    *   Saves the *new, pruned* script state to a temporary file (`pruned_script_path_temp`).
4.  **Parse Pruned Dependencies (`parser.py` -> `utils.run_nuke