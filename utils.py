# fixarc/utils.py
"""Utility functions for the Fix Archive (fixarc) tool."""

import os
import re
import shutil
import subprocess
import json
import tempfile
import platform
import sys
import time
import select
import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any, Union

# Use logger from __init__
from . import log
# Import constants and exceptions relative to the package
from . import constants
from .exceptions import (
    DependencyError, ConfigurationError, ArchiveError, ParsingError, PruningError,
    RepathingError, GizmoError, NukeExecutionError
)

# --- Fixenv Integration ---
# Assume fixenv might be available, provide fallbacks if not
try:
    from fixenv import OS, OS_WIN, OS_LIN, OS_MAC
    from fixenv import normalize_path as fixenv_normalize_path
    from fixenv import sanitize_path as fixenv_sanitize_path
    from fixenv import get_metadata_from_path as fixenv_get_metadata # Use fixenv's metadata parser
    _fixenv_available = True
    log.debug("Using fixenv for OS detection and path handling.")
except ImportError:
    log.warning("fixenv package not found. Using basic OS detection and path normalization.")
    _fixenv_available = False
    OS = platform.system()
    OS_WIN, OS_LIN, OS_MAC = "Windows", "Linux", "Darwin"

    # Basic fallbacks
    def fixenv_normalize_path(path: Union[str, Path]) -> str:
        return str(path).replace("\\", "/")

    def fixenv_sanitize_path(path: Union[str, Path]) -> str:
        p = Path(fixenv_normalize_path(path))
        try: return str(p.resolve(strict=False)) # strict=False for non-existent paths
        except Exception: return str(p.absolute())

    def fixenv_get_metadata(script_path: str) -> Dict[str, Any]:
         log.warning("Cannot extract metadata from path: 'fixenv'/'fixfx' packages not available.")
         return {}

# --- Path Manipulation & Validation ---
def normalize_path(path: Union[str, Path]) -> str:
    """Normalize path using fixenv's function or basic fallback."""
    return fixenv_normalize_path(path)

def sanitize_path(path: Union[str, Path]) -> str:
    """Sanitize path using fixenv's function or basic fallback."""
    return fixenv_sanitize_path(path)

def validate_path_exists(path: str, context: str = "Dependency") -> None:
    """Checks if a file or sequence directory exists. Raises DependencyError if not."""
    abs_path_str = sanitize_path(path) # Get absolute path first
    abs_path_obj = Path(abs_path_str)
    is_seq = get_frame_padding_pattern(abs_path_str) is not None
    target_to_check = abs_path_obj.parent if is_seq else abs_path_obj
    check_type = "directory" if is_seq else "file"

    log.debug(f"Validating existence of {check_type}: {target_to_check} (Context: {context}, Original: '{path}')")
    exists = False
    try:
        if is_seq: exists = target_to_check.is_dir()
        else: exists = target_to_check.is_file()
    except OSError as e:
        log.warning(f"OS error checking existence of {target_to_check}: {e}")
        exists = False

    if not exists:
        error_msg = f"{context}: Required {check_type} not found at expected location: {target_to_check} (From original path: '{path}')"
        log.error(error_msg)
        raise DependencyError(error_msg)
    log.debug(f"Validation passed: {check_type} exists at {target_to_check}")

def is_ltfs_safe(filename: str) -> bool:
    """Check if a filename contains potentially problematic characters."""
    if not isinstance(filename, str): filename = str(filename)
    if not filename: return True
    match = re.search(constants.INVALID_FILENAME_CHARS, filename)
    if match:
        # Log only once per unique problematic filename? Could get noisy.
        # log.warning(f"Potentially unsafe character '{match.group(0)}' found in filename: '{filename}'")
        return False
    return True

def ensure_ltfs_safe(path_component: str) -> bool:
    """Checks if a single path component is safe. Logs error if not."""
    if not is_ltfs_safe(path_component):
         log.error(f"Path component '{path_component}' contains invalid characters for LTFS/archive.")
         return False
    return True

