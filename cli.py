# fixarc/cli.py
"""
Command-line interface for the Fix Archive (fixarc) tool.

Orchestrates the archival process:
1. Parses arguments and prepares metadata.
2. Determines the final destination path for the processed Nuke script.
3. Executes the core Nuke processing (_nuke_executor.py) via `nuke -t`.
4. Parses results from the Nuke process (status, dependency map).
5. Copies required dependency files using robust methods.
6. Generates an optional report.
"""

import argparse
import sys
import json
from pathlib import Path
import logging # Import standard logging for setup
import time

from typing import Dict, Any, Optional, List
from fixenv import normalize_path
# Use package-level logger and __version__
from . import log, __version__
from . import constants  # Import constants module to access DEFAULT_VENDOR_NAME
from .archive_utils import get_archive_script_path # Specific utility for script path
from .utils import (
    get_metadata_from_path, execute_nuke_archive_process, copy_files_robustly
)
from .exceptions import (
    ConfigurationError, DependencyError, NukeExecutionError, ParsingError, RepathingError, GizmoError, PruningError, ArchiverError
)


def create_parser() -> argparse.ArgumentParser:
    """Creates the argument parser for the command-line interface."""
    parser = argparse.ArgumentParser(
        prog="fixarc", # Program name for help messages
        description=f"Fix Archive Tool v{__version__}. Prepares Nuke scripts and dependencies for archival.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter # Shows default values in help
    )

    # --- Positional Arguments ---
    parser.add_argument(
        "script_path",
        type=str,
        help="Path to the source Nuke script (.nk) to process and archive."
    )

    # --- Required Arguments ---
    parser.add_argument(
        "--archive-root",
        type=str,
        required=True,
        help="Root directory where the standardized archive structure will be created."
    )

    # --- Metadata Group (Overrides inferred values) ---
    metadata_group = parser.add_argument_group('SPT Metadata (Overrides inferred values)')
    metadata_group.add_argument(
        "--vendor", type=str, 
        default=constants.DEFAULT_VENDOR_NAME,
        help=f"Vendor name (e.g., 'FixFX'). Defaults to {constants.DEFAULT_VENDOR_NAME} from your fixenv config if available."
    )
    metadata_group.add_argument(
        "--show", type=str,
        help="Show name (e.g., 'bob01'). Will attempt to infer from path if not provided."
    )
    metadata_group.add_argument(
        "--episode", type=str,
        help="Episode identifier (e.g., 'BOB_100'). Will attempt to infer if not provided."
    )
    metadata_group.add_argument(
        "--shot", type=str,
        help="Shot identifier (e.g., 'BOB_100_000_050_MTS'). Will attempt to infer if not provided."
    )

    # --- Options Group ---
    options_group = parser.add_argument_group('Processing Options')
    options_group.add_argument(
        "--bake-gizmos",
        action="store_true",
        help="Bake non-native gizmos into Group nodes within the final archived script."
    )
    options_group.add_argument(
        "--update-script",
        action="store_true",
        help="Repath file nodes within the final archived script to be relative to the archive structure. (Script is always saved to archive)."
    )
    # --frame-range is currently handled *inside* Nuke if needed for parsing,
    # but could be passed if copy needed range explicitly? Less needed now.
    # options_group.add_argument(
    #     "--frame-range", type=str,
    #     help="DEPRECATED? Specify frame range for sequences (e.g., '1001-1100'). Nuke process should handle this."
    # )
    options_group.add_argument(
        "--report-json",
        type=str,
        metavar="OUTPUT.json",
        help="Write a JSON manifest detailing the archive process and file mappings."
    )
    options_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate Nuke processing and file mapping. Skips saving the final script and copying files."
    )

    # --- General Arguments ---
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=1,
        help="Increase logging verbosity (-v for INFO, -vv for DEBUG)."
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}' # Use __version__ from __init__
    )

    return parser


def _setup_logging(verbosity: int) -> None:
    """Configures logging level based on verbosity flags."""
    level = logging.WARNING # Default
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG

    try:
        # Set level on the root logger obtained from __init__
        log.setLevel(level)
        
        # Check if the logger has any handlers; if not, add a console handler
        if not log.handlers:
            # Create a console handler
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(level)
            # Create a formatter
            formatter = logging.Formatter('%(asctime)s [%(levelname)-7s] [%(name)s]: %(message)s')
            console_handler.setFormatter(formatter)
            # Add the handler to the logger
            log.addHandler(console_handler)
            log.debug("Added console handler to logger")
        else:
            # Ensure handlers also respect the level
            for handler in log.handlers:
                handler.setLevel(level)
                
        # Ensure propagation to root logger is enabled
        log.propagate = True
        
        # Test log output
        log.debug("Debug logging enabled")
        log.info(f"Logging level set to {logging.getLevelName(level)}")
    except Exception as e:
        # Fallback to standard logging if our logger object is problematic
        logging.basicConfig(level=level, format='%(asctime)s [%(levelname)-7s] [%(name)s]: %(message)s')
        logging.warning(f"Could not configure package logger, using basicConfig. Error: {e}")
        log.warning(f"Logging level set to {logging.getLevelName(level)} (basic config)")
        
    # Always output something to stderr to verify logging is working
    sys.stderr.write(f"Logging initialized at level: {logging.getLevelName(level)}\n")

