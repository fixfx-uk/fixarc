"""Utility functions for the Fix Archive tool."""

import os
import re
import shutil
import subprocess
import json
import tempfile
import platform
import sys # Keep sys import for potential fallback logging
import time
import select
import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any, Union

import constants
from .constants import (
    NUKE_EXEC_PATH_WIN,
    NUKE_EXEC_PATH_LIN,
    NUKE_EXEC_PATH_MAC,
)

# --- Logging Setup ---
# Import the get_logger function configured in the parent __init__.
# This ensures we use fixfx.core.logger if available, or the fallback.
try:
    from . import get_logger
    log = get_logger(__name__) # Get logger named 'fixarc.utils'
except ImportError:
    # This should ideally not happen if __init__.py ran, but basic fallback
    import logging
    log = logging.getLogger(__name__)
    if not log.hasHandlers():
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s]: %(message)s')
        handler.setFormatter(formatter)
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    log.error("Could not import get_logger from parent package. Using basic logging.")

# Import constants and exceptions relative to the package
from . import constants
from .exceptions import (
    DependencyError, ConfigurationError, ArchiveError, ParsingError, PruningError,
    RepathingError, GizmoError # Ensure all used exceptions are imported
)

# --- Fixenv Integration ---
from fixenv import OS, OS_WIN, OS_LIN, OS_MAC
import fixenv

# --- Path Manipulation & Validation ---
from fixenv import normalize_path

def validate_path_exists(path: str, context: str = "Dependency") -> None:
    """
    Checks if a file or sequence directory exists. Raises DependencyError if not.
    """
    # Use sanitize_path which should return an absolute, normalized path
    abs_path_obj = Path(path)

    # Check if it looks like a sequence pattern
    is_seq = get_frame_padding_pattern(abs_path_str) is not None

    target_to_check = abs_path_obj.parent if is_seq else abs_path_obj
    check_type = "directory" if is_seq else "file"

    log.debug(f"Validating existence of {check_type}: {target_to_check} (Context: {context}, Original: '{path}')")

    exists = False
    try:
        if is_seq:
            exists = target_to_check.is_dir()
        else:
            exists = target_to_check.is_file()
    except OSError as e:
        log.warning(f"OS error checking existence of {target_to_check}: {e}")
        # Treat access errors as non-existent for safety? Or re-raise? Let's treat as not found.
        exists = False

    if not exists:
        error_msg = f"{context}: Required {check_type} not found at expected location: {target_to_check} (From original path: '{path}')"
        log.error(error_msg)
        raise DependencyError(error_msg)

    log.debug(f"Validation passed: {check_type} exists at {target_to_check}")


def is_ltfs_safe(filename: str) -> bool:
    """Check if a filename contains potentially problematic characters for LTFS/cross-platform."""
    if not isinstance(filename, str): filename = str(filename) # Ensure string
    if not filename: return True # Empty string is safe
    match = re.search(constants.INVALID_FILENAME_CHARS, filename)
    if match:
        log.warning(f"Potentially unsafe character '{match.group(0)}' found in filename: '{filename}'")
        return False
    return True

def ensure_ltfs_safe(path_component: str) -> bool:
    """Checks if a single path component (file or dir name) is safe. Logs error if not."""
    if not is_ltfs_safe(path_component):
         # Error logged by is_ltfs_safe
         return False
    return True


# --- Sequence Detection ---
def get_frame_padding_pattern(path: Union[str, Path]) -> Optional[str]:
    """Detects common frame padding patterns (%0Xd, ####, $F variants)."""
    path_str = normalize_path(path) # Use normalized path string
    # Prioritize %0xd style
    percent_match = re.search(r"(%0*(\d*)d)", path_str)
    if percent_match:
        return percent_match.group(1) # e.g., %04d, %d
    # Check for #### (common Nuke/Houdini alternative)
    if "####" in path_str:
        return "####"
    # Check for $F variants (e.g., $F, $F4)
    # Match $F followed by optional digits
    f_match = re.search(r"(\$F\d*)", path_str)
    if f_match:
        # If just $F, return $F. If $F4, return $F4.
        return f_match.group(1)
    # Add other patterns like <frame>, <UDIM> if needed
    return None

def is_sequence(path: Union[str, Path]) -> bool:
    """Checks if the path likely represents a frame sequence based on common patterns."""
    return get_frame_padding_pattern(path) is not None

