"""Command-line interface for the Fix Archive tool.

Example:
 python -m fix-archive.cli "Z:/proj/bob01/shots/BOB_100/BOB_100_000/BOB_100_000_050_MTS/publish/nuke/BOB_100_000_050_MTS_Comp_v007.nk" \
    --archive-root "W:\proj\bob01\delivery\archive" \
    --vendor "FixFX"

"""

import argparse
import sys
import json
import os
from pathlib import Path
import tempfile
import shutil
import re # Make sure re is imported
import logging # Import logging for setup

# Revert to relative imports as the package directory contains a hyphen
from . import log # Use package logger
from .prune import find_nodes_to_keep, save_pruned_script
from .parser import parse_script_dependencies
from .archiver import archive_project
from .repath import repath_script
from .gizmobake import bake_gizmos_in_script
# Assuming parse_frame_range moved to utils.py
from .utils import get_metadata_from_path, normalize_path, parse_frame_range
from .exceptions import (
    ArchiveError, ConfigurationError, PruningError, ParsingError,
    GizmoError, RepathingError, DependencyError
)


def create_parser() -> argparse.ArgumentParser:
    """Creates the argument parser."""
    parser = argparse.ArgumentParser(
        prog="fix-archive", # Define the program name for help message
        description="Fix Archive Tool. Prepares Nuke scripts and dependencies for archival.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter # Shows defaults in help
    )

    parser.add_argument(
        "script_path",
        type=str,
        help="Path to the source Nuke script (.nk) to archive."
    )
    parser.add_argument(
        "--archive-root",
        type=str,
        required=True,
        help="Root directory where the archive structure will be created."
    )

    # Metadata Group
    metadata_group = parser.add_argument_group('SPT Metadata (Overrides inferred values)')
    metadata_group.add_argument("--vendor", type=str, help="Vendor name (e.g., '123 VFX Company')")
    metadata_group.add_argument("--show", type=str, help="Show name (e.g., 'EXAMPLE')")
    metadata_group.add_argument("--season", type=str, help="Season identifier (e.g., 'Season 1', '1')")
    metadata_group.add_argument("--episode", type=str, help="Episode identifier (e.g., '100', 'E01')")
    metadata_group.add_argument("--shot", type=str, help="Shot identifier (e.g., 'EXA100_010_010')")

    # Options Group
    options_group = parser.add_argument_group('Archiving Options')
    options_group.add_argument(
        "--bake-gizmos",
        action="store_true",
        help="Bake non-native gizmos into Group nodes before archiving."
    )
    options_group.add_argument(
        "--update-script",
        action="store_true",
        help="Save the final archived Nuke script with repathed file nodes (relative to archive). Operates on the pruned/baked script."
    )
    options_group.add_argument(
        "--frame-range",
        type=str,
        help="Specify frame range for sequences (e.g., '1001-1100' or '1050'). Overrides detection."
    )
    options_group.add_argument(
        "--report-json",
        type=str,
        metavar="OUTPUT.json",
        help="Write a JSON manifest detailing the archive process and file mappings."
    )
    options_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the process without copying files or writing the final script/report."
    )

    # General Arguments
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=0,
        help="Increase logging verbosity (-v for INFO, -vv for DEBUG)."
    )
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s'
    )

    return parser

# Removed parse_frame_range - Assuming it's moved to utils.py