def _prepare_and_validate_metadata(args: argparse.Namespace, script_path: str) -> Dict[str, Any]:
    """Infers, merges, and validates required metadata."""
    log.debug("Preparing and validating metadata...")
    inferred = get_metadata_from_path(script_path) # Uses fixenv if available
    
    # Log what was inferred from the path
    if inferred:
        log.debug(f"Metadata inferred from path: {inferred}")
    else:
        log.warning("No metadata could be inferred from the script path.")

    # Try to get a complete shot identifier directly from inferred data first
    inferred_shot = inferred.get("shot_name") or inferred.get("shot")
    
    # If shot wasn't directly available, check if we have the components to build it
    if not inferred_shot and all(k in inferred for k in ("episode", "sequence", "shot_number")):
        ep = inferred.get("episode")
        sq = inferred.get("sequence")
        sh_num = inferred.get("shot_number") or inferred.get("shot") # Could be named differently
        sh_tag = inferred.get("tag", "")
        if ep and sq and sh_num:
            inferred_shot = f"{ep}_{sq}_{sh_num}"
            if sh_tag: inferred_shot += f"_{sh_tag}"
            log.info(f"Constructed shot name from inferred parts: {inferred_shot}")

    # Build metadata including sequence and tag for full context in Nuke executor
    metadata = {
        "vendor": args.vendor or constants.DEFAULT_VENDOR_NAME,
        "show": args.show or inferred.get("project") or inferred.get("show"),  # Map inferred 'project' to 'show'
        "episode": args.episode or inferred.get("episode"),
        # Include sequence and tag from inferred StudioData for dependency mapping
        "sequence": inferred.get("sequence"),
        "tag": inferred.get("tag"),
        "shot": args.shot or inferred_shot,
    }
    
    # Log what we got from CLI vs inference
    for key, value in metadata.items():
        cli_value = getattr(args, key, None)
        if cli_value:
            log.debug(f"Using CLI-provided value for '{key}': {cli_value}")
        elif value:
            log.debug(f"Using inferred value for '{key}': {value}")

    # Validate required fields for SPT structure
    required_keys = ["vendor", "show", "episode", "shot"]  # sequence and tag are optional for CLI
    missing = [k for k in required_keys if not metadata.get(k)]
    
    if missing:
        # For more helpful error message, indicate which values couldn't be inferred
        missing_args = [f"--{k}" for k in missing]
        
        # Compose a helpful error message with examples
        error_msg = f"Missing required metadata for archive structure. Please provide via CLI ({', '.join(missing_args)})."
        
        # Add path inference suggestion
        error_msg += "\n\nAlternatively, ensure your script path follows the studio pattern for automatic inference."
        error_msg += "\nExample path: /proj/bob01/shots/BOB_100/BOB_100_010_CMP/publish/nuke/my_script.nk"
        
        # Add what we found (or didn't find)
        error_msg += f"\n\nRequired: {required_keys}"
        error_msg += f"\nFound: {metadata}"
        
        raise ConfigurationError(error_msg)

    log.info(f"Using metadata: {metadata}")
    return metadata