def expand_sequence_path(path_pattern: Union[str, Path], frame_range: Tuple[int, int]) -> List[str]:
    """
    Expands a sequence path pattern into a list of file paths for a given range.
    Supports %0Xd, ####, $F, $F<n>. Returns empty list on error.
    """
    pattern_token = get_frame_padding_pattern(path_pattern)
    if not pattern_token:
        # If no pattern, but range given, maybe just return original path N times? No, return single.
        log.debug(f"Path '{path_pattern}' is not a sequence pattern. Returning as single item.")
        return [normalize_path(path_pattern)]

    paths = []
    try:
        start, end = frame_range
        # Allow end < start, generate frames based on range direction? No, standard is start -> end.
        if end < start:
            log.warning(f"End frame {end} is less than start frame {start} for sequence '{path_pattern}'. Expanding only frame {start}.")
            end = start # Clamp range to single frame if end < start

        log.debug(f"Expanding sequence '{path_pattern}' from frame {start} to {end}")
        path_str = normalize_path(path_pattern) # Use normalized string

        padding = 4 # Default padding
        num_format = "{frame:04d}" # Default format string

        if pattern_token.startswith('%'):
            match = re.match(r"%0*(\d*)d", pattern_token)
            padding = int(match.group(1)) if match and match.group(1) else 4
            num_format = f"{{frame:0{padding}d}}"
            base_path = path_str.replace(pattern_token, num_format, 1) # Replace first occurrence
        elif pattern_token == "####":
            padding = 4
            num_format = "{frame:04d}"
            base_path = path_str.replace("####", num_format, 1)
        elif pattern_token.startswith('$F'):
             padding_str = pattern_token[2:]
             padding = int(padding_str) if padding_str.isdigit() else 4
             num_format = f"{{frame:0{padding}d}}"
             base_path = path_str.replace(pattern_token, num_format, 1)
        else:
             log.error(f"Unsupported sequence pattern '{pattern_token}' in path '{path_str}'. Cannot expand.")
             return [] # Return empty list on unsupported pattern

        # Generate paths using f-string formatting for clarity
        for i in range(start, end + 1):
             # Use a dictionary for format() to make it explicit
             frame_path = base_path.format(frame=i)
             paths.append(frame_path)

    except (ValueError, TypeError) as e:
        log.error(f"Error formatting sequence path for frame number: {e}. Pattern='{pattern_token}', Path='{path_pattern}', Range={frame_range}")
        return [] # Return empty list on formatting error
    except Exception as e:
        log.error(f"Unexpected error expanding sequence '{path_pattern}': {e}")
        return []

    return paths


def find_sequence_range_on_disk(path_pattern: Union[str, Path]) -> Optional[Tuple[int, int]]:
    """
    Tries to find the first and last frame number of a sequence present on disk
    matching the provided pattern.
    """
    pattern_token = get_frame_padding_pattern(path_pattern)
    if not pattern_token:
        log.debug(f"Path '{path_pattern}' is not a sequence pattern. Cannot scan disk.")
        return None

    try:
        norm_pattern = normalize_path(path_pattern)
        base_dir = Path(norm_pattern).parent

        if not base_dir.is_dir():
            log.warning(f"Directory for sequence pattern '{norm_pattern}' does not exist or is not a directory: {base_dir}")
            return None

        filename_pattern_part = Path(norm_pattern).name
        # Split based on the detected token
        parts = filename_pattern_part.split(pattern_token, 1)
        file_prefix = parts[0]
        file_suffix = parts[1] if len(parts) > 1 else ""

        # Determine regex capture group based on pattern's padding
        padding = 4 # Default
        if pattern_token.startswith('%'):
            match = re.match(r"%0*(\d*)d", pattern_token)
            padding = int(match.group(1)) if match and match.group(1) else 4
        elif pattern_token == "####":
            padding = 4
        elif pattern_token.startswith('$F'):
             padding_str = pattern_token[2:]
             padding = int(padding_str) if padding_str.isdigit() else 4

        # Regex to capture frame number digits (\d+) - be more specific with padding
        # Capture exactly 'padding' digits
        frame_regex_part = rf"(\d{{{padding}}})"

        # Escape regex special characters in prefix/suffix for safety
        escaped_prefix = re.escape(file_prefix)
        escaped_suffix = re.escape(file_suffix)
        # Compile regex: ^ + prefix + digits + suffix + $
        frame_regex = re.compile(rf"^{escaped_prefix}{frame_regex_part}{escaped_suffix}$")

        frames = []
        log.debug(f"Scanning directory '{base_dir}' with regex '{frame_regex.pattern}'")
        for item in base_dir.iterdir():
            # Check if item is a file first to avoid errors on dirs/links
            if item.is_file():
                match = frame_regex.match(item.name)
                if match:
                    try:
                        # Extract the captured frame number (group 1)
                        frame_num = int(match.group(1))
                        frames.append(frame_num)
                    except (ValueError, IndexError):
                        # Log if conversion fails, but continue scanning
                        log.warning(f"Could not parse frame number from matched file: {item.name}")
                        continue

        if not frames:
            log.warning(f"No frames found on disk matching pattern '{norm_pattern}' in directory '{base_dir}'")
            return None

        min_frame, max_frame = min(frames), max(frames)
        log.debug(f"Disk scan found range: {min_frame}-{max_frame}")
        return min_frame, max_frame

    except OSError as e:
        log.error(f"OS error scanning directory or files for sequence '{path_pattern}': {e}")
        return None
    except Exception as e:
        # Catch other potential errors (regex, path manipulation)
        log.error(f"Unexpected error during sequence range disk scan for '{path_pattern}': {e}")
        return None