def main(args=None):
    """Main execution function."""
    if args is None:
        args = sys.argv[1:]

    parser = create_parser()
    parsed_args = parser.parse_args(args)

    # --- Configure Logging Verbosity ---
    # Set level on the logger obtained from __init__
    log_level = logging.WARNING # Default
    if parsed_args.verbose == 1:
        log_level = logging.INFO
    elif parsed_args.verbose >= 2:
        log_level = logging.DEBUG

    # Attempt to set level - assumes logger handlers are configured to respect this
    try:
        # --- DEBUGGING --- 
        print(f"[Debug CLI] Type of 'log' before setLevel: {type(log)}", file=sys.stderr)
        print(f"[Debug CLI] Value of 'log' before setLevel: {repr(log)}", file=sys.stderr)
        print(f"[Debug CLI] Attempting to set level to: {log_level} ({logging.getLevelName(log_level)})", file=sys.stderr)
        # --- END DEBUGGING ---
        
        log.setLevel(log_level)
        
        # If using fixfx logger, it might configure handlers already.
        # If standalone, ensure handlers are present.
        if not log.hasHandlers():
             handler = logging.StreamHandler(sys.stdout)
             formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s]: %(message)s', '%Y-%m-%d %H:%M:%S')
             handler.setFormatter(formatter)
             log.addHandler(handler)
        # Set level on handlers too if they exist
        for handler in log.handlers:
             handler.setLevel(log_level)
        log.info(f"Log level set to {logging.getLevelName(log_level)}")
    except Exception as log_e:
        # --- DEBUGGING --- 
        print(f"[Debug CLI] Exception during log setup: {type(log_e).__name__}: {log_e}", file=sys.stderr)
        # --- END DEBUGGING ---
        # Use standard logging temporarily if our logger failed catastrophically
        logging.warning(f"Could not dynamically set log level using imported logger: {log_e}")


    original_script_path = None
    pruned_script_path_temp = None # Path to temp file after pruning
    baked_script_path_temp = None # Path to temp file after baking (if done)
    final_script_content = None   # Content to be saved at the end
    archive_map = {}
    temp_files_to_clean = []

    try:
        log.info(f"--- Starting Fix Archive Tool ---")
        log.info(f"Processing script: {parsed_args.script_path}")
        log.info(f"Archive Root: {parsed_args.archive_root}")
        if parsed_args.dry_run:
            log.warning("--- DRY RUN MODE ENABLED ---")

        # --- Validate Original Script Path ---
        original_script_path = normalize_path(parsed_args.script_path)
        if not Path(original_script_path).exists():
             raise ConfigurationError(f"Original script path not found: {original_script_path}")
        log.debug(f"Validated original script exists: {original_script_path}")

        # --- Prepare Metadata ---
        log.debug("Preparing metadata...")
        inferred_metadata = get_metadata_from_path(original_script_path)
        metadata = {
            "vendor": parsed_args.vendor or inferred_metadata.get("vendor", "UNKNOWN_VENDOR"),
            "show": parsed_args.show or inferred_metadata.get("project", "UNKNOWN_SHOW"),
            "season": parsed_args.season or inferred_metadata.get("season", ""),
            "episode": parsed_args.episode or inferred_metadata.get("episode", "UNKNOWN_EPISODE"),
            "shot": parsed_args.shot or inferred_metadata.get("shot", None),
        }
        # Attempt to construct shot name if missing
        if not metadata["shot"] and all(k in inferred_metadata for k in ("episode", "sequence", "shot")): # Check if 'shot' number exists
             # Assuming StudioData parses 'sequence' and 'shot' number correctly
             ep = inferred_metadata.get("episode")
             sq = inferred_metadata.get("sequence")
             sh_num = inferred_metadata.get("shot") # Use the 'shot' field if it holds the number
             sh_tag = inferred_metadata.get("tag", "") # Add tag if present
             if ep and sq and sh_num:
                   constructed_shot = f"{ep}_{sq}_{sh_num}"
                   if sh_tag: constructed_shot += f"_{sh_tag}"
                   log.info(f"Constructed shot name from inferred parts: {constructed_shot}")
                   metadata["shot"] = constructed_shot

        # Final validation for required metadata fields
        for key in ["vendor", "show", "shot"]: # Episode might not always be required? Check SPT spec.
             if not metadata[key] or "UNKNOWN" in str(metadata[key]):
                  raise ConfigurationError(f"Required metadata '{key}' is missing or could not be inferred. Please provide via CLI (--{key}). Value found: '{metadata[key]}'")
        log.info(f"Using metadata: {metadata}")


        # --- Parse Frame Range Override ---
        frame_range_override = None
        if parsed_args.frame_range:
            try:
                frame_range_override = parse_frame_range(parsed_args.frame_range) # Use utils function
                if frame_range_override:
                     log.info(f"Using frame range override: {frame_range_override}")
            except ValueError as e:
                 parser.error(str(e)) # argparse handles exit

        # === Workflow Steps ===

        # 1. Pruning: Identify nodes and save pruned script to temp location
        log.info("--- Step 1: Identifying nodes to keep and pruning script ---")
        nodes_to_keep = find_nodes_to_keep(original_script_path)
        if not nodes_to_keep:
            raise PruningError("Failed to identify any nodes to keep during pruning (including target writes).")

        if parsed_args.dry_run:
             log.info(f"[DRY RUN] Would keep {len(nodes_to_keep)} nodes (including backdrops).")
             script_path_for_following_steps = original_script_path
        else:
             pruned_script_path_temp = save_pruned_script(original_script_path, nodes_to_keep)
             if not pruned_script_path_temp or not Path(pruned_script_path_temp).exists():
                  raise PruningError("save_pruned_script did not return a valid temporary script path.")
             temp_files_to_clean.append(pruned_script_path_temp) # Mark for cleanup
             script_path_for_following_steps = pruned_script_path_temp
             log.info(f"Pruned script saved temporarily to: {pruned_script_path_temp}")


        # 2. Parsing Dependencies (from the pruned script)
        log.info(f"--- Step 2: Parsing dependencies from: {script_path_for_following_steps} ---")
        dependency_manifest = parse_script_dependencies(script_path_for_following_steps, frame_range_override)
        log.info(f"Found {len(dependency_manifest)} file references in pruned script.")
        log.debug(f"Dependency Manifest:\n{json.dumps(dependency_manifest, indent=2)}")


        # 3. Archiving Files (based on pruned script's dependencies)
        log.info("--- Step 3: Archiving files ---")
        archive_map = archive_project(
            script_path_for_following_steps, # Archive the (temp) pruned script
            dependency_manifest,
            parsed_args.archive_root,
            metadata,
            parsed_args.dry_run
        )
        log.info("File archiving step completed.")
        log.debug(f"Archive Map:\n{json.dumps(archive_map, indent=2)}")

        # Determine final script path in archive *before* potential baking/repathing
        final_script_archive_path = archive_map.get("script")
        if not final_script_archive_path:
             raise ArchiverError("Failed to determine the final archived script path in the archive map.")
        log.info(f"Final archived script location determined as: {final_script_archive_path}")


        # --- Post-Archive Processing ---
        script_to_process_further = script_path_for_following_steps

        # 4. Gizmo Baking (Optional, operates on the script used for parsing)
        if parsed_args.bake_gizmos:
            log.info(f"--- Step 4: Baking gizmos in: {script_to_process_further} ---")
            baked_script_path_result = bake_gizmos_in_script(script_to_process_further, parsed_args.dry_run)

            if baked_script_path_result != script_to_process_further: # Check if baking actually produced a *new* temp file path
                 log.info(f"Using baked script for further processing: {baked_script_path_result}")
                 if baked_script_path_result not in temp_files_to_clean:
                      temp_files_to_clean.append(baked_script_path_result)
                 script_to_process_further = baked_script_path_result # Update path for repathing
                 baked_script_path_temp = baked_script_path_result
            else:
                 log.info("No baking performed or required.")
                 baked_script_path_temp = None


        # 5. Repathing Script Content (If update requested, operates on latest temp script version)
        current_script_content = None # Content read from the script file
        if parsed_args.update_script:
             log.info(f"--- Step 5: Repathing script content from: {script_to_process_further} ---")
             if parsed_args.dry_run:
                  log.info("[DRY RUN] Would repath script content.")
                  final_script_content = "[DRY RUN - Content not generated]" # Placeholder for dry run
             else:
                  # Read the content of the script that might have been baked
                  try:
                      with open(script_to_process_further, 'r', encoding='utf-8', errors='replace') as f:
                          current_script_content = f.read()
                  except Exception as read_e:
                       raise RepathingError(f"Failed to read script content from '{script_to_process_further}' before repathing: {read_e}") from read_e

                  # Perform the repathing on the content string
                  try:
                      final_script_content = repath_script(
                           current_script_content,
                           archive_map,
                           final_script_archive_path # Repath relative to final destination
                      )
                      log.info("Script content repathed successfully.")
                  except Exception as e:
                      log.error(f"Failed to repath script content: {e}. Will attempt to save unrepathed content if possible.")
                      final_script_content = current_script_content # Fallback to content before repathing


        # 6. Saving Final Script (If update requested)
        if parsed_args.update_script:
             log.info("--- Step 6: Saving final script ---")
             if final_script_content is None: # Check if content was prepared
                 if not parsed_args.dry_run:
                     # Content wasn't prepared (e.g., dry run in repath step, or read failed)
                     # Read again from the last known temp script path
                     log.warning("Repathing skipped or failed, reading last known script version for saving.")
                     try:
                         with open(script_to_process_further, 'r', encoding='utf-8', errors='replace') as f:
                             final_script_content = f.read()
                         log.info(f"Read content from {script_to_process_further} for final save.")
                     except Exception as read_e:
                         raise ArchiveError(f"Could not read script '{script_to_process_further}' to save unrepathed version: {read_e}")
                 else:
                     # If still None in dry run, something is wrong or content placeholder used
                     if final_script_content is None:
                           final_script_content = "[DRY RUN - Cannot determine content]"

             # Now, save the content (or simulate)
             if parsed_args.dry_run:
                 log.info(f"[DRY RUN] Would write final script content to: {final_script_archive_path}")
             elif final_script_content and "[DRY RUN" not in final_script_content:
                 log.info(f"Writing final {'(repathed/baked)' if final_script_content != current_script_content else '(pruned)'} script to: {final_script_archive_path}")
                 try:
                     # Archiver should have created the dir, but ensure it exists
                     Path(final_script_archive_path).parent.mkdir(parents=True, exist_ok=True)
                     with open(final_script_archive_path, 'w', encoding='utf-8') as f:
                         f.write(final_script_content)
                     log.info("Successfully wrote final script.")
                 except Exception as e:
                     raise ArchiveError(f"Failed to write final script to {final_script_archive_path}: {e}") from e
             else:
                 # This case implies content is missing even after trying to read again
                 raise ArchiveError("Could not prepare final script content for saving (content missing or invalid).")

        elif not parsed_args.dry_run:
             # If not updating script, the pruned (but not baked/repathed) script initially copied by archiver is final.
             log.info("Skipping final script save as --update-script was not specified. Archived script is the pruned version.")
             # Note: If baking happened, the baked *content* exists only in the temp file which will be deleted.


        # 7. Generate Report (Optional)
        if parsed_args.report_json:
            log.info("--- Step 7: Generating report ---")
            report_path = normalize_path(parsed_args.report_json)
            if parsed_args.dry_run:
                log.info(f"[DRY RUN] Would write JSON report to: {report_path}")
            else:
                log.info(f"Writing JSON report to: {report_path}")
                try:
                    report_data = {
                        "source_script": original_script_path,
                        "archive_root": parsed_args.archive_root,
                        "metadata": metadata,
                        "options": vars(parsed_args), # Save all parsed args
                        "pruned_script_temporary_path": pruned_script_path_temp if not parsed_args.dry_run else "[DRY RUN]",
                        "baked_script_temporary_path": baked_script_path_temp if not parsed_args.dry_run and baked_script_path_temp else "[N/A or DRY RUN]",
                        "final_archived_script_path": final_script_archive_path,
                        "archive_map": archive_map # Map of original_dependency_path -> archive_path
                    }
                    # Ensure parent directory exists for the report
                    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
                    with open(report_path, 'w', encoding='utf-8') as f:
                        json.dump(report_data, f, indent=2)
                    log.info(f"Successfully wrote JSON report to {report_path}.")
                except Exception as e:
                    log.error(f"Failed to write JSON report to {report_path}: {e}") # Log error but don't fail process


        log.info(f"--- Fix Archive process completed successfully for {original_script_path} ---")

    except (ArchiveError, ConfigurationError, PruningError, ParsingError, GizmoError, RepathingError, DependencyError) as e:
        log.error(f"ARCHIVE FAILED: {e}")
        # Optionally log traceback for specific errors if needed for debugging
        # if isinstance(e, ParsingError): log.exception("Parsing error traceback:")
        sys.exit(1) # Exit with error code
    except Exception as e:
        log.exception(f"An unexpected critical error occurred during the archive process: {e}") # Log full traceback
        sys.exit(1) # Exit with error code
    finally:
        # --- Cleanup Temporary Files ---
        if temp_files_to_clean:
             log.debug(f"Cleaning up temporary files: {temp_files_to_clean}")
             for temp_file in temp_files_to_clean:
                 try:
                     if temp_file and Path(temp_file).exists():
                         os.remove(temp_file)
                         log.debug(f"Removed temp file: {temp_file}")
                 except OSError as e:
                     # Log warning but don't fail the whole process for cleanup error
                     log.warning(f"Failed to remove temporary file {temp_file}: {e}")

if __name__ == "__main__":
    # Allows running the CLI using `python -m fix-archive.cli` or directly
    try:
        main()
    except ImportError as e:
        print(f"Error: {e}")
        print("Try running with: python -m fix-archive.cli [args]")
        sys.exit(1)