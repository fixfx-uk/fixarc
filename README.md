# Fix Archive Tool (`fixarc`)

**Version:** 1.0.0

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
```

### Examples

Below are examples using a hypothetical project structure on a Windows `W:` drive.

**Scenario:** Archive the Nuke script `BOB_101_002_030_CLN_Comp_v005.nk` for the shot `BOB_101_002_030` for vendor `FixFX`. The main project lives under `W:\proj\sandbox` and the target archive location is `W:\proj\sandbox\delivery\archive`.

**Using the wrapper script (recommended):**

```bash
fixarc "W:\proj\sandbox\shots\BOB_101\BOB_101_002\BOB_101_002_030_CLN\Comp\work\robin-d\nuke\BOB_101_002_030_CLN_Comp_v005.nk" --archive-root "W:\proj\sandbox\delivery\archive" --vendor "FixFX" --shot-name "BOB_101_002_030"
```

**Running as a Python module:**

```bash
python -m fixarc.cli "W:\proj\sandbox\shots\BOB_101\BOB_101_002\BOB_101_002_030_CLN\Comp\work\robin-d\nuke\BOB_101_002_030_CLN_Comp_v005.nk" --archive-root "W:\proj\sandbox\delivery\archive" --vendor "FixFX" --shot-name "BOB_101_002_030"
```

**Common Optional Flags:**

*   `--update-script`: Modifies the script to use relative paths pointing to the new archive locations.
*   `--bake-gizmos`: Converts gizmos to groups within the archived script.
*   `--frame-range 1001-1050`: Specifies a particular frame range to consider for sequence dependencies.
*   `--report`: Generates a JSON report of the archival process.
*   `--dry-run`: Simulates the process without actually copying files or saving the script. Useful for testing.
*   `--log-level DEBUG`: Sets the logging level for more detailed output.

**Example with optional flags (dry run, update script, bake gizmos):**
```bash
fixarc "W:\proj\sandbox\shots\BOB_101\BOB_101_002\BOB_101_002_030_CLN\Comp\work\robin-d\nuke\BOB_101_002_030_CLN_Comp_v005.nk" --archive-root "W:\proj\sandbox\delivery\archive" --vendor "FixFX" --shot-name "BOB_101_002_030" --update-script --bake-gizmos --dry-run
```

## Batch Archiving with `fixarc-handler`

The `fixarc-handler` script (typically found in the `bin` directory or accessible via system PATH if installed) provides a way to batch archive multiple Nuke scripts based on project, episode, sequence, or shot names. It intelligently finds published Nuke scripts within a specified project structure and then uses `fixarc` for the actual archiving process. It can also optionally submit these archiving jobs to a Deadline render farm.

### `fixarc-handler` Usage

The basic structure of the command is:

```bash
# General form (assuming fixarc-handler is in PATH or you are in its directory)
fixarc-handler --project <PROJECT_NAME> [--episode <EP_NAME>...] [--sequence <SEQ_NAME>...] [--shot <SHOT_NAME>...] --archive-root <PATH_TO_ARCHIVE> [options]

# If running directly via python:
python path/to/fixarc/bin/fixarc-handler --project <PROJECT_NAME> ...
```

**Key `fixarc-handler` Options:**

*   `--project PROJECT_NAME`: Specifies the project to operate on. If used alone, it attempts to archive all shots in that project. It's also required as context if using `--episode`, `--sequence`, or `--shot`.
*   `--episode EPISODE_NAME [EPISODE_NAME ...]`: Archives scripts from the specified episode(s) within the given `--project`.
*   `--sequence SEQUENCE_NAME [SEQUENCE_NAME ...]`: Archives scripts from the specified sequence(s) within the given `--project`.
*   `--shot SHOT_NAME [SHOT_NAME ...]`: Archives scripts from the specified shot(s) within the given `--project`.
*   `--archive-root ARCHIVE_ROOT_PATH`: **Required.** The root directory where the archives will be created (e.g., `W:\proj\sandbox\delivery\archive`).
*   `--base-path BASE_PROJECT_PATH`: Overrides the default project base path (e.g., `W:\proj`). If not set, it often relies on an environment variable like `FIXSTORE_DRIVE`.
*   `--max-versions N`: Number of latest published script versions to archive per shot. `0` means all versions, `1` (default) means only the latest, `N > 1` means the latest `N` versions.
*   `--client-config PATH_TO_CONFIG.json`: Path to a JSON configuration file for client-specific mappings (passed to `fixarc`).
*   `--farm`: Submits each `fixarc` process as a separate job to Deadline.
*   `--fixarc-options "OPTIONS_STRING"`: A quote-enclosed string of additional options to be passed directly to each `fixarc` call (e.g., `"--update-script --bake-gizmos"`).
*   `-v, -vv`: Increases logging verbosity.

### `fixarc-handler` Examples

The following examples demonstrate usage on different operating systems, using the hypothetical project "sandbox" located at `W:\proj\sandbox` (for Windows) or `/mnt/proj/sandbox` (for Linux/macOS), with an archive root of `W:\proj\sandbox\delivery\archive` or `/mnt/proj/sandbox/delivery/archive` respectively.

#### Windows Examples

**1. Archive the latest version of all published Nuke scripts for project "sandbox":**

This command will search for published Nuke scripts under `W:\proj\sandbox\sandbox\shots\...` (assuming `W:\proj\sandbox` is the base path) and archive the latest version of each found script to `W:\proj\sandbox\delivery\archive`.

```bash
fixarc-handler --project sandbox ^
    --archive-root "W:\proj\sandbox\delivery\archive" ^
    --base-path "W:\proj"