# Main execution function
def main(args: Optional[List[str]] = None) -> None:
    """Main CLI execution workflow."""
    if args is None:
        args = sys.argv[1:]

    parser = create_parser()
    parsed_args = parser.parse_args(args)

    # --- Setup ---
    start_time = time.time()
    _setup_logging(parsed_args.verbose)
    log.info(f"--- Starting Fix Archive Tool v{__version__} ---")
    if parsed_args.dry_run: log.warning("--- DRY RUN MODE ENABLED ---")
    
    # Log the vendor source
    if parsed_args.vendor == constants.DEFAULT_VENDOR_NAME:
        log.debug(f"Using default vendor '{constants.DEFAULT_VENDOR_NAME}' from configuration")
    else:
        log.debug(f"Using vendor '{parsed_args.vendor}' specified via --vendor argument")

    original_script_path: Optional[str] = None
    final_script_archive_path: Optional[str] = None
    nuke_results: Dict[str, Any] = {}
    copy_success_count = 0
    copy_failure_count = 0

    try:
        # --- Input Validation and Metadata Preparation ---
        original_script_path = normalize_path(parsed_args.script_path)
        archive_root = normalize_path(parsed_args.archive_root)
        if not Path(original_script_path).is_file():
             raise ConfigurationError(f"Input script not found or is not a file: {original_script_path}")
        if not Path(archive_root).exists():
             log.warning(f"Archive root directory does not exist: {archive_root}. It will be created.")
        elif not Path(archive_root).is_dir():
             raise ConfigurationError(f"Archive root path exists but is not a directory: {archive_root}")
             
        # --- Input Path Format Log ---
        script_filename = Path(original_script_path).name
        script_dir = str(Path(original_script_path).parent)
        log.info(f"Input script: {script_filename}")
        log.debug(f"Script directory: {script_dir}")

        # Prepare metadata (infer from path or use CLI args)
        try:
            metadata = _prepare_and_validate_metadata(parsed_args, original_script_path)
        except ConfigurationError as e:
            # Add helpful hint about using verbose flag for more info
            if parsed_args.verbose < 2:  # If not already in debug mode
                raise ConfigurationError(f"{str(e)}\n\nHint: Run with -vv for detailed debug logging") from None
            else:
                raise

        # Determine the final path for the Nuke script *before* calling Nuke process
        final_script_archive_path = get_archive_script_path(
            archive_root, metadata, Path(original_script_path).name
        )
        log.info(f"Calculated final archive path for script: {final_script_archive_path}")

        # --- Execute Core Nuke Process ---
        log.info("--- Step 1: Executing Nuke Process (Load, Prune, Bake, Repath, Save) ---")
        if parsed_args.dry_run:
            log.info("[DRY RUN] Skipping Nuke process execution.")
            # Simulate successful Nuke results for dry run of subsequent steps
            nuke_results = {
                "status": "success",
                "final_saved_script_path": final_script_archive_path,
                "dependencies_to_copy": {"[DRY RUN Placeholder Source]": "[DRY RUN Placeholder Dest]"},
                "errors": [],
                "nodes_kept": ["[DRY RUN]"],
                "gizmos_baked_count": 0,
                "repath_count": 0
            }
        else:
            nuke_results = execute_nuke_archive_process(
                input_script_path=original_script_path,
                archive_root=archive_root,
                final_script_archive_path=final_script_archive_path,
                metadata=metadata,
                bake_gizmos=parsed_args.bake_gizmos,
                repath_script_flag=parsed_args.update_script,
                # timeout=300 # Optional: Adjust timeout if needed
            )
            # execute_nuke_archive_process raises NukeExecutionError on failure

        # --- Copy Dependencies ---
        log.info("--- Step 2: Copying Dependencies ---")
        # Add log verification output
        sys.stderr.write("Direct stderr write: Starting dependency copy step\n")
        sys.stdout.write("Direct stdout write: Starting dependency copy step\n")
        
        dependencies_to_copy = nuke_results.get("dependencies_to_copy", {})
        if not dependencies_to_copy:
             log.warning("Nuke process returned no dependencies to copy.")
        else:
             # copy_files_robustly handles dry run internally based on flag
             copy_success_count, copy_failure_count = copy_files_robustly(
                 dependencies_to_copy,
                 parsed_args.dry_run
             )
             if copy_failure_count > 0:
                  log.error(f"{copy_failure_count} dependencies failed to copy. Check previous logs.")
                  # Decide if this should be a fatal error? Maybe not, depends on importance.
                  # For now, log as error but continue to report generation.

        # --- Generate Report (Optional) ---
        if parsed_args.report_json:
            log.info("--- Step 3: Generating Report ---")
            report_path = normalize_path(parsed_args.report_json)
            if parsed_args.dry_run:
                log.info(f"[DRY RUN] Would write JSON report to: {report_path}")
            else:
                log.info(f"Writing JSON report to: {report_path}")
                try:
                    # Combine all relevant info into the report
                    report_data = {
                        "process_start_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_time)),
                        "process_duration_seconds": round(time.time() - start_time, 2),
                        "fixarc_version": __version__,
                        "source_script": original_script_path,
                        "archive_root": archive_root,
                        "cli_options": vars(parsed_args), # Store command line args used
                        "metadata_used": metadata,
                        "nuke_process_results": nuke_results, # Include full Nuke output dict
                        "file_copy_summary": {
                            "success_count": copy_success_count,
                            "failure_count": copy_failure_count,
                        }
                        # Archive map (dependencies_to_copy) is already inside nuke_results
                    }
                    # Ensure parent directory exists for the report
                    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(report_path, 'w', encoding='utf-8') as f:
                        json.dump(report_data, f, indent=2, ensure_ascii=False)
                    log.info(f"Successfully wrote JSON report to {report_path}.")
                except Exception as e:
                    # Log report writing error but don't fail the whole process
                    log.error(f"Failed to write JSON report to {report_path}: {e}")

        # --- Final Summary ---
        total_time = time.time() - start_time
        summary_status = "completed successfully" if copy_failure_count == 0 else f"completed with {copy_failure_count} copy failures"
        log.info(f"--- Fix Archive process {summary_status} in {total_time:.2f} seconds ---")
        if copy_failure_count > 0:
             log.error("Please review logs for details on file copy failures.")
             sys.exit(1) # Exit with error code if copying failed

    except (ConfigurationError, PruningError, ParsingError, DependencyError, NukeExecutionError, ArchiverError, RepathingError, GizmoError) as e:
        log.error(f"ARCHIVE FAILED: ({type(e).__name__}) {e}")
        # log.debug("Traceback:", exc_info=True) # Add traceback at debug level
        sys.exit(1) # Exit with error code for specific handled exceptions
    except Exception as e:
        log.exception(f"An unexpected critical error occurred: {e}") # Log full traceback for unexpected
        sys.exit(1) # Exit with error code

if __name__ == "__main__":
    # Allows running the CLI using `python -m fixarc.cli`
    main()