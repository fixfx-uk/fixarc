# fixarc/utils.py
"""Utility functions for the Fix Archive (fixarc) tool."""

import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any, Union

# --- Fixenv Integration ---
# fixenv is a hard dependency
import fixenv
# --- YAML Loading --- (Required dependency)
import yaml
from fixarc import constants
from fixarc import log
from fixarc.exceptions import (
    DependencyError, ConfigurationError, ArchiveError, ParsingError, NukeExecutionError, ArchiverError
)
from fixfx.data.studio_data import StudioData


# --- Path Manipulation & Validation ---
def validate_path_exists(path: str, context: str = "Dependency") -> None:
    """Checks if a file or sequence directory exists. Raises DependencyError if not."""
    abs_path_str = fixenv.sanitize_path(path) # Get absolute path first
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
    path_str = fixenv.normalize_path(path) # Use normalized
    percent_match = re.search(r"(%0*(\d*)d)", path_str)
    if percent_match: return percent_match.group(1)
    if "####" in path_str: return "####"
    f_match = re.search(r"(\$F\d*)", path_str)
    if f_match: return f_match.group(1)
    return None

def is_sequence(path: Union[str, Path]) -> bool:
    return get_frame_padding_pattern(path) is not None

def expand_sequence_path(path_pattern: Union[str, Path], frame_range: Tuple[int, int]) -> List[str]:
    # Convert to string and normalize once at the beginning
    if isinstance(path_pattern, Path):
        path_pattern_str = str(path_pattern)
    else:
        path_pattern_str = path_pattern
    normalized_path_pattern = fixenv.normalize_path(path_pattern_str)

    pattern_token = get_frame_padding_pattern(normalized_path_pattern) # Pass the normalized string
    if not pattern_token: return [normalized_path_pattern] # Use the already normalized path
    paths = []
    try:
        start, end = frame_range
        if end < start: end = start # Clamp range
        # path_str = fixenv.normalize_path(path_pattern) # Remove this redundant normalization
        path_str = normalized_path_pattern # Use the already normalized path
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
    # Convert to string and normalize once at the beginning
    if isinstance(path_pattern, Path):
        path_pattern_str = str(path_pattern)
    else:
        path_pattern_str = path_pattern
    normalized_path_pattern = fixenv.normalize_path(path_pattern_str)

    pattern_token = get_frame_padding_pattern(normalized_path_pattern) # Pass the normalized string
    if not pattern_token: return None
    try:
        # norm_pattern = fixenv.normalize_path(path_pattern); base_dir = Path(norm_pattern).parent # Remove redundant normalization
        base_dir = Path(normalized_path_pattern).parent # Use the already normalized path
        if not base_dir.is_dir(): return None
        filename_pattern_part = Path(normalized_path_pattern).name; parts = filename_pattern_part.split(pattern_token, 1); file_prefix = parts[0]; file_suffix = parts[1] if len(parts) > 1 else ""
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
                if match:
                    try:
                        frames.append(int(match.group(1)))
                    except (ValueError, IndexError):
                        pass
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
    """Find the Nuke executable path.
    
    Returns:
        Path to the Nuke executable
        
    Raises:
        ConfigurationError: If Nuke executable is not found at the default location
    """
    # Use the default path from fixenv constants if available
    default_path = fixenv.constants.NUKE_EXEC_PATH_DEFAULT

    if Path(default_path).is_file():
        log.debug(f"Using default Nuke executable for {fixenv.OS}: {default_path}")
        return fixenv.normalize_path(default_path)

    # If default not found, raise error
    raise ConfigurationError(f"Nuke executable not found at default location: '{default_path}'.")

# Log the Nuke executor script path
log.info(f"Nuke Executor Script Path: {constants.NUKE_EXECUTOR_SCRIPT_PATH.absolute()}")