def parse_frame_range(range_str: Optional[str]) -> Optional[Tuple[int, int]]:
    """Parses frame range string like '1001-1100' or '1050'."""
    if not range_str:
        return None
    range_str = str(range_str).strip() # Ensure string and remove whitespace
    # Match single frame or range (allowing negative numbers)
    match = re.match(r"^(-?\d+)(?:-(-?\d+))?$", range_str)
    if not match:
        raise ValueError(f"Invalid frame range format: '{range_str}'. Use 'start' or 'start-end'.")
    try:
        start = int(match.group(1))
        end_str = match.group(2)
        end = int(end_str) if end_str is not None else start # Use start if end is missing
        # Allow end frame to be less than start frame (handled by expand_sequence)
        # if end < start:
        #    log.warning(f"End frame {end} is less than start frame {start} in provided range '{range_str}'.")
        return start, end
    except ValueError:
        # Should not happen with regex match, but catch just in case
        raise ValueError(f"Could not parse integers from frame range string: '{range_str}'")


# --- Nuke Interaction ---
def get_nuke_executable() -> str:
    """Finds the Nuke executable path based on OS and environment."""
    # Select default based on current OS
    if OS == OS_WIN:
        nuke_path = NUKE_EXEC_PATH_WIN
        # List of potential Nuke install locations on Windows
        alternate_paths = [
            "C:\\Program Files\\Nuke*\\Nuke*.exe",
            "C:\\Program Files\\Foundry\\Nuke*\\Nuke*.exe"
        ]
    elif OS == OS_LIN:
        nuke_path = NUKE_EXEC_PATH_LIN
        # List of potential Nuke install locations on Linux
        alternate_paths = [
            "/usr/local/Nuke*/Nuke*",
            "/opt/Nuke*/Nuke*",
            "/opt/Foundry/Nuke*/Nuke*"
        ]
    elif OS == OS_MAC:
        nuke_path = NUKE_EXEC_PATH_MAC
        # List of potential Nuke install locations on Mac
        alternate_paths = [
            "/Applications/Nuke*.app/Contents/MacOS/Nuke*"
        ]
    else:
        # Should not happen if OS detection works
        raise EnvironmentError(f"Unsupported operating system '{OS}' for Nuke.")

    # Validate the default path
    if Path(nuke_path).is_file():
        log.debug(f"Using default Nuke executable for {OS}: {nuke_path}")
        return nuke_path
    
    log.warning(f"Nuke executable not found at default location: '{nuke_path}'. Trying alternate locations...")
    
    # Try checking alternate common install locations
    import glob
    for pattern in alternate_paths:
        possible_paths = glob.glob(pattern)
        if possible_paths:
            # Sort to get the highest version
            possible_paths.sort(reverse=True)
            nuke_path = possible_paths[0]
            log.info(f"Found Nuke executable at alternate location: {nuke_path}")
            return nuke_path
    
    # Additional custom check: look for NUKE_PATH or NUKE_ROOT environment variables
    for env_var in ["NUKE_EXE_PATH", "NUKE_PATH", "NUKE_ROOT"]:
        env_path = os.environ.get(env_var)
        if env_path:
            log.info(f"Checking environment variable {env_var}={env_path}")
            if Path(env_path).is_file() and "nuke" in env_path.lower():
                log.info(f"Using Nuke executable from {env_var}: {env_path}")
                return env_path
            elif Path(env_path).is_dir():
                # If it's a directory, look for nuke executable inside
                possible_execs = list(Path(env_path).glob("**/Nuke*.exe" if OS == OS_WIN else "**/Nuke*"))
                if possible_execs:
                    nuke_path = str(possible_execs[0])
                    log.info(f"Found Nuke executable in {env_var} directory: {nuke_path}")
                    return nuke_path
    
    # If we get here, we failed to find Nuke
    raise ConfigurationError(
        f"Nuke executable not found at default location: '{nuke_path}' or any alternate locations. "
        f"Please ensure Nuke is installed correctly or set the NUKE_EXE_PATH environment variable. "
        f"Expected locations on {OS} include: {', '.join(alternate_paths)}"
    )