# --- Sequence Detection --- (Mostly unchanged, ensure normalize_path is used)
def get_frame_padding_pattern(path: Union[str, Path]) -> Optional[str]:
    path_str = normalize_path(path) # Use normalized
    percent_match = re.search(r"(%0*(\d*)d)", path_str)
    if percent_match: return percent_match.group(1)
    if "####" in path_str: return "####"
    f_match = re.search(r"(\$F\d*)", path_str)
    if f_match: return f_match.group(1)
    return None

def is_sequence(path: Union[str, Path]) -> bool:
    return get_frame_padding_pattern(path) is not None

def expand_sequence_path(path_pattern: Union[str, Path], frame_range: Tuple[int, int]) -> List[str]:
    pattern_token = get_frame_padding_pattern(path_pattern)
    if not pattern_token: return [normalize_path(path_pattern)]
    paths = []
    try:
        start, end = frame_range
        if end < start: end = start # Clamp range
        path_str = normalize_path(path_pattern)
        padding = 4; num_format = "{frame:04d}" # Defaults
        if pattern_token.startswith('%'):
            match = re.match(r"%0*(\d*)d", pattern_token); padding = int(match.group(1)) if match and match.group(1) else 4; num_format = f"{{frame:0{padding}d}}"; base_path = path_str.replace(pattern_token, num_format, 1)
        elif pattern_token == "####": padding = 4; num_format = "{frame:04d}"; base_path = path_str.replace("####", num_format, 1)
        elif pattern_token.startswith('$F'): padding_str = pattern_token[2:]; padding = int(padding_str) if padding_str.isdigit() else 4; num_format = f"{{frame:0{padding}d}}"; base_path = path_str.replace(pattern_token, num_format, 1)
        else: log.error(f"Unsupported pattern '{pattern_token}'"); return []
        for i in range(start, end + 1): paths.append(base_path.format(frame=i))
    except Exception as e: log.error(f"Error expanding sequence '{path_pattern}': {e}"); return []
    return paths

def find_sequence_range_on_disk(path_pattern: Union[str, Path]) -> Optional[Tuple[int, int]]:
    pattern_token = get_frame_padding_pattern(path_pattern)
    if not pattern_token: return None
    try:
        norm_pattern = normalize_path(path_pattern); base_dir = Path(norm_pattern).parent
        if not base_dir.is_dir(): return None
        filename_pattern_part = Path(norm_pattern).name; parts = filename_pattern_part.split(pattern_token, 1); file_prefix = parts[0]; file_suffix = parts[1] if len(parts) > 1 else ""
        padding = 4 # Default
        if pattern_token.startswith('%'): match = re.match(r"%0*(\d*)d", pattern_token); padding = int(match.group(1)) if match and match.group(1) else 4
        elif pattern_token == "####": padding = 4
        elif pattern_token.startswith('$F'): padding_str = pattern_token[2:]; padding = int(padding_str) if padding_str.isdigit() else 4
        frame_regex_part = rf"(\d{{{padding}}})"
        escaped_prefix = re.escape(file_prefix); escaped_suffix = re.escape(file_suffix); frame_regex = re.compile(rf"^{escaped_prefix}{frame_regex_part}{escaped_suffix}$")
        frames = []
        for item in base_dir.iterdir():
            if item.is_file():
                match = frame_regex.match(item.name)
                if match: try: frames.append(int(match.group(1))) except (ValueError, IndexError): pass
        if not frames: return None
        return min(frames), max(frames)
    except Exception as e: log.error(f"Error scanning disk for range '{path_pattern}': {e}"); return None

def parse_frame_range(range_str: Optional[str]) -> Optional[Tuple[int, int]]:
    if not range_str: return None
    match = re.match(r"^(-?\d+)(?:-(-?\d+))?$", str(range_str).strip())
    if not match: raise ValueError(f"Invalid frame range format: '{range_str}'.")
    try: start = int(match.group(1)); end = int(match.group(2)) if match.group(2) is not None else start; return start, end
    except ValueError: raise ValueError(f"Could not parse integers from range: '{range_str}'")