```

**2. Archive the latest 3 versions of published Nuke scripts for episode "BOB_101" of project "sandbox":**

This targets only scripts within the "BOB_101" episode structure (e.g., `W:\proj\sandbox\sandbox\shots\BOB_101\...`).

```bash
fixarc-handler --project sandbox --episode BOB_101 ^
    --archive-root "W:\proj\sandbox\delivery\archive" ^
    --base-path "W:\proj" ^
    --max-versions 3
```

**3. Archive all versions for specific shots "BOB_101_002_030_CLN" and "BOB_101_003_030_CLN" in project "sandbox", submit to farm, and pass custom `fixarc` options:**

This example demonstrates:
*   Targeting multiple specific shots.
*   Archiving all versions (`--max-versions 0`).
*   Submitting to Deadline (`--farm`).
*   Passing `--update-script` and `--bake-gizmos` to the underlying `fixarc` calls for each script.
*   Assuming `fixarc-handler` is run via python directly from its location within the `fixarc` package.

```bash
python C:\Users\robin.d\Documents\dev\pipe\fixarc\bin\fixarc-handler ^
    --project sandbox ^
    --shot BOB_101_002_030_CLN BOB_101_003_030_CLN ^
    --archive-root "W:\proj\sandbox\delivery\archive" ^
    --base-path "W:\proj" ^
    --max-versions 0 ^
    --farm ^
    --fixarc-options "--update-script --bake-gizmos --vendor FixFX"
```
Note: The `^` character is used for line continuation in Windows CMD. The paths and vendor are examples.

**4. Archive latest version for sequence "BOB_101_00X" using a client config and verbose logging:**

```bash
fixarc-handler --project sandbox --sequence BOB_101_00X ^
    --archive-root "W:\proj\sandbox\delivery\archive" ^
    --base-path "W:\proj" ^
    --client-config "W:\proj\sandbox\config\spt_config_v3.json" ^
    -vv
```
This assumes a client configuration file exists at the specified path.

#### Linux / macOS Examples

**1. Archive the latest version of all published Nuke scripts for project "sandbox":**

This command will search for published Nuke scripts under `/mnt/proj/sandbox/sandbox/shots/...` (assuming `/mnt/proj/sandbox` is the base path) and archive the latest version of each found script to `/mnt/proj/sandbox/delivery/archive`.

```bash
fixarc-handler --project sandbox \\
    --archive-root /mnt/proj/sandbox/delivery/archive \\
    --base-path /mnt/proj
```

**2. Archive the latest 3 versions of published Nuke scripts for episode "BOB_101" of project "sandbox":**

This targets only scripts within the "BOB_101" episode structure (e.g., `/mnt/proj/sandbox/sandbox/shots/BOB_101/...`).

```bash
fixarc-handler --project sandbox --episode BOB_101 \\
    --archive-root /mnt/proj/sandbox/delivery/archive \\
    --base-path /mnt/proj \\
    --max-versions 3
```

**3. Archive all versions for specific shots "BOB_101_002_030_CLN" and "BOB_101_003_030_CLN" in project "sandbox", submit to farm, and pass custom `fixarc` options:**

This example uses a generic path for the `fixarc-handler` script.

```bash
python /opt/fixarc/bin/fixarc-handler \\
    --project sandbox \\
    --shot BOB_101_002_030_CLN BOB_101_003_030_CLN \\
    --archive-root /mnt/proj/sandbox/delivery/archive \\
    --base-path /mnt/proj \\
    --max-versions 0 \\
    --farm \\
    --fixarc-options "--update-script --bake-gizmos --vendor FixFX"
```
Note: The `\\` character is used for line continuation in Bash/Shell. The paths and vendor are examples.

**4. Archive latest version for sequence "BOB_101_00X" using a client config and verbose logging:**

```bash
fixarc-handler --project sandbox --sequence BOB_101_00X \\
    --archive-root /mnt/proj/sandbox/delivery/archive \\
    --base-path /mnt/proj \\
    --client-config /mnt/proj/sandbox/config/spt_config_v3.json \\
    -vv
```

**5. Archive all versions for episode "BOB_101" and submit to farm, relying on `FIXSTORE_DRIVE`:**

This assumes the `FIXSTORE_DRIVE` environment variable is set (e.g., to `/mnt/proj`), from which `--base-path` (e.g. `/mnt/proj`) would be inferred by the script if not explicitly provided.

```bash
fixarc-handler --project sandbox --episode BOB_101 \\
    --archive-root /mnt/proj/sandbox/delivery/archive \\
    --max-versions 0 \\
    --farm
```

**6. Archive latest versions for specific shots "BOB_101_002_020_CLN" and "BOB_101_00X_010_WIG" with high verbosity:**

```bash
fixarc-handler --project sandbox \\
    --shot BOB_101_002_020_CLN BOB_101_00X_010_WIG \\
    --archive-root /mnt/proj/sandbox/delivery/archive \\
    --base-path /mnt/proj \\
    --max-versions 1 \\
    -vv
```