# Path to the nuke_ops.py script within this package
NUKE_OPS_SCRIPT_PATH = Path(__file__).parent / "nuke_ops.py"

def run_nuke_action(actions: List[str],
                    script_path: Optional[str] = None,
                    target_nodes: Optional[List[str]] = None,
                    node_name: Optional[str] = None,
                    output_path: Optional[str] = None,
                    frame_range: Optional[Tuple[int, int]] = None,
                    timeout: int = 120) -> Dict[str, Any]:
    """
    Runs the nuke_ops.py script via 'nuke -t' to perform specific actions.

    Args:
        actions: List of actions to perform (e.g., ['get_writes', 'get_deps']).
        script_path: Path to the Nuke script to load (if required by actions).
        target_nodes: List of node names (if required by actions).
        node_name: Single node name (if required by action).
        output_path: Output file path (if required by actions).
        frame_range: Optional tuple (start, end) for frame range override.
        timeout: Timeout in seconds for the Nuke process (default reduced to 120).

    Returns:
        Dictionary containing the results or errors parsed from the Nuke script's JSON output.

    Raises:
        ConfigurationError: If Nuke executable or nuke_ops.py script not found.
        ArchiveError: If the Nuke process fails critically or returns errors indicating failure.
        subprocess.TimeoutExpired: If the process times out.
        FileNotFoundError: If nuke_ops.py script is missing.
        ParsingError: If the JSON output from Nuke cannot be parsed.
    """
    nuke_exe = get_nuke_executable() # Raises ConfigurationError if not found

    if not NUKE_OPS_SCRIPT_PATH.is_file():
        raise FileNotFoundError(f"Core Nuke operations script missing at: {NUKE_OPS_SCRIPT_PATH}")

    # Build the command line arguments for Nuke
    command = [nuke_exe, "-t", str(NUKE_OPS_SCRIPT_PATH)] # -t for terminal mode
    command.extend(["--action"] + actions) # Specify action(s)

    # Add optional arguments only if they have a value
    if script_path:
        command.extend(["--script-path", normalize_path(script_path)])
    if target_nodes: # Pass even if empty list? No, only if non-empty.
        command.extend(["--target-nodes"] + target_nodes)
    if node_name:
        command.extend(["--node-name", node_name])
    if output_path:
        command.extend(["--output-path", normalize_path(output_path)])
    if frame_range:
        # Format frame range tuple as "start-end" string for argparse
        command.extend(["--frame-range", f"{frame_range[0]}-{frame_range[1]}"])

    log.info(f"Running Nuke command with {timeout}s timeout: {' '.join(command)}")
    full_output = "" # Initialize variable to store output for debugging on error

    try:
        # Log start time
        start_time = time.time()
        log.debug(f"Nuke process starting at: {datetime.datetime.now().strftime('%H:%M:%S')}")
        
        # Execute the command using Popen for more control
        with subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace'
        ) as process:
            # Set up progress logging
            elapsed = 0
            stdout_chunks = []
            stderr_chunks = []
            
            while process.poll() is None:
                # Check for timeout
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    process.terminate()
                    log.error(f"Nuke process terminated after {elapsed:.1f}s (exceeded timeout of {timeout}s)")
                    raise subprocess.TimeoutExpired(cmd=command, timeout=timeout)
                
                # Log progress every 10 seconds
                if int(elapsed) % 10 == 0 and int(elapsed) > 0:
                    log.info(f"Nuke process running for {int(elapsed)}s...")
                
                # Non-blocking read from stdout and stderr
                stdout_ready = select.select([process.stdout], [], [], 0.1)[0]
                if stdout_ready:
                    stdout_chunk = process.stdout.read(1024)
                    if stdout_chunk:
                        stdout_chunks.append(stdout_chunk)
                        
                stderr_ready = select.select([process.stderr], [], [], 0.1)[0]
                if stderr_ready:
                    stderr_chunk = process.stderr.read(1024)
                    if stderr_chunk:
                        stderr_chunks.append(stderr_chunk)
                        
                # Small delay to prevent CPU spinning
                time.sleep(0.1)
            
            # Process completed, get final output
            final_stdout, final_stderr = process.communicate()
            if final_stdout:
                stdout_chunks.append(final_stdout)
            if final_stderr:
                stderr_chunks.append(final_stderr)
                
            # Combine all output
            stdout_output = ''.join(stdout_chunks)
            stderr_output = ''.join(stderr_chunks)
            returncode = process.returncode
            
            log.debug(f"Nuke process finished after {elapsed:.1f}s. Exit Code: {returncode}")
            full_output = f"--- Nuke stdout ---\n{stdout_output}\n\n--- Nuke stderr ---\n{stderr_output}"

        # Log the full raw output only at DEBUG level to avoid cluttering logs
        if full_output.strip():
            log.debug(f"Nuke Raw Output (stdout & stderr):\n{full_output.strip()}")

        # --- Process Results ---
        # Even if exit code is non-zero, try parsing stdout for potential error messages from nuke_ops.py
        results = {}
        try:
            results = _parse_nuke_ops_output(stdout_output) # Try parsing JSON from stdout
        except ParsingError as pe:
            # Parsing failed, log error but check exit code before raising fully
            log.error(f"Failed to parse JSON results from Nuke stdout: {pe}")
            if returncode != 0:
                # Nuke failed *and* output is unparseable - raise critical error
                error_message = f"Nuke process failed (Exit Code {returncode}) and output parsing error: {pe}."
                log.error(error_message)
                # Include stderr for context if available
                if stderr_output.strip():
                     error_message += f"\nNuke stderr: {stderr_output.strip()[:1000]}..." # Limit length
                raise ArchiveError(error_message) from pe
            else:
                 # Nuke exited cleanly but output unparseable - strange, raise parsing error
                 raise pe

        # Check for critical errors reported within the parsed JSON results
        if results.get("fatal_error"):
             log.error(f"Nuke script reported fatal error: {results['fatal_error']}")
             raise ArchiveError(f"Fatal error during Nuke execution: {results['fatal_error']}")
        if results.get("load_error"):
             log.error(f"Nuke script failed to load input script: {results['load_error']}")
             raise ArchiveError(f"Nuke failed to load script: {results['load_error']}")

        # If Nuke process had non-zero exit code, but we parsed results, treat as failure but return results
        if returncode != 0:
            error_message = f"Nuke process execution failed (Exit Code {returncode}) for actions: {actions}."
            log.error(error_message)
            results['execution_error'] = error_message # Add flag to results
            # Check if specific action errors were also reported
            action_errors = {k:v for k,v in results.items() if k.endswith('_error') and v}
            if action_errors: log.error(f"Specific action errors reported: {action_errors}")
            # Return results dictionary containing the error flags/messages
            return results

        # If exit code 0 and parsing successful, check for non-fatal action errors
        action_errors = {k:v for k,v in results.items() if k.endswith('_error') and v and k != 'execution_error'}
        if action_errors:
            log.warning(f"Nuke process completed, but reported non-fatal errors during actions: {action_errors}")
            # Proceed, but caller should be aware of these warnings

        log.info(f"Nuke action(s) '{actions}' completed successfully.")
        return results # Return the parsed dictionary

    except FileNotFoundError:
        # This catches if the nuke_exe itself wasn't found by subprocess.run
        raise ConfigurationError(f"Nuke executable not found or permission denied at '{nuke_exe}'. Please ensure Nuke is installed and accessible.") from None
    except subprocess.TimeoutExpired:
        log.error(f"Nuke process timed out after {timeout} seconds for actions: {actions}.")
        log.debug(f"Nuke Raw Output on Timeout:\n{full_output.strip()}") # Log captured output
        raise # Re-raise TimeoutExpired
    except Exception as e:
        # Catch any other unexpected errors during subprocess handling or result processing
        log.exception(f"An unexpected error occurred running Nuke action '{actions}': {e}")
        log.debug(f"Nuke Raw Output on Error:\n{full_output.strip()}") # Log captured output
        # Wrap in ArchiveError for consistent exception type
        raise ArchiveError(f"Failed to run Nuke action '{actions}': {e}") from e


def _parse_nuke_ops_output(output: str) -> Dict[str, Any]:
    """Helper to extract the final JSON results from nuke_ops.py stdout."""
    json_start_tag = "--- NUKE OPS FINAL RESULTS ---"
    json_string = ""
    try:
        # Find the *last* occurrence of the start tag
        json_start_index = output.rindex(json_start_tag)
        # Extract everything after the start tag
        json_string_with_trailer = output[json_start_index + len(json_start_tag):].strip()

        # Clean potential trailing script end tag if present
        json_end_tag = "--- NUKE OPS SCRIPT END ---"
        if json_end_tag in json_string_with_trailer:
             json_string = json_string_with_trailer.split(json_end_tag)[0].strip()
        else:
             # If end tag isn't there, maybe process finished abruptly? Use whole string.
             json_string = json_string_with_trailer

        # Handle case where output might be just tags or empty after tags
        if not json_string:
             log.warning("No JSON content found after result tag in Nuke output.")
             # Check output *before* the tag for errors if content is missing
             output_before_tag = output[:json_start_index] if json_start_index > 0 else output
             if "error" in output_before_tag.lower() or "traceback" in output_before_tag.lower():
                  log.error("Error messages detected in Nuke output before missing JSON results.")
                  # Raise parsing error with hint
                  raise ParsingError("No JSON content found, errors detected in Nuke log before results tag.")
             return {} # Return empty dict if no content and no obvious prior errors

        # Attempt to parse the extracted JSON string
        parsed_json = json.loads(json_string)
        log.debug("Successfully parsed JSON results from Nuke output.")
        return parsed_json

    except ValueError as e: # Catches rindex not found or json.JSONDecodeError
        log.error(f"Failed to find result tag or parse JSON from Nuke output: {e}")
        # Log context around the failure point
        log.debug(f"Full Nuke Output for Parsing Debug:\n{output.strip()}")
        if json_start_tag in output:
             log.debug(f"Problematic JSON String Candidate Tried:\n{json_string}")
        # Raise specific ParsingError
        raise ParsingError(f"Could not retrieve valid JSON results from Nuke: {e}") from e


# --- File System Operations ---
def copy_file_or_sequence(source_path: str, dest_path: str, frame_range: Optional[Tuple[int, int]], dry_run: bool = False) -> List[Tuple[str, str]]:
    """
    Copies a single file or an entire sequence. Uses shutil.copy2.
    Returns list of (source, destination) pairs copied or simulated.
    Raises errors on failure to create directories or copy critical files.
    Logs warnings for missing sequence frames but attempts to continue.
    """
    copied_pairs = []
    start_time = time.time()
    try:
        norm_source = normalize_path(source_path)
        norm_dest = normalize_path(dest_path)
        is_seq = is_sequence(norm_source) # Check based on normalized source path pattern
        target_dir = Path(norm_dest).parent

        # --- Ensure Target Directory Exists ---
        if dry_run:
            # Only log simulation if directory doesn't already exist
            if not target_dir.exists():
                 log.info(f"[DRY RUN] Would ensure directory exists: {target_dir}")
        else:
            try:
                # Create directory if it doesn't exist
                if not target_dir.exists():
                     log.debug(f"Creating target directory: {target_dir}")
                     target_dir.mkdir(parents=True, exist_ok=True)
                elif not target_dir.is_dir():
                     # Path exists but isn't a directory - critical error
                     raise ArchiverError(f"Target path '{target_dir}' exists but is not a directory.")
            except OSError as e:
                # Catch permission errors, etc.
                raise ArchiverError(f"Failed to create target directory '{target_dir}': {e}") from e

        # --- Check for existing destination ---
        if not dry_run and Path(norm_dest).exists() and not is_seq:
            log.warning(f"Destination file already exists: {norm_dest}. Will be overwritten.")
            
        # --- Perform Copy ---
        if is_seq:
            # --- Sequence Copy ---
            if not frame_range: # Frame range is mandatory for sequence copy now
                raise ValueError(f"Frame range must be provided to copy sequence: {norm_source}")
            if not isinstance(frame_range, tuple) or len(frame_range) != 2 or not all(isinstance(f, int) for f in frame_range):
                 raise ValueError(f"Invalid frame_range format: {frame_range}. Expected (start_int, end_int).")

            source_files = expand_sequence_path(norm_source, frame_range)
            dest_files = expand_sequence_path(norm_dest, frame_range) # Expand dest using same range

            if not source_files:
                 raise DependencyError(f"Failed to expand source sequence path '{norm_source}' for range {frame_range}.")
            if len(source_files) != len(dest_files):
                 raise ArchiverError(f"Sequence length mismatch: Source expansion ({len(source_files)}) != Dest expansion ({len(dest_files)}). Src='{norm_source}', Dst='{norm_dest}'")

            total_frames = len(source_files)
            log.info(f"Processing sequence '{Path(norm_source).name}' ({total_frames} frames from {frame_range[0]} to {frame_range[1]})...")
            frames_copied_count = 0
            frames_skipped_count = 0
            copy_errors = []
            
            # Progress reporting thresholds
            report_interval = max(1, min(100, total_frames // 10))  # Report at 10% intervals
            last_report_time = time.time()
            
            for i, (src_frame_path, dst_frame_path) in enumerate(zip(source_files, dest_files)):
                # Progress reporting
                if i % report_interval == 0 or i == total_frames - 1 or time.time() - last_report_time > 5:
                    percent_done = (i / total_frames) * 100
                    elapsed = time.time() - start_time
                    if elapsed > 0 and i > 0:
                        frames_per_sec = i / elapsed
                        est_remaining = (total_frames - i) / frames_per_sec if frames_per_sec > 0 else 0
                        log.info(f"Sequence progress: {i}/{total_frames} frames ({percent_done:.1f}%) - "
                                 f"{frames_per_sec:.1f} frames/sec, ~{est_remaining:.1f}s remaining")
                    else:
                        log.info(f"Sequence progress: {i}/{total_frames} frames ({percent_done:.1f}%)")
                    last_report_time = time.time()
                
                norm_src_frame = normalize_path(src_frame_path)
                norm_dst_frame = normalize_path(dst_frame_path)
                if dry_run:
                    # Simulate validation and copy
                    log.debug(f"[DRY RUN] Would validate and copy: {norm_src_frame} -> {norm_dst_frame}")
                    # Assume validation passes in dry run for reporting
                    copied_pairs.append((norm_src_frame, norm_dst_frame))
                    frames_copied_count += 1
                else:
                    try:
                        # Validate source frame exists just before copying
                        src_frame_obj = Path(norm_src_frame)
                        if not src_frame_obj.is_file():
                             # Log clearly that frame is missing and skip
                             log.warning(f"Skipping missing sequence frame: {norm_src_frame}")
                             frames_skipped_count += 1
                             continue # Go to next frame

                        # Check if destination already exists
                        if Path(norm_dst_frame).exists():
                            log.debug(f"Destination frame already exists, overwriting: {norm_dst_frame}")
                            
                        # Check source file size
                        src_size = src_frame_obj.stat().st_size
                        if src_size == 0:
                            log.warning(f"Source frame has zero size: {norm_src_frame}")
                                
                        # Copy with progress tracking for large files (over 100MB)
                        if src_size > 100 * 1024 * 1024:
                            log.info(f"Copying large frame ({src_size/1024/1024:.1f} MB): {norm_src_frame}")
                            
                        shutil.copy2(norm_src_frame, norm_dst_frame) # copy2 preserves metadata
                        
                        # Verify the copy succeeded and file sizes match
                        if Path(norm_dst_frame).exists():
                            dst_size = Path(norm_dst_frame).stat().st_size
                            if dst_size != src_size:
                                log.warning(f"Size mismatch after copy: Source={src_size} bytes, Dest={dst_size} bytes")
                                
                        copied_pairs.append((norm_src_frame, norm_dst_frame))
                        frames_copied_count += 1
                    except Exception as e:
                        # Catch specific copy errors (permissions, disk full, network issues)
                        error_msg = f"Failed to copy sequence frame {norm_src_frame} to {norm_dst_frame}: {e}"
                        log.error(error_msg)
                        copy_errors.append(error_msg)
                        frames_skipped_count += 1 # Count errors as skipped
                        
                        # If we have multiple consecutive errors, maybe there's a systemic problem
                        if len(copy_errors) >= 3 and all(error_msg in e for e in copy_errors[-3:]):
                            log.error("Multiple consecutive similar errors detected, may indicate a systemic problem")
                        
            total_time = time.time() - start_time
            frames_per_sec = frames_copied_count / total_time if total_time > 0 else 0
            log.info(f"Sequence copy complete: {frames_copied_count} frames copied, {frames_skipped_count} frames skipped in {total_time:.1f}s ({frames_per_sec:.1f} frames/sec)")
            
            # If ALL frames failed or were skipped, raise an error
            if frames_copied_count == 0 and (frames_skipped_count > 0 or copy_errors):
                 raise DependencyError(f"Failed to copy any frames for sequence '{norm_source}'. {frames_skipped_count} frames missing/skipped. First error: {copy_errors[0] if copy_errors else 'All frames missing'}")
            elif copy_errors and frames_copied_count < total_frames * 0.9:  # If less than 90% copied successfully
                 # Raise error for significant failures
                 raise ArchiverError(f"Only copied {frames_copied_count}/{total_frames} frames for sequence '{norm_source}'. Encountered {len(copy_errors)} errors. First error: {copy_errors[0]}")
            elif copy_errors:
                 # Just log a warning if most frames copied successfully
                 log.warning(f"Copied {frames_copied_count}/{total_frames} frames with {len(copy_errors)} errors for sequence '{norm_source}'")

        else:
            # --- Single File Copy ---
            if dry_run:
                log.info(f"[DRY RUN] Would validate and copy single file: {norm_source} -> {norm_dest}")
                copied_pairs.append((norm_source, norm_dest))
            else:
                try:
                    # Validate source file exists just before copy
                    validate_path_exists(norm_source, "Single file dependency") # Will raise if not found
                    
                    # Check file size for large file logging
                    src_size = Path(norm_source).stat().st_size
                    if src_size > 100 * 1024 * 1024:  # 100MB
                        log.info(f"Copying large file ({src_size/1024/1024:.1f} MB): {norm_source} -> {norm_dest}")
                    else:
                        log.debug(f"Copying single file ({src_size/1024:.1f} KB): {norm_source} -> {norm_dest}")
                        
                    shutil.copy2(norm_source, norm_dest)
                    
                    # Verify the copy succeeded
                    if Path(norm_dest).exists():
                        dst_size = Path(norm_dest).stat().st_size
                        if dst_size != src_size:
                            log.warning(f"Size mismatch after copy: Source={src_size} bytes, Dest={dst_size} bytes")
                    
                    copied_pairs.append((norm_source, norm_dest))
                    total_time = time.time() - start_time
                    log.debug(f"File copy completed in {total_time:.2f}s")
                except (DependencyError, Exception) as e:
                    # Re-raise errors during single file copy as ArchiverError
                    raise ArchiverError(f"Failed to copy file {norm_source} to {norm_dest}: {e}") from e

        return copied_pairs

    except Exception as e:
         # Catch unexpected errors in the setup phase (path normalization etc.)
         log.exception(f"Unexpected error during setup for copy operation: {source_path} -> {dest_path}")
         raise ArchiverError(f"Setup failed for copy: {e}") from e


# --- Metadata Extraction ---
def get_metadata_from_path(script_path: str) -> Dict[str, Any]:
    """
    Uses fixfx.data.StudioData (if available) to attempt extracting metadata.
    Returns an empty dict if parsing fails, path is not recognized, or fixfx is unavailable.
    """
    try:
        # Import locally to reduce startup impact and handle missing dependency gracefully
        from fixfx.data.studio_data import StudioData
        from fixfx.data import _patterns # Import patterns to get list of properties

        log.debug(f"Attempting metadata extraction from path: {script_path}")
        sd = StudioData(script_path) # Raises ValueError if no pattern matches

        # Extract only the named groups captured by the matching pattern
        metadata = {}
        if hasattr(sd, '_match') and sd._match:
             # Use groupdict from the match object for accuracy
             metadata = {k: v for k, v in sd._match.groupdict().items() if v is not None and v != ''}
             log.debug(f"Extracted metadata via groupdict: {metadata}")
        else:
             # Fallback: Iterate known properties if match object not exposed (less reliable)
             log.warning("Could not access match object from StudioData, iterating known properties as fallback.")
             for prop in _patterns.PROPERTIES:
                  try:
                       value = getattr(sd, prop, None) # Use getattr with default
                       if value is not None and value != '':
                            metadata[prop] = value
                  except AttributeError:
                       pass # Property might not be applicable to this path pattern
             log.debug(f"Extracted metadata via property iteration: {metadata}")


        if not metadata:
             log.warning(f"No metadata fields were successfully extracted from path: {script_path}")
        else:
             log.info(f"Successfully extracted metadata from path: {metadata}")
        return metadata

    except ValueError as e:
        # StudioData raises ValueError if no pattern matches
        log.warning(f"Path '{script_path}' did not match any known studio data patterns: {e}")
        return {}
    except ImportError:
        # Handle case where fixfx.data is present but _patterns is not? Unlikely.
        log.error("Failed to import fixfx.data components for metadata extraction.")
        return {}
    except Exception as e:
        # Catch any other unexpected errors during StudioData usage
        log.error(f"Unexpected error extracting metadata from path '{script_path}': {e}")
        return {}