# --- Nuke Interaction ---
def get_nuke_executable() -> str:
    """Finds the Nuke executable path."""
    # Prioritize NUKE_EXE_PATH env var
    nuke_path_env = os.getenv("NUKE_EXE_PATH")
    if nuke_path_env:
        nuke_path_env_obj = Path(nuke_path_env)
        if nuke_path_env_obj.is_file():
            log.debug(f"Using Nuke executable from NUKE_EXE_PATH: {nuke_path_env}")
            return normalize_path(nuke_path_env)
        else:
            log.warning(f"NUKE_EXE_PATH ('{nuke_path_env}') does not point to a valid file. Checking defaults...")

    # Fallback to defaults based on OS
    if OS == OS_WIN: default_path = constants.DEFAULT_NUKE_EXECUTABLE_WIN
    elif OS == OS_LIN: default_path = constants.DEFAULT_NUKE_EXECUTABLE_LIN
    elif OS == OS_MAC: default_path = constants.DEFAULT_NUKE_EXECUTABLE_MAC
    else: raise EnvironmentError(f"Unsupported OS '{OS}' for Nuke.")

    if Path(default_path).is_file():
        log.debug(f"Using default Nuke executable for {OS}: {default_path}")
        return normalize_path(default_path)

    # If default not found, raise error (could add more search logic here if needed)
    raise ConfigurationError(f"Nuke executable not found at default location: '{default_path}'. Set the NUKE_EXE_PATH environment variable.")

# Path to the internal Nuke script relative to this utils file
_NUKE_EXECUTOR_SCRIPT_PATH = Path(__file__).parent / constants.NUKE_EXECUTOR_SCRIPT_NAME

def execute_nuke_archive_process(
    input_script_path: str,
    archive_root: str,
    final_script_archive_path: str,
    metadata: Dict[str, Any],
    bake_gizmos: bool,
    repath_script_flag: bool,
    timeout: int = 300 # Increased default timeout for potentially long process
) -> Dict[str, Any]:
    """
    Executes the _nuke_executor.py script via 'nuke -t'. This performs the
    entire Nuke-side process: load, prune, dep collection, bake, repath, save.

    Args:
        input_script_path: Absolute path to the original Nuke script.
        archive_root: Absolute path to the archive destination root.
        final_script_archive_path: Absolute path where the processed script should be saved.
        metadata: Dictionary containing vendor, show, episode, shot, etc.
        bake_gizmos: Boolean flag passed to Nuke script.
        repath_script_flag: Boolean flag passed to Nuke script.
        timeout: Timeout in seconds for the entire Nuke process.

    Returns:
        Dictionary containing the results parsed from the Nuke script's JSON output.
        Expected keys: 'status', 'final_saved_script_path', 'dependencies_to_copy', 'errors'.

    Raises:
        ConfigurationError: If Nuke executable or executor script not found.
        NukeExecutionError: If the Nuke process fails critically (timeout, crash, non-zero exit).
        ParsingError: If the JSON output from Nuke cannot be parsed.
    """
    nuke_exe = get_nuke_executable() # Raises ConfigurationError if not found

    if not _NUKE_EXECUTOR_SCRIPT_PATH.is_file():
        raise FileNotFoundError(f"Core Nuke executor script missing: {_NUKE_EXECUTOR_SCRIPT_PATH}")

    # Serialize metadata to JSON string for command line argument
    try:
        metadata_json_string = json.dumps(metadata)
    except TypeError as e:
        raise ConfigurationError(f"Metadata dictionary cannot be serialized to JSON: {e}") from e

    # Build the command line arguments
    command = [
        nuke_exe,
        "-t", # Terminal mode
        str(_NUKE_EXECUTOR_SCRIPT_PATH),
        "--input-script-path", normalize_path(input_script_path),
        "--archive-root", normalize_path(archive_root),
        "--final-script-archive-path", normalize_path(final_script_archive_path),
        "--metadata-json", metadata_json_string,
    ]
    if bake_gizmos: command.append("--bake-gizmos")
    if repath_script_flag: command.append("--repath-script")
    # Add other necessary arguments here if _nuke_executor expects them

    log.info(f"Executing Nuke process with {timeout}s timeout...")
    log.debug(f"Nuke Command: {' '.join(command)}") # Log full command at debug
    full_stdout = ""
    full_stderr = ""
    start_time = time.time()

    try:
        # Use Popen for potentially better handling of large output / interactivity if needed later
        # For now, stick with run for simplicity, but increase buffer size if output truncated?
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False, # Handle exit code manually
            timeout=timeout,
            encoding='utf-8',
            errors='replace' # Handle potential weird characters in Nuke output
        )
        elapsed = time.time() - start_time
        full_stdout = process.stdout or ""
        full_stderr = process.stderr or ""
        returncode = process.returncode

        log.debug(f"Nuke process finished after {elapsed:.1f}s. Exit Code: {returncode}")
        # Log stdout/stderr only if they contain data, trim whitespace
        if full_stdout.strip(): log.debug(f"Nuke stdout:\n{full_stdout.strip()}")
        if full_stderr.strip(): log.warning(f"Nuke stderr:\n{full_stderr.strip()}") # Log stderr as warning

        # --- Parse JSON Output ---
        # Expect JSON to be the *last* significant output on stdout
        try:
            results = _parse_nuke_executor_output(full_stdout)
        except ParsingError as pe:
            log.error(f"Failed to parse JSON results from Nuke process: {pe}")
            # If parsing fails, check exit code and stderr for clues
            if returncode != 0:
                 err_msg = f"Nuke process failed (Exit Code {returncode}) and output parsing error: {pe}."
            else:
                 err_msg = f"Nuke process finished successfully (Exit Code 0) but output parsing failed: {pe}."
            if full_stderr.strip(): err_msg += f"\nStderr: {full_stderr.strip()[:500]}..."
            raise NukeExecutionError(err_msg) from pe

        # --- Check Results and Exit Code ---
        if results.get("status") != "success" or returncode != 0:
             error_list = results.get("errors", [])
             # If Nuke crashed hard, error list might be empty, use stderr
             if not error_list and returncode != 0: error_list.append(f"Nuke process exited with code {returncode}.")
             if full_stderr.strip(): error_list.append(f"Stderr: {full_stderr.strip()[:500]}...")

             final_error_message = f"Nuke process reported failure (Status: {results.get('status', 'unknown')}, Exit Code: {returncode}). Errors: {' || '.join(error_list)}"
             log.error(final_error_message)
             raise NukeExecutionError(final_error_message, results=results) # Include parsed results if available

        # If status is success and exit code is 0
        log.info(f"Nuke processing completed successfully in {elapsed:.1f}s.")
        return results

    except FileNotFoundError:
        # Occurs if nuke_exe path is wrong or nuke isn't installed/in PATH
        raise ConfigurationError(f"Nuke executable not found or permission denied at '{nuke_exe}'.") from None
    except subprocess.TimeoutExpired:
        log.error(f"Nuke process timed out after {timeout} seconds.")
        # Log captured output if available
        if full_stdout.strip(): log.debug(f"Nuke stdout on Timeout:\n{full_stdout.strip()}")
        if full_stderr.strip(): log.warning(f"Nuke stderr on Timeout:\n{full_stderr.strip()}")
        raise NukeExecutionError(f"Nuke process timed out after {timeout} seconds.") from None
    except Exception as e:
        # Catch any other unexpected errors (e.g., subprocess issues)
        log.exception(f"An unexpected error occurred running Nuke: {e}")
        if full_stdout.strip(): log.debug(f"Nuke stdout on Error:\n{full_stdout.strip()}")
        if full_stderr.strip(): log.warning(f"Nuke stderr on Error:\n{full_stderr.strip()}")
        raise ArchiveError(f"Failed to execute Nuke process: {e}") from e


def _parse_nuke_executor_output(output: str) -> Dict[str, Any]:
    """Helper to extract the final JSON results block from _nuke_executor.py stdout."""
    json_start_tag = "--- NUKE EXECUTOR FINAL RESULTS ---"
    json_string = ""
    try:
        # Find the *last* occurrence of the start tag
        json_start_index = output.rindex(json_start_tag)
        # Extract JSON string part
        json_part = output[json_start_index + len(json_start_tag):]
        # Find the first opening brace '{' which marks the start of our JSON object
        json_obj_start = json_part.find('{')
        if json_obj_start == -1:
             raise ValueError("Could not find start of JSON object ('{') after result tag.")
        # Find the matching closing brace '}' - this is tricky if JSON is nested
        # Simple approach: find last closing brace
        json_obj_end = json_part.rfind('}')
        if json_obj_end == -1 or json_obj_end < json_obj_start:
             raise ValueError("Could not find end of JSON object ('}') after result tag.")

        # Extract the potential JSON string
        json_string = json_part[json_obj_start : json_obj_end + 1].strip()

        if not json_string:
             raise ValueError("JSON results section is empty after extraction.")

        parsed_json = json.loads(json_string)
        log.debug("Successfully parsed JSON results from Nuke executor output.")
        return parsed_json
    except ValueError as e: # Catches rindex not found, brace finding errors, or json.JSONDecodeError
        log.error(f"Failed to find or parse JSON results from Nuke output: {e}")
        log.debug(f"Full Nuke Output for Parsing Debug:\n{output.strip()}")
        if json_start_tag in output:
             log.debug(f"Problematic String Segment Tried:\n{json_string if json_string else 'N/A'}")
        raise ParsingError(f"Could not retrieve valid JSON results from Nuke executor: {e}") from e

# --- Robust File Copying ---
def copy_files_robustly(
    dependencies_to_copy: Dict[str, Optional[str]], # {source_abs: dest_abs_or_None}
    dry_run: bool = False
) -> Tuple[int, int]:
    """
    Copies files listed in the dependency map using robocopy (Win) or rsync (Lin/Mac)
    with shutil fallback. Handles sequences.

    Args:
        dependencies_to_copy: Dictionary mapping absolute source paths to absolute
                              destination paths (value is None if destination invalid).
        dry_run: If True, simulate copy operations.

    Returns:
        Tuple (success_count, failure_count)
    """
    success_count = 0
    failure_count = 0
    total_expected = len(dependencies_to_copy)
    log.info(f"Starting robust file copy process for {total_expected} dependency entries...")
    processed_sequences = set() # Track sequence patterns already handled

    for index, (source_path, dest_path) in enumerate(dependencies_to_copy.items()):

        log.debug(f"Processing copy item {index+1}/{total_expected}: {source_path} -> {dest_path}")

        if not source_path: # Should not happen if map generated correctly
            log.warning("Skipping copy item with no source path.")
            failure_count += 1
            continue
        if not dest_path:
            log.warning(f"Skipping copy for '{source_path}': Invalid or missing destination path.")
            failure_count += 1
            continue

        norm_source = normalize_path(source_path)
        norm_dest = normalize_path(dest_path)

        is_seq = is_sequence(norm_source)
        source_pattern_or_file = norm_source if is_seq else Path(norm_source)
        dest_dir = Path(norm_dest).parent
        dest_pattern_or_file = norm_dest

        # Skip sequences if the pattern was already processed
        if is_seq and source_pattern_or_file in processed_sequences:
             log.debug(f"Skipping already processed sequence pattern: {source_pattern_or_file}")
             continue

        # Ensure destination directory exists (create if needed, handle errors)
        if dry_run:
             if not dest_dir.exists(): log.info(f"[DRY RUN] Would ensure directory exists: {dest_dir}")
        else:
             try:
                 dest_dir.mkdir(parents=True, exist_ok=True)
             except OSError as e:
                 log.error(f"Failed to create destination directory '{dest_dir}' for '{norm_source}': {e}")
                 failure_count += 1
                 if is_seq: processed_sequences.add(source_pattern_or_file) # Mark as failed
                 continue # Skip this item/sequence

        # --- Perform Copy Operation ---
        copy_command = []
        use_shutil_fallback = False

        try:
            # --- Build Command (Robocopy/Rsync) ---
            if OS == OS_WIN:
                 # Robocopy - Basic options: /E (subdirs), /COPY:DAT (data, attrs, times), /R:3 (retries), /W:5 (wait)
                 # /NJH (no header), /NJS (no summary), /NP (no progress), /NDL (no dir logging) - adjust for desired output
                 # For sequences, copy individual files. Robocopy better for dirs.
                 if not is_seq:
                      # Copy single file: robocopy <SourceDir> <DestDir> <FileName> [options]
                      src_dir = str(Path(norm_source).parent)
                      src_file = Path(norm_source).name
                      command = ['robocopy', src_dir, str(dest_dir), src_file, '/COPY:DAT', '/R:2', '/W:3', '/NJH', '/NJS', '/NP', '/NDL']
                      # Add /IS to include same files (overwrite)
                      if Path(norm_dest).exists(): command.append('/IS')
                      copy_command = command
                 else:
                      use_shutil_fallback = True # Robocopy less ideal for frame-by-frame of sequences
            elif OS == OS_LIN or OS == OS_MAC:
                 # Rsync - Basic options: -a (archive), -v (verbose), --progress
                 # Handle sequences carefully. Rsync good for dirs or specific files.
                 if not is_seq:
                      # Copy single file: rsync [options] <SourceFile> <DestFile>
                      command = ['rsync', '-t', '--progress', norm_source, norm_dest] # -t preserves times
                      copy_command = command
                 else:
                      use_shutil_fallback = True # Rsync less ideal for specific frame ranges unless generating file list

            # --- Execute Command or Fallback ---
            if copy_command and not use_shutil_fallback:
                 if dry_run:
                      log.info(f"[DRY RUN] Would execute: {' '.join(copy_command)}")
                      success_count += 1 # Assume success for dry run simulation
                 else:
                      log.info(f"Executing copy command: {' '.join(copy_command)}")
                      # Run the command
                      copy_process = subprocess.run(copy_command, capture_output=True, text=True, check=False)
                      if copy_process.returncode > 1: # Robocopy uses codes 0-1 for success
                           log.error(f"Copy command failed for '{norm_source}' (Code: {copy_process.returncode}):")
                           if copy_process.stdout: log.error(f"stdout: {copy_process.stdout.strip()}")
                           if copy_process.stderr: log.error(f"stderr: {copy_process.stderr.strip()}")
                           failure_count += 1
                      else:
                           log.info(f"Successfully copied '{norm_source}' using external tool.")
                           success_count += 1
            else:
                 # Use Shutil Fallback (especially for sequences)
                 log.debug(f"Using shutil fallback for: {norm_source}")
                 # Need frame range if sequence
                 frame_range = None
                 if is_seq:
                      # This info isn't passed here easily - need to get it from manifest again?
                      # Workaround: Scan disk again here if needed. Very inefficient.
                      # BEST: Nuke process should return range info with dependencies_to_copy map.
                      # Assuming for now copy_file_or_sequence can handle it (needs refactor there)
                      log.warning(f"Cannot determine frame range for shutil fallback on sequence: {norm_source}. Copy may fail or be incomplete.")
                      # Try scanning disk as fallback
                      frame_range = find_sequence_range_on_disk(norm_source)
                      if not frame_range:
                           raise DependencyError(f"Frame range needed for shutil sequence copy of '{norm_source}' but could not be determined.")


                 copied_pairs = copy_file_or_sequence(norm_source, norm_dest, frame_range, dry_run)
                 if not dry_run and not copied_pairs:
                      # Indicates failure within copy_file_or_sequence
                      log.error(f"Shutil copy failed for: {norm_source}")
                      failure_count += 1
                 else:
                      success_count += len(copied_pairs) if is_seq else 1 # Count frames or single file

            # Mark sequence pattern as processed after attempting copy
            if is_seq:
                 processed_sequences.add(source_pattern_or_file)

        except (DependencyError, ArchiverError, Exception) as e:
             log.error(f"Failed to process copy item '{norm_source}' -> '{norm_dest}': {e}")
             failure_count += 1
             if is_seq: processed_sequences.add(source_pattern_or_file) # Mark as failed

    log.info(f"Robust copy process finished. Success: {success_count}, Failures: {failure_count}")
    # Note: success_count might represent frames for sequences when using shutil
    return success_count, failure_count


# --- Metadata Extraction Wrapper ---
def get_metadata_from_path(script_path: str) -> Dict[str, Any]:
    """Wrapper to use fixenv's metadata extraction if available."""
    return fixenv_get_metadata(script_path) # Uses fallback if fixenv not imported