def execute_nuke_archive_process(
    input_script_path: str,
    archive_root: str,
    final_script_archive_path: str,
    metadata: Dict[str, Any],
    bake_gizmos: bool,
    repath_script_flag: bool = False,
    timeout: int = 300 
) -> Dict[str, Any]:
    """Execute the _nuke_executor.py script via 'nuke -t'.
    
    This performs the Nuke-side process: load, prune, dependency collection, 
    bake, save final script. It also handles repathing by passing a 
    pre-calculated mapping if requested.

    Args:
        input_script_path: Absolute path to the original Nuke script.
        archive_root: Absolute path to the archive destination root.
        final_script_archive_path: Absolute path where the processed script should be saved.
        metadata: Dictionary containing vendor, show, episode, shot, etc.
        bake_gizmos: Whether to bake gizmos in the script.
        repath_script_flag: Whether to enable repathing knobs within the script.
        timeout: Timeout in seconds for the entire Nuke process.

    Returns:
        Dictionary containing the results from the Nuke script's JSON output.
        Keys include: 'status', 'final_saved_script_path', 'original_dependencies', 'errors'.

    Raises:
        ConfigurationError: If Nuke executable or executor script not found.
        NukeExecutionError: If the Nuke process fails (timeout, crash, non-zero exit).
        ParsingError: If the JSON output from Nuke cannot be parsed.
    """
    nuke_exe = get_nuke_executable() # Raises ConfigurationError if not found

    if not constants.NUKE_EXECUTOR_SCRIPT_PATH.is_file():
        raise FileNotFoundError(f"Core Nuke executor script missing: {constants.NUKE_EXECUTOR_SCRIPT_PATH}")

    # Serialize metadata to JSON string for command line argument
    try:
        metadata_json_string = json.dumps(metadata)
    except TypeError as e:
        raise ConfigurationError(f"Metadata dictionary cannot be serialized to JSON: {e}") from e

    # Build the command line arguments
    command = [
        nuke_exe,
        "-t", # Terminal mode
        str(constants.NUKE_EXECUTOR_SCRIPT_PATH),
        "--input-script-path", fixenv.normalize_path(input_script_path),
        "--archive-root", fixenv.normalize_path(archive_root), # Pass for context
        "--final-script-archive-path", fixenv.normalize_path(final_script_archive_path),
        "--metadata-json", metadata_json_string, # Pass for context
    ]
    if bake_gizmos: command.append("--bake-gizmos")
    if repath_script_flag: command.append("--repath-script")

    # Use environment as is - NUKE_PATH is set up in the fixarc launcher script
    env = os.environ.copy()
    log.debug(f"Nuke Environment: {env}")
    
    log.info(f"Executing Nuke process with {timeout}s timeout... (Executor: {constants.NUKE_EXECUTOR_SCRIPT_PATH.name})")
    log.debug(f"Nuke Command: {' '.join(command)}") # Log full command at debug
    full_stdout = ""
    full_stderr = ""
    start_time = time.time()

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False, # Handle exit code manually
            timeout=timeout,
            encoding='utf-8',
            errors='replace', # Handle potential weird characters in Nuke output
            env=env  # Use our modified environment
        )
        elapsed = time.time() - start_time
        full_stdout = process.stdout or ""
        full_stderr = process.stderr or ""
        returncode = process.returncode

        log.debug(f"Nuke process finished after {elapsed:.1f}s. Exit Code: {returncode}")
        if full_stdout.strip(): log.debug(f"Nuke stdout:\n{full_stdout.strip()}")
        if full_stderr.strip(): log.warning(f"Nuke stderr:\n{full_stderr.strip()}") # Log stderr as warning

        # --- Parse JSON Output ---
        try:
            results = _parse_nuke_executor_output(full_stdout)
        except ParsingError as pe:
            log.error(f"Failed to parse JSON results from Nuke process: {pe}")
            if returncode != 0:
                 err_msg = f"Nuke process failed (Exit Code {returncode}) and output parsing error: {pe}."
            else:
                 err_msg = f"Nuke process finished successfully (Exit Code 0) but output parsing failed: {pe}."
            if full_stderr.strip(): err_msg += f"\nStderr: {full_stderr.strip()[:500]}..."
            raise NukeExecutionError(err_msg) from pe

        # --- Check Results and Exit Code ---
        if results.get("status") != "success" or returncode != 0:
             error_list = results.get("errors", [])
             if not error_list and returncode != 0: error_list.append(f"Nuke process exited with code {returncode}.")
             if full_stderr.strip(): error_list.append(f"Stderr: {full_stderr.strip()[:500]}...")

             final_error_message = f"Nuke process reported failure (Status: {results.get('status', 'unknown')}, Exit Code: {returncode}). Errors: {' || '.join(error_list)}"
             log.error(final_error_message)
             # Include original_dependencies in the exception if available for debugging
             if "original_dependencies" in results:
                 raise NukeExecutionError(final_error_message, results=results)
             else:
                 raise NukeExecutionError(final_error_message)

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

# --- Robust File Operations ---
def copy_file_or_sequence(source: str, dest: str, frame_range: Optional[Tuple[int, int]] = None, dry_run: bool = False) -> List[Tuple[str, str]]:
    """
    Copy a single file or sequence of frame files using shutil.
    Logs errors but doesn't raise them directly, returns empty list on failure.

    Args:
        source: Source file path or sequence pattern
        dest: Destination file path or sequence pattern
        frame_range: Optional tuple (start, end) for frame range if dealing with sequences
        dry_run: If True, simulate the operation

    Returns:
        List of (source, dest) pairs that were successfully planned or copied.
    """
    copied_pairs = []
    norm_source = fixenv.normalize_path(source)
    norm_dest = fixenv.normalize_path(dest)

    try:
        if is_sequence(norm_source):
            log.debug(f"Copying sequence: {norm_source} -> {norm_dest}")
            # Determine frame range if not provided
            resolved_range = frame_range
            if not resolved_range:
                resolved_range = find_sequence_range_on_disk(norm_source)
                if resolved_range:
                    log.info(f"Found frame range on disk for {norm_source}: {resolved_range[0]}-{resolved_range[1]}")
                else:
                    log.error(f"Sequence pattern detected but no frame range provided or found for: {norm_source}")
                    return [] # Cannot proceed without a range

            # Expand sequence into individual files
            source_files = expand_sequence_path(norm_source, resolved_range)
            dest_files = expand_sequence_path(norm_dest, resolved_range)

            if not source_files:
                log.error(f"Failed to expand source sequence: {norm_source}")
                return []
            if len(source_files) != len(dest_files):
                log.error(f"Mismatch in frame expansion for {norm_source} ({len(source_files)} frames) -> {norm_dest} ({len(dest_files)} frames)")
                return []

            dest_dir = Path(norm_dest).parent
            if not dry_run:
                try:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    log.error(f"Failed to create destination directory '{dest_dir}': {e}")
                    return [] # Cannot copy if destination dir fails

            # Copy each frame file
            for src, dst in zip(source_files, dest_files):
                if dry_run:
                    log.info(f"[DRY RUN] Would copy frame: {src} -> {dst}")
                    copied_pairs.append((src, dst))
                else:
                    src_path_obj = Path(src)
                    if not src_path_obj.is_file():
                        # Log as warning, maybe some frames are missing intentionally?
                        log.warning(f"Source frame missing: {src}")
                        continue # Skip this frame
                    try:
                        shutil.copy2(src, dst)
                        copied_pairs.append((src, dst))
                    except Exception as e:
                        log.error(f"Failed to copy frame {src} -> {dst}: {e}")
                        # Continue trying other frames
        else:
            # Copy single file
            log.debug(f"Copying single file: {norm_source} -> {norm_dest}")
            dest_dir = Path(norm_dest).parent
            if dry_run:
                log.info(f"[DRY RUN] Would copy: {norm_source} -> {norm_dest}")
                copied_pairs.append((norm_source, norm_dest))
            else:
                try:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    log.error(f"Failed to create destination directory '{dest_dir}': {e}")
                    return []

                src_path_obj = Path(norm_source)
                if not src_path_obj.is_file():
                    log.error(f"Source file does not exist: {norm_source}")
                    return []
                try:
                    shutil.copy2(norm_source, norm_dest)
                    copied_pairs.append((norm_source, norm_dest))
                except Exception as e:
                    log.error(f"Failed to copy {norm_source} -> {norm_dest}: {e}")
                    return [] # Fail if single file copy fails

    except Exception as e:
        log.error(f"Unexpected error in copy_file_or_sequence for {norm_source} -> {norm_dest}: {e}")
        return [] # Return empty on unexpected error

    return copied_pairs

# --- Robust File Copying ---
def copy_files_robustly(
    dependencies_to_copy: Dict[str, str], # {source_abs: dest_abs}
    dry_run: bool = False
) -> Tuple[int, int]:
    """
    Copies files listed in the dependency map using robocopy (Win) or rsync (Lin/Mac)
    with shutil fallback. Handles sequences.

    Args:
        dependencies_to_copy: Dictionary mapping absolute source paths to absolute
                              destination paths.
        dry_run: If True, simulate copy operations.

    Returns:
        Tuple (success_count, failure_count)
    """
    success_count = 0
    failure_count = 0
    total_expected = len(dependencies_to_copy)
    log.info(f"Starting robust file copy process for {total_expected} dependency item(s)...")
    processed_sequences = set() # Track sequence patterns already handled

    items = list(dependencies_to_copy.items())
    items.sort() # Process in a predictable order (helps with sequence handling)

    for index, (source_path, dest_path) in enumerate(items):

        log.debug(f"Processing copy item {index+1}/{total_expected}: {source_path} -> {dest_path}")

        # Basic validation
        if not source_path or not dest_path:
            log.warning(f"Skipping invalid copy item: Source='{source_path}', Dest='{dest_path}'")
            failure_count += 1
            continue

        norm_source = fixenv.normalize_path(source_path)
        norm_dest = fixenv.normalize_path(dest_path)

        # Check for sequence pattern
        is_seq = is_sequence(norm_source)
        sequence_pattern = norm_source if is_seq else None

        # Skip sequences if the pattern was already processed by this loop
        if is_seq and sequence_pattern in processed_sequences:
             log.debug(f"Skipping already processed sequence pattern: {sequence_pattern}")
             # Don't increment success/failure here, it was handled when first encountered
             continue

        # Destination directory preparation is handled inside copy_file_or_sequence or external tools

        # --- Perform Copy Operation ---
        copy_command = []
        use_shutil_fallback = False
        copy_success = False
        num_files_in_op = 1 # Default for single files

        try:
            # --- Build Command (Robocopy/Rsync) ---
            if fixenv.OS == fixenv.OS_WIN and not is_seq:
                 # Use robocopy for single files (less efficient but robust)
                 src_dir = str(Path(norm_source).parent)
                 src_file = Path(norm_source).name
                 dest_dir = str(Path(norm_dest).parent)
                 command = ['robocopy', src_dir, dest_dir, src_file, '/COPY:DAT', '/R:2', '/W:3', '/NJH', '/NJS', '/NP', '/NDL']
                 # Check if destination exists to decide on /IS (include same files/overwrite)
                 if not dry_run and Path(norm_dest).exists(): command.append('/IS')
                 copy_command = command
            elif (fixenv.OS == fixenv.OS_LIN or fixenv.OS == fixenv.OS_MAC) and not is_seq:
                 # Use rsync for single files
                 command = ['rsync', '-t', '-q', norm_source, norm_dest] # -t preserves times, -q quiet
                 copy_command = command
            else:
                 # Use shutil fallback for sequences or non-Win/Lin/Mac OS
                 log.debug(f"Using shutil fallback for: {norm_source}")
                 use_shutil_fallback = True

            # --- Execute Command or Fallback ---
            if copy_command and not use_shutil_fallback:
                 if dry_run:
                      log.info(f"[DRY RUN] Would execute: {' '.join(copy_command)}")
                      copy_success = True # Assume success for dry run command simulation
                 else:
                      log.info(f"Executing copy: {' '.join(copy_command)}")
                      # Ensure destination directory exists before running command
                      Path(norm_dest).parent.mkdir(parents=True, exist_ok=True)

                      copy_process = subprocess.run(copy_command, capture_output=True, text=True, check=False, encoding='utf-8', errors='replace')
                      # Robocopy success codes are <= 1 (or <= 3 if /IS used? Check docs). Rsync is 0.
                      success_codes = {0, 1} if fixenv.OS == fixenv.OS_WIN else {0}
                      if copy_process.returncode not in success_codes:
                           log.error(f"Copy command failed for '{norm_source}' (Code: {copy_process.returncode}):")
                           stdout = copy_process.stdout.strip()
                           stderr = copy_process.stderr.strip()
                           if stdout: log.error(f"stdout: {stdout}")
                           if stderr: log.error(f"stderr: {stderr}")
                           copy_success = False
                      else:
                           log.info(f"Successfully copied '{norm_source}' using external tool.")
                           copy_success = True
            else:
                 # Use Shutil Fallback
                 # Frame range determination happens inside copy_file_or_sequence now
                 copied_pairs = copy_file_or_sequence(norm_source, norm_dest, frame_range=None, dry_run=dry_run)
                 if copied_pairs: # Function returns list of successful copies
                     copy_success = True
                     num_files_in_op = len(copied_pairs) if is_seq else 1
                 else:
                     # copy_file_or_sequence logs errors internally
                     log.error(f"Shutil copy failed or resulted in zero files for: {norm_source}")
                     copy_success = False

            # --- Update Counts ---
            if copy_success:
                success_count += num_files_in_op
            else:
                # Estimate failure count: assume 1 for single file or guess sequence length?
                # Better to just count 1 failure per entry that failed.
                failure_count += 1

            # Mark sequence pattern as processed after attempting copy
            if is_seq and sequence_pattern:
                 processed_sequences.add(sequence_pattern)

        except (DependencyError, ArchiverError, OSError, Exception) as e:
             log.error(f"Failed to process copy item '{norm_source}' -> '{norm_dest}': {e}")
             failure_count += 1
             if is_seq and sequence_pattern: processed_sequences.add(sequence_pattern) # Mark as failed

    # Adjust success count if dry run (we only counted entries, not potential files)
    if dry_run:
        # This is tricky without actually expanding sequences. Report based on entries processed.
        success_count = total_expected - failure_count # Assume all non-failed entries would succeed
        log.info(f"[DRY RUN] Simulated copy process finished. Potential Success: {success_count}, Failures: {failure_count}")
    else:
        log.info(f"Robust copy process finished. Files Copied: {success_count}, Failures: {failure_count}")

    return success_count, failure_count


# --- Metadata Extraction Wrapper ---
def get_metadata_from_path(script_path: str) -> Dict[str, Any]:
    """
    Extract metadata from a file path using StudioData.

    Args:
        script_path (str): Path to the script file

    Returns:
        Dict[str, Any]: Dictionary containing extracted metadata, or empty if error.
    """
    try:
        log.debug(f"Attempting to extract metadata from path: {script_path}")
        studio_data = StudioData(script_path)
        
        # DEBUG: Inspect the StudioData object attributes
        _debug_studio_data_object(studio_data)
        
        # Use the metadata property which returns a dictionary of all available properties
        metadata = studio_data.metadata
        
        # Log the extracted metadata for debugging
        if metadata:
            log.debug(f"Successfully extracted metadata: {metadata}")
        else:
            log.warning(f"No metadata could be extracted from path: {script_path}")
            
        return metadata
    except Exception as e:
        log.warning(f"Error extracting metadata from path '{script_path}': {e}")
        return {}

def _debug_studio_data_object(studio_data: Any) -> None:
    """
    Debug helper to inspect StudioData object properties.
    Only runs when log level is DEBUG.
    """
    # Check if the current log level is more verbose than DEBUG (lower numbers are more verbose)
    if log.getEffectiveLevel() > logging.DEBUG:
        return
        
    log.debug("--- StudioData Debug Information ---")
    
    # Get regular attributes
    attributes = []
    for attr in dir(studio_data):
        # Skip private attributes and methods
        if attr.startswith('_') or callable(getattr(studio_data, attr)) or attr == 'metadata':
            continue
        
        try:
            value = getattr(studio_data, attr)
            attributes.append(f"{attr}: {value}")
        except Exception as e:
            attributes.append(f"{attr}: <error accessing: {e}>")
    
    if attributes:
        log.debug("Available attributes:")
        for attr in sorted(attributes):
            log.debug(f"  {attr}")
    else:
        log.debug("No accessible attributes found")
    
    # Output object type for debugging
    log.debug(f"Object type: {type(studio_data).__name__}")
    log.debug("--- End StudioData Debug Info ---")

# --- Path Mapping Logic ---

def load_mapping_rules(config_path: str) -> Optional[List[Dict[str, Any]]]:
    """Loads mapping rules from a YAML file."""
    try:
        abs_path = Path(config_path).resolve()
        if not abs_path.is_file():
            log.error(f"Mapping config file not found: {abs_path}")
            return None
        with open(abs_path, 'r', encoding='utf-8') as f:
            rules_data = yaml.safe_load(f)
        if not isinstance(rules_data, dict) or 'mapping_rules' not in rules_data:
            log.error(f"Invalid YAML format: Missing 'mapping_rules' top-level key in {abs_path}")
            return None
        rules_list = rules_data['mapping_rules']
        if not isinstance(rules_list, list):
            log.error(f"Invalid YAML format: 'mapping_rules' should be a list in {abs_path}")
            return None
        log.info(f"Successfully loaded {len(rules_list)} mapping rules from {abs_path}")
        return rules_list
    except yaml.YAMLError as e:
        log.error(f"Error parsing YAML mapping file {config_path}: {e}")
        return None
    except Exception as e:
        log.error(f"Error reading mapping file {config_path}: {e}")
        return None

def map_path_using_rules(sd: 'StudioData', rules: List[Dict[str, Any]]) -> Optional[str]:
    """
    Applies mapping rules based on StudioData properties to find a relative destination category.

    Args:
        sd: A StudioData object representing the source file path.
        rules: A list of rule dictionaries loaded from YAML.

    Returns:
        The matched relative destination path string (e.g., 'assets/images') or None if no rule matches.
    """
    if not sd:
        log.debug("Cannot map path: Invalid StudioData object provided.")
        return None

    # Extract properties from StudioData object into a dictionary
    properties = {}
    try:
        for prop in dir(sd):
            if not prop.startswith('_') and not callable(getattr(sd, prop)) and prop != 'metadata':
                properties[prop] = getattr(sd, prop)
    except Exception as e:
        log.warning(f"Error extracting properties from StudioData: {e}")
    
    log.debug(f"Attempting to map path using StudioData properties: {properties}")
    for rule in rules:
        conditions = rule.get('conditions', {})
        destination = rule.get('destination')
        rule_name = rule.get('name', 'Unnamed Rule')

        if not conditions or not destination:
            log.warning(f"Skipping invalid rule '{rule_name}': Missing 'conditions' or 'destination'.")
            continue

        match = True
        # Handle __DEFAULT__ rule first
        if conditions.get('__DEFAULT__', False):
            log.debug(f"Matched default rule '{rule_name}'. Destination: '{destination}'")
            return str(destination)

        # Evaluate other conditions
        for key, expected_value in conditions.items():
            actual_value = properties.get(key)

            if actual_value is None:
                match = False
                break # Property not found in StudioData

            # Condition types: exact string or list contains
            if isinstance(expected_value, list):
                if str(actual_value) not in expected_value:
                    match = False
                    break
            elif isinstance(expected_value, str):
                if str(actual_value) != expected_value:
                    match = False
                    break
            else: # Unsupported condition value type
                log.warning(f"Rule '{rule_name}' condition '{key}': Unsupported value type '{type(expected_value)}'. Skipping condition.")
                match = False # Treat unsupported condition as non-match
                break

        if match:
            log.debug(f"Matched rule '{rule_name}'. Conditions: {conditions}. Destination: '{destination}'")
            return str(destination) # Return first match

    log.debug(f"No specific rule matched for StudioData properties: {properties}")
    return None # No rule matched

def get_default_archive_path(source_path: str, archive_root: str) -> str:
    """
    Constructs the default archive path by replacing the drive letter/UNC prefix
    and prepending the archive root. Used when no mapping config is provided.

    Example:
        source_path = "Z:/proj/bob01/shots/BOB_103/.../file.exr"
        archive_root = "W:/proj/bob01/delivery/archive"
        Returns: "W:/proj/bob01/delivery/archive/Z_/proj/bob01/shots/BOB_103/.../file.exr"

        source_path = "//server/share/proj/bob01/.../file.exr"
        archive_root = "W:/proj/bob01/delivery/archive"
        Returns: "W:/proj/bob01/delivery/archive/server/share/proj/bob01/.../file.exr"

    Args:
        source_path: The absolute source path (normalized with forward slashes).
        archive_root: The absolute archive root path (normalized).

    Returns:
        The calculated absolute destination path.

    Raises:
        ValueError: If paths are invalid or cannot be processed.
    """
    norm_source = fixenv.normalize_path(source_path)
    norm_root = fixenv.normalize_path(archive_root)

    if not Path(norm_root).is_absolute():
        raise ValueError(f"Archive root must be an absolute path: {archive_root}")

    relative_part = ""
    # Handle Windows drive letters (e.g., C:/...) or UNC paths (e.g., //server/share/...)
    drive_match = re.match(r"^([a-zA-Z]):/(.*)", norm_source)
    unc_match = re.match(r"^//([^/]+/[^/]+)/(.*)", norm_source) # Match //server/share

    if drive_match:
        drive = drive_match.group(1)
        path_remainder = drive_match.group(2)
        relative_part = f"{drive}_/{path_remainder}" # e.g., C_/my/path
    elif unc_match:
        server_share = unc_match.group(1)
        path_remainder = unc_match.group(2)
        relative_part = f"{server_share}/{path_remainder}" # e.g., server/share/my/path
    elif norm_source.startswith('/'): # Linux/Mac absolute paths
        # Prepend a marker or just use the path relative to root? Let's use root_
        relative_part = f"root_{norm_source.lstrip('/')}"
    else:
        # Assume it might be a relative path already? Or just use it as is?
        # Using it as-is might be dangerous. Let's raise an error for unexpected formats.
        raise ValueError(f"Cannot determine relative part for default mapping from source: {source_path}")

    # Ensure the relative part doesn't try to escape the root (e.g., contain "..")
    # Splitting by / is safe due to normalize_path
    if '..' in relative_part.split('/'):
        raise ValueError(f"Source path resulted in potentially unsafe relative path: {relative_part}")

    # Combine archive root and the modified relative part
    # Use os.path.join and then normalize again to handle separators correctly
    final_path = fixenv.normalize_path(os.path.join(norm_root, relative_part))
    log.debug(f"Default mapping: '{source_path}' -> '{final_path}'")
    return final_path