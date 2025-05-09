#!/bin/bash

# --- Configuration ---
# Default base path for projects relies on FIXSTORE_DRIVE environment variable

# --- Script Setup ---
# Exit immediately if a command exits with a non-zero status.
# Pipefail ensures pipeline errors are caught.
set -eo pipefail
TEMP_DIR="" # Initialize global for trap cleanup

# --- Functions ---
usage() {
  cat << EOF
Usage: $(basename "$0") --archive-root <path> [MODE] [NAMES...] [OPTIONS]

Handles archiving Nuke scripts for projects, sequences, or shots using 'fixarc'.
Selects specific versions based on --max-versions. Can submit jobs to Deadline.

MODE (Choose one):
  --project <project_name>         Archive published Nuke scripts in the project's 'shots' scope.
  --sequence <sequence_name...>    Archive published Nuke scripts in the specified sequence(s).
                                   Requires --project argument.
  --shot <shot_name...>            Archive published Nuke scripts in the specified shot(s).
                                   Requires --project argument.

REQUIRED ARGUMENTS:
  --archive-root <path>            Root directory path for the archive output structure.

OPTIONAL ARGUMENTS:
  --project <project_name>         Project context, REQUIRED when using --sequence or --shot.
  --base-path <path>               Override the default base path for projects (Default: \$FIXSTORE_DRIVE/proj).
  --max-versions <N>               Number of latest versions to archive per shot:
                                     N <= 0: Archive ALL versions.
                                     N == 1 or unset: Archive LATEST version only.
                                     N > 1: Archive the latest N versions.
  --client-config <path.json>      Path to a JSON config file for client-specific mapping rules
                                   (passed to fixarc).
  --farm                           Submit each 'fixarc' process as a separate Deadline job.
                                   Requires 'deadlinecommand' to be in PATH.
  --fixarc-options "<options>"     Quote enclosed string of *other* options passed directly to 'fixarc'
                                   (e.g., "--bake-gizmos --vendor MyVendor"). Do not include
                                   --archive-root or --client-config here.
  -h, --help                       Show this help message and exit.

Examples:
  # Archive latest version for all shots in project 'bob01' locally
  $(basename "$0") --archive-root /path/to/archive --project bob01

  # Archive latest 3 versions for sequence BOB_101_002 on the farm
  $(basename "$0") --archive-root /path/to/archive --project bob01 --sequence BOB_101_002 \\
    --max-versions 3 --farm

EOF
  exit 1
}

log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1"
}
warn() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1" >&2
}
error() {
 echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

# Cleanup function for temporary files
cleanup() {
  if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
    # log "Cleaning up temporary directory: $TEMP_DIR" # Optional: verbose cleanup log
    rm -rf "$TEMP_DIR"
  fi
}
# Register cleanup function to run on exit, interrupt, or termination
trap cleanup EXIT HUP INT TERM

# --- Argument Parsing ---
MODE=""
PROJECT_NAME=""
ARCHIVE_ROOT=""
BASE_PATH=""
FIXARC_OPTIONS_STR=""
MAX_VERSIONS=1 # Default to latest only
CLIENT_CONFIG_PATH=""
FARM_MODE=false
NAMES=()

# Use getopt for robust option parsing
TEMP=$(getopt -o h --long help,project:,sequence,shot,archive-root:,base-path:,max-versions:,client-config:,farm,fixarc-options: -n "$(basename "$0")" -- "$@")
if [ $? != 0 ] ; then error "Terminating..." ; exit 1 ; fi
eval set -- "$TEMP"
unset TEMP

IS_SEQUENCE_MODE=false
IS_SHOT_MODE=false

while true; do
  case "$1" in
    --project)
      PROJECT_NAME="$2"
      # Check if a mode is already set, project can be context *or* mode
      if [ -z "$MODE" ]; then
          MODE="project"
      fi
      shift 2 ;;
    --sequence)
      # Only set mode if not already set by --project
      if [ -z "$MODE" ]; then
          MODE="sequence"
      fi
      IS_SEQUENCE_MODE=true # Flag to collect names after options
      shift ;;
    --shot)
       # Only set mode if not already set by --project
      if [ -z "$MODE" ]; then
          MODE="shot"
      fi
      IS_SHOT_MODE=true # Flag to collect names after options
      shift ;;
    --archive-root)
      ARCHIVE_ROOT="$2"
      shift 2 ;;
    --base-path)
      BASE_PATH="$2"
      shift 2 ;;
     --max-versions)
      MAX_VERSIONS="$2"
      # Validate numeric
      if ! [[ "$MAX_VERSIONS" =~ ^-?[0-9]+$ ]]; then
          error "--max-versions requires an integer value."
          usage
      fi
      shift 2 ;;
    --client-config)
      CLIENT_CONFIG_PATH="$2"
      shift 2 ;;
    --farm)
      FARM_MODE=true
      shift ;;
    --fixarc-options)
      FIXARC_OPTIONS_STR="$2"
      shift 2 ;;
    -h|--help)
      usage ;;
    --)
      shift # Discard the '--' separator
      break ;; # Stop option parsing
    *)
      error "Internal error! Unexpected option: $1" ; exit 1 ;;
  esac
done

# Collect remaining arguments as NAMES
NAMES=("$@")

# --- Input Validation ---
# (Existing validations for archive-root, mode, project context, names, client-config)
if [ -z "$ARCHIVE_ROOT" ]; then error "--archive-root is required."; usage; fi
# ... (keep other validations from previous version) ...
if [[ "$MODE" == "sequence" || "$MODE" == "shot" ]] && [ -z "$PROJECT_NAME" ]; then error "--project <project_name> is required when using --sequence or --shot mode."; usage; fi
# ... etc ...
if [ -n "$CLIENT_CONFIG_PATH" ] && [ ! -f "$CLIENT_CONFIG_PATH" ]; then error "Client config file not found: $CLIENT_CONFIG_PATH"; exit 1; fi

# Check for deadlinecommand if farm mode is enabled
if $FARM_MODE && ! command -v deadlinecommand &> /dev/null; then
    error "--farm mode requires 'deadlinecommand' to be in your PATH."
    exit 1
fi


# Check if fixarc command exists and get its absolute path
if ! command -v fixarc &> /dev/null; then
    error "'fixarc' command not found. Make sure it's installed and in your PATH."
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
    RELATIVE_FIXARC="${SCRIPT_DIR}/../bin/fixarc" # Assuming standard layout relative to handler
     if [ -x "$RELATIVE_FIXARC" ]; then
         FIXARC_CMD_PATH=$(realpath "$RELATIVE_FIXARC") # Get absolute path
         log "Found relative fixarc: ${FIXARC_CMD_PATH}"
     else
         error "Could not find relative fixarc either. Exiting."
        exit 1
     fi
else
    # Try to get absolute path of fixarc from PATH
    FIXARC_CMD_PATH=$(command -v fixarc)
     if [ -z "$FIXARC_CMD_PATH" ] || [ ! -x "$FIXARC_CMD_PATH" ]; then
          error "Found 'fixarc' in PATH but could not determine executable path or permissions."
          exit 1
     fi
     # Ensure absolute path for Deadline executable
     FIXARC_CMD_PATH=$(realpath "$FIXARC_CMD_PATH")

fi
log "Using fixarc command: $FIXARC_CMD_PATH"

# --- Determine Base Path ---
if [ -z "$BASE_PATH" ]; then
    if [ -z "$FIXSTORE_DRIVE" ]; then
        error "Cannot determine default base path. Please set FIXSTORE_DRIVE environment variable or use --base-path."
        exit 1
    fi
    BASE_PATH="${FIXSTORE_DRIVE}/proj"
fi
# Normalize base path (simple forward slash conversion, remove trailing)
BASE_PATH="${BASE_PATH//\\//}"
BASE_PATH="${BASE_PATH%/}"
log "Using base project path: $BASE_PATH"


# --- Prepare fixarc options array ---
declare -a FIXARC_OPTIONS_ARRAY
eval "FIXARC_OPTIONS_ARRAY=($FIXARC_OPTIONS_STR)" # Use eval carefully

# --- Build Search Paths ---
# (Same logic as previous version to populate SEARCH_PATHS and MISSING_SEARCH_ROOTS)
SEARCH_PATHS=()
MISSING_SEARCH_ROOTS=()
log "Determining search paths (Mode: $MODE)"
# ... (case statement for project/sequence/shot populating SEARCH_PATHS) ...
case "$MODE" in
  project)
    log "Targeting project: $PROJECT_NAME"
    search_root="$BASE_PATH/$PROJECT_NAME/shots"
    if [ ! -d "$search_root" ]; then error "Project shots directory not found: $search_root"; exit 1; fi
    SEARCH_PATHS+=("$search_root")
    ;;
  sequence)
    log "Targeting sequences for project: $PROJECT_NAME"
    for seq_name in "${NAMES[@]}"; do
        episode=$(echo "$seq_name" | cut -d'_' -f1,2)
        if [ -z "$episode" ]; then warn "Could not infer episode from sequence name '$seq_name'. Skipping."; continue; fi
        search_root="$BASE_PATH/$PROJECT_NAME/shots/$episode/$seq_name"
         if [ ! -d "$search_root" ]; then warn "Sequence directory not found: $search_root. Will not search here."; MISSING_SEARCH_ROOTS+=("$search_root"); else SEARCH_PATHS+=("$search_root"); log "Added search path for sequence '$seq_name': $search_root"; fi
    done
    ;;
  shot)
    log "Targeting shots for project: $PROJECT_NAME"
    for shot_name in "${NAMES[@]}"; do
        parts=(${shot_name//_/ }); if [ ${#parts[@]} -lt 4 ]; then warn "Shot name '$shot_name' does not seem to match expected format (EP_EP_SEQ_SHOT_TAG). Skipping."; continue; fi
        episode="${parts[0]}_${parts[1]}"; sequence_dir="${parts[0]}_${parts[1]}_${parts[2]}"
        if [ -z "$episode" ] || [ -z "$sequence_dir" ]; then warn "Could not infer episode/sequence directory from shot name '$shot_name'. Skipping."; continue; fi
        search_root="$BASE_PATH/$PROJECT_NAME/shots/$episode/$sequence_dir/$shot_name"
        if [ ! -d "$search_root" ]; then warn "Shot directory not found: $search_root. Will not search here."; MISSING_SEARCH_ROOTS+=("$search_root"); else SEARCH_PATHS+=("$search_root"); log "Added search path for shot '$shot_name': $search_root"; fi
    done
    ;;
esac

if [ ${#SEARCH_PATHS[@]} -eq 0 ]; then error "No valid search paths could be determined."; if [ ${#MISSING_SEARCH_ROOTS[@]} -gt 0 ]; then error "The following expected directories were missing:"; printf "  %s\n" "${MISSING_SEARCH_ROOTS[@]}" >&2; fi; exit 1; fi


# --- Find and Filter Nuke Scripts ---
log "Searching for Nuke scripts (*.nk) in 'publish/nuke' subdirectories and filtering by version..."
FOUND_SCRIPTS=()

# Find the publish/nuke dirs first
while IFS= read -r nuke_dir; do
    log "Checking directory: $nuke_dir"
    # Find .nk files, sort naturally (-V), handle null terminators (-z)
    mapfile -t sorted_scripts < <(find "$nuke_dir" -maxdepth 1 -name '*.nk' -type f -print0 | sort -zV)

    if [ ${#sorted_scripts[@]} -eq 0 ]; then log "  No .nk files found in $nuke_dir"; continue; fi

    scripts_to_add=()
    if [[ "$MAX_VERSIONS" -le 0 ]]; then
        log "  Selecting ALL ${#sorted_scripts[@]} versions (max-versions <= 0)."
        scripts_to_add=("${sorted_scripts[@]}")
    elif [[ "$MAX_VERSIONS" -eq 1 ]]; then
        log "  Selecting LATEST version (max-versions = 1 or unset)."
        scripts_to_add=("${sorted_scripts[-1]}") # Last element is latest
    else
        count=${#sorted_scripts[@]}
        num_to_take=$(( MAX_VERSIONS > count ? count : MAX_VERSIONS )) # Take N or count, whichever is smaller
        log "  Selecting LATEST $num_to_take versions (max-versions = $MAX_VERSIONS)."
        start_index=$(( count - num_to_take ))
        scripts_to_add=("${sorted_scripts[@]:$start_index}")
    fi

    FOUND_SCRIPTS+=("${scripts_to_add[@]}")
    log "  Added ${#scripts_to_add[@]} script(s) from this directory to the final list."

done < <(find "${SEARCH_PATHS[@]}" -type d -path "*/publish/nuke" -print)

# --- Check if Scripts Found ---
if [ ${#FOUND_SCRIPTS[@]} -eq 0 ]; then
  warn "No Nuke scripts found matching the criteria in 'publish/nuke' directories."
  if [ ${#MISSING_SEARCH_ROOTS[@]} -gt 0 ]; then
      warn "Note: The following expected directories were missing and could not be searched:"
      printf "  %s\n" "${MISSING_SEARCH_ROOTS[@]}" >&2
  fi
  # Stop if nothing found - changed from exit 2 to error + exit 1 based on requirement 7
  error "Stopping because no Nuke scripts were found to process."
  exit 1
fi

log "Total Nuke scripts selected for archival: ${#FOUND_SCRIPTS[@]}"
printf "  %s\n" "${FOUND_SCRIPTS[@]}"

# --- Prompt if Missing Dirs ---
if [ ${#MISSING_SEARCH_ROOTS[@]} -gt 0 ]; then
    warn "Some expected source directories were missing during the search:"
    printf "  %s\n" "${MISSING_SEARCH_ROOTS[@]}" >&2
    read -p "Do you want to continue archiving the found scripts? (y/N) " -n 1 -r
    echo # Move to new line
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log "User aborted."
        exit 3 # Specific exit code for user abort
    fi
fi


# --- Execute Archiving ---
SUCCESS_COUNT=0
FAIL_COUNT=0
CURRENT_USER=$(whoami) # Get current username for Deadline jobs

for script in "${FOUND_SCRIPTS[@]}"; do
  # Normalize script path
  script_norm="${script//\\//}"
  script_basename=$(basename "$script_norm")
  log "--- Preparing '$script_basename' ---"

  # --- Build Base Command Arguments ---
  # Start with script path and mandatory archive root
  declare -a base_args=( "$script_norm" --archive-root "$ARCHIVE_ROOT" )
  # Add client config if provided
  if [ -n "$CLIENT_CONFIG_PATH" ]; then
      base_args+=( "--client-config" "$CLIENT_CONFIG_PATH" )
  fi
  # Add other fixarc options if they exist
  if [ ${#FIXARC_OPTIONS_ARRAY[@]} -gt 0 ]; then
       base_args+=( "${FIXARC_OPTIONS_ARRAY[@]}" )
  fi

  # --- Execute Locally or Submit to Farm ---
  if ! $FARM_MODE; then
      # --- Run Locally ---
      log "Executing locally: $FIXARC_CMD_PATH ${base_args[*]}"
      if "$FIXARC_CMD_PATH" "${base_args[@]}"; then
        log "Successfully archived locally: $script_basename"
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
      else
        error "'fixarc' failed locally for: $script_basename (Exit code: $?)"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        # error "Stopping due to failure."; exit 1 # Optional: Stop on first failure
      fi
  else
      # --- Submit to Farm ---
      log "Submitting to Deadline farm: $script_basename"
      # Create temp directory for this job's files
      TEMP_DIR=$(mktemp -d -t fixarc_job_XXXXXX)
      JOB_INFO_FILE="$TEMP_DIR/job_info.job"

      # Prepare arguments string for Deadline job file (quote each arg)
      deadline_args=""
      for arg in "${base_args[@]}"; do
           # Simple quoting for arguments - assumes no embedded quotes needed for now
           deadline_args+="\"$arg\" "
      done

      # Create Job Info file content
      cat > "$JOB_INFO_FILE" << EOF
Plugin=CommandLine
Name=FixArc: $script_basename
Comment=Archive $script_norm via fixarc-handler
UserName=$CURRENT_USER
Frames=0
InitialStatus=Active
MachineLimit=1
# Optional: Add Pool=your_pool or Group=your_group if needed
# Pool=
# Group=

Executable=$FIXARC_CMD_PATH
Arguments=$deadline_args
# Set working directory? Often good practice for command line jobs
# StartInDirectory=$(dirname "$FIXARC_CMD_PATH") # Example: run from where fixarc lives
# Or maybe run from project root? Needs careful thought depending on fixarc's needs.

# Environment keys if needed (Example: inherit PYTHONPATH)
# EnvironmentKeyValue0=PYTHONPATH=$PYTHONPATH
EOF

      log "  Submitting Deadline job file: $JOB_INFO_FILE"
      if deadlinecommand "$JOB_INFO_FILE"; then
          log "  Successfully submitted job for $script_basename to Deadline."
          SUCCESS_COUNT=$((SUCCESS_COUNT + 1)) # Count submission success
      else
          error "  Failed to submit job for $script_basename to Deadline (Exit code: $?). Check Deadline logs."
          FAIL_COUNT=$((FAIL_COUNT + 1))
          # error "Stopping due to submission failure."; exit 1 # Optional: Stop on first failure
      fi
      # Cleanup is handled by trap EXIT
      TEMP_DIR="" # Reset global var after use
  fi
  log "------------------------------"
done

# --- Final Report ---
if $FARM_MODE; then
    log "Deadline job submission complete."
    log "Submitted: $SUCCESS_COUNT job(s)"
    log "Failed to submit: $FAIL_COUNT job(s)"
    log "Note: Check Deadline Monitor for the actual completion status of submitted jobs."
else
    log "Local archiving complete."
    log "Success: $SUCCESS_COUNT script(s)"
    log "Failed:  $FAIL_COUNT script(s)"
fi


if [ ${#MISSING_SEARCH_ROOTS[@]} -gt 0 ]; then
    warn "Reminder: Some expected source directories were missing during the search:"
    printf "  %s\n" "${MISSING_SEARCH_ROOTS[@]}" >&2
fi


if [ $FAIL_COUNT -gt 0 ]; then
  exit 1 # Exit with error if any submission or local run failed
else
  exit 0 # Exit successfully
fi


# Breakdown of Changes for Deadline Integration:

# --farm Flag: Added to getopt parsing and a boolean variable FARM_MODE is set.

# deadlinecommand Check: If FARM_MODE is true, the script checks if deadlinecommand is executable and in the PATH.

# FIXARC_CMD_PATH: Determined the absolute path to the fixarc wrapper using command -v and realpath. This is crucial because the Deadline worker needs the full path.

# trap cleanup: Added a trap command at the beginning to call the cleanup function when the script exits (normally, or due to interrupt/termination). The cleanup function removes the temporary directory created for job submission files.

# Conditional Execution Loop:

# The main loop now checks if ! $FARM_MODE; then ... else ... fi.

# Local Execution: Remains the same as before.

# Farm Submission:

# Creates a unique temporary directory using mktemp -d.

# Constructs the deadline_args string, ensuring each argument from the base_args array is quoted.

# Writes a job_info.job file using a cat << EOF ... EOF heredoc. This file contains:

# Plugin=CommandLine

# Job metadata (Name, Comment, UserName, Frames=0, InitialStatus, MachineLimit). You might want to add Pool or Group here based on your farm setup.

# Executable=$FIXARC_CMD_PATH (the absolute path to the wrapper).

# Arguments=$deadline_args (the quoted arguments for fixarc).

# Optionally added StartInDirectory and EnvironmentKeyValue comments as examples if needed later.

# Calls deadlinecommand "$JOB_INFO_FILE".

# Checks the exit code of deadlinecommand to determine if the submission was successful.

# Updates success/failure counts based on submission status.

# Resets TEMP_DIR so the trap doesn't try to remove it multiple times if it's reused in an error scenario (though mktemp should create unique dirs).

# Reporting: The final summary message is adjusted based on whether --farm was used, clarifying that success in farm mode means successful submission.