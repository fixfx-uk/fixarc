import os
import logging
import glob
import sys

# Attempt to use the same logging setup as the main application
log = None
try:
    from fixfx import log
except ImportError:
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)-7s] [%(name)s]: %(message)s'
    )
    log = logging.getLogger("fixarc.ui.data_utils")

def get_default_base_path():
    """
    Attempts to get the default base project path.
    1. Tries fixenv.constants.FIXSTORE_DRIVE + '/proj'.
    2. Falls back to an environment variable 'FIXSTORE_DRIVE' + '/proj'.
    3. Returns a placeholder or raises an error if none are found.
    """
    try:
        import fixenv
        if hasattr(fixenv.constants, 'FIXSTORE_DRIVE') and fixenv.constants.FIXSTORE_DRIVE:
            log.debug(f"Using FIXSTORE_DRIVE from fixenv.constants: {fixenv.constants.FIXSTORE_DRIVE}")
            return os.path.join(fixenv.constants.FIXSTORE_DRIVE, "proj")
    except ImportError:
        log.debug("fixenv.constants not available.")
    
    # Fallback to environment variable
    fixstore_drive_env = os.environ.get("FIXSTORE_DRIVE")
    if fixstore_drive_env:
        log.debug(f"Using FIXSTORE_DRIVE from environment variable: {fixstore_drive_env}")
        return os.path.join(fixstore_drive_env, "proj")
    
    log.warning("FIXSTORE_DRIVE not found in fixenv.constants or environment. Please set a base path manually.")
    # For UI, returning None or a placeholder might be better than raising an error immediately
    return None 

def get_projects(base_path):
    """Lists project directories directly under the base_path."""
    if not base_path or not os.path.isdir(base_path):
        return []
    try:
        return sorted([d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))])
    except OSError as e:
        log.error(f"Error listing projects in {base_path}: {e}")
        return []

def get_episodes(base_path, project_name):
    """Lists episode directories under <base_path>/<project_name>/shots/."""
    if not all([base_path, project_name]):
        return []
    shots_path = os.path.join(base_path, project_name, "shots")
    if not os.path.isdir(shots_path):
        return []
    try:
        return sorted([d for d in os.listdir(shots_path) if os.path.isdir(os.path.join(shots_path, d))])
    except OSError as e:
        log.error(f"Error listing episodes in {shots_path}: {e}")
        return []
def get_sequences(base_path, project_name, episode_names):
    """
    Lists sequence directories under the specified episodes.
    
    Args:
        base_path (str): Base path containing projects
        project_name (str): Name of the project
        episode_names (list): List of episode names to search sequences under
        
    Returns:
        list: Sorted list of unique sequence names found under the specified episodes
        
    Path structure:
        <base_path>/<project_name>/shots/<episode_name>/<sequence_name>
    """
    if not all([base_path, project_name]) or not episode_names:
        return []
    
    all_sequences = set()
    for episode_name in episode_names:
        episode_path = os.path.join(base_path, project_name, "shots", episode_name)
        if not os.path.isdir(episode_path):
            continue
        try:
            sequences_in_episode = [d for d in os.listdir(episode_path) if os.path.isdir(os.path.join(episode_path, d))]
            all_sequences.update(sequences_in_episode)
        except OSError as e:
            log.error(f"Error listing sequences in {episode_path}: {e}")
    return sorted(list(all_sequences))

def get_shots(base_path, project_name, episode_names, sequence_names):
    """
    Lists shot directories.
    Filters by selected project, then by selected episodes, then by selected sequences.
    Path structure: <base_path>/<project>/shots/<episode>/<sequence>/<shot>
    """
    if not all([base_path, project_name]):
        return []

    shots = set()
    
    # If no episodes selected, we might be looking for shots directly under project/shots (if flat)
    # or we should imply all episodes. For this UI, let's build paths iteratively.
    
    paths_to_scan_for_shots = []
    if not episode_names: # Consider all episodes if none are specified for shot listing
        _episodes = get_episodes(base_path, project_name)
        if not _episodes: # No episodes found at all
             return []
        for episode_name in _episodes:
            if not sequence_names: # Consider all sequences under this episode
                _sequences = get_sequences(base_path, project_name, [episode_name])
                if not _sequences: # No sequences found in this episode
                    episode_path = os.path.join(base_path, project_name, "shots", episode_name)
                    # Check if shots are directly under episode (unlikely but covering a case)
                    if os.path.isdir(episode_path): paths_to_scan_for_shots.append(episode_path)
                    continue
                for seq_name in _sequences:
                    paths_to_scan_for_shots.append(os.path.join(base_path, project_name, "shots", episode_name, seq_name))
            else: # Specific sequences selected
                for seq_name in sequence_names:
                    # Check if this sequence exists under this episode
                    seq_path = os.path.join(base_path, project_name, "shots", episode_name, seq_name)
                    if os.path.isdir(seq_path):
                         paths_to_scan_for_shots.append(seq_path)
    else: # Specific episodes selected
        for episode_name in episode_names:
            if not sequence_names: # Consider all sequences under this specific episode
                _sequences = get_sequences(base_path, project_name, [episode_name])
                if not _sequences:
                    episode_path = os.path.join(base_path, project_name, "shots", episode_name)
                    if os.path.isdir(episode_path): paths_to_scan_for_shots.append(episode_path)
                    continue
                for seq_name in _sequences:
                    paths_to_scan_for_shots.append(os.path.join(base_path, project_name, "shots", episode_name, seq_name))
            else: # Specific sequences selected under specific episodes
                for seq_name in sequence_names:
                    seq_path = os.path.join(base_path, project_name, "shots", episode_name, seq_name)
                    if os.path.isdir(seq_path):
                        paths_to_scan_for_shots.append(seq_path)

    # Remove duplicates just in case
    paths_to_scan_for_shots = sorted(list(set(paths_to_scan_for_shots)))
    log.debug(f"Paths to scan for shots: {paths_to_scan_for_shots}")

    for path_to_scan in paths_to_scan_for_shots:
        if not os.path.isdir(path_to_scan):
            continue
        try:
            # Shots are directories directly under the sequence (or episode if flat) path
            shots_in_path = [d for d in os.listdir(path_to_scan) if os.path.isdir(os.path.join(path_to_scan, d))]
            shots.update(shots_in_path)
        except OSError as e:
            log.error(f"Error listing shots in {path_to_scan}: {e}")
            
    return sorted(list(shots))


def get_nuke_scripts_for_preview(base_path, project_name, mode, names_to_process, max_versions):
    """
    Finds and filters Nuke scripts based on handler logic for preview.
    This function reuses parts of fixarc-handler's logic.
    'mode' can be 'project', 'episode', 'sequence', 'shot'.
    'names_to_process' are the specific episode/sequence/shot names if mode is not 'project'.
    """
    # This part directly reuses the logic from fixarc-handler's
    # build_search_paths and find_and_filter_nuke_scripts
    
    # Step 1: Build search paths (Simplified version from fixarc-handler)
    # We need to call the same build_search_paths as fixarc-handler would use
    # For simplicity, let's assume the UI selections (project, episode, sequence, shots selected)
    # translate into the `search_paths` that fixarc-handler's `find_and_filter_nuke_scripts` expects.
    # The UI would construct the `search_paths` for preview based on what it has determined the
    # handler would target.

    # The UI will determine the specific shot directories to look into.
    # If user selected specific shots, names_to_process = list of shot directory paths
    # If user selected sequences, names_to_process = list of sequence directory paths
    # etc.
    # For simplicity, let's assume `names_to_process` here contains the fully resolved
    # directories that need to be scanned for publish/nuke folders.
    
    actual_search_paths_for_scripts = []
    if mode == "project":
        project_shots_path = os.path.join(base_path, project_name, "shots")
        if os.path.isdir(project_shots_path):
            actual_search_paths_for_scripts.append(project_shots_path)
    elif mode == "episode":
        for episode_name in names_to_process:
            ep_path = os.path.join(base_path, project_name, "shots", episode_name)
            if os.path.isdir(ep_path):
                actual_search_paths_for_scripts.append(ep_path)
    elif mode == "sequence":
        for seq_name in names_to_process: # seq_name is like BOB_101_00X
            parts = seq_name.split('_')
            episode_dir_guess = f"{parts[0]}_{parts[1]}" if len(parts) >= 2 else parts[0]
            seq_path = os.path.join(base_path, project_name, "shots", episode_dir_guess, seq_name)
            if os.path.isdir(seq_path):
                actual_search_paths_for_scripts.append(seq_path)
    elif mode == "shot": # names_to_process contains selected shot *names*
        # Need to reconstruct the full path to each shot directory
        # This implies we need the episode and sequence context for each shot name.
        # This function might be better if it directly receives the shot directory paths.
        # Let's assume for now `names_to_process` are full paths to shot dirs for 'shot' mode preview.
        # This needs to align with how the UI calls it.
        # For now, if mode is "shot", names_to_process should be the selected shot *directory paths*.
        for shot_dir_path in names_to_process:
            if os.path.isdir(shot_dir_path):
                 actual_search_paths_for_scripts.append(shot_dir_path)

    if not actual_search_paths_for_scripts:
        log.warning("Preview: No valid search paths derived from selections.")
        return []

    # Step 2: Find and filter (Simplified from fixarc-handler's find_and_filter_nuke_scripts)
    # This re-implements the Nuke script finding logic for the preview
    
    preview_scripts = []
    log.debug(f"Preview: Searching for Nuke scripts in {actual_search_paths_for_scripts} with max_versions={max_versions}")

    for search_root in actual_search_paths_for_scripts:
        for dirpath, dirnames, filenames in os.walk(search_root):
            norm_dirpath = os.path.normpath(dirpath)
            if norm_dirpath.endswith(os.path.join("publish", "nuke")):
                nuke_publish_dir = dirpath
                
                try:
                    nk_files_in_dir = sorted(
                        [os.path.join(nuke_publish_dir, f) for f in os.listdir(nuke_publish_dir) if f.endswith(".nk") and os.path.isfile(os.path.join(nuke_publish_dir, f))]
                    )
                    # TODO: Implement robust version sorting (e.g., using natsort or regex-based version extraction)
                except OSError as e:
                    log.error(f"Error listing Nuke scripts in {nuke_publish_dir} for preview: {e}")
                    continue
                
                if not nk_files_in_dir:
                    continue

                log.debug(f"  Preview: Found {len(nk_files_in_dir)} .nk files in {nuke_publish_dir}: {[os.path.basename(f) for f in nk_files_in_dir]}")
                scripts_to_add_preview = []
                if max_versions <= 0:
                    scripts_to_add_preview.extend(nk_files_in_dir)
                elif max_versions == 1:
                    if nk_files_in_dir:
                        scripts_to_add_preview.append(nk_files_in_dir[-1])
                else:
                    count = len(nk_files_in_dir)
                    num_to_take = min(max_versions, count)
                    scripts_to_add_preview.extend(nk_files_in_dir[-num_to_take:])
                
                preview_scripts.extend(scripts_to_add_preview)
    
    log.info(f"Preview: Found {len(preview_scripts)} Nuke script(s) based on current selections and max versions.")
    for p_script in preview_scripts:
        log.debug(f"  Preview script: {p_script}")
    return preview_scripts

if __name__ == '__main__':
    # Example Usage (for testing data_utils directly)
    log.info("Testing data_utils.py...")
    
    # Configure for your test environment
    # test_base_path = get_default_base_path()
    test_base_path = "W:/proj" # Override for testing if FIXSTORE_DRIVE not set up like prod
    # test_base_path = "Z:/proj" 
    
    if not test_base_path or not os.path.isdir(test_base_path):
        log.error(f"Test base path '{test_base_path}' is not valid. Please configure for testing.")
        sys.exit(1)

    log.info(f"Using Test Base Path: {test_base_path}")

    projects = get_projects(test_base_path)
    log.info(f"Projects: {projects}")

    if projects:
        test_project = "sandbox" # projects[0]
        if test_project not in projects:
            log.warning(f"Test project '{test_project}' not found in {projects}. Using first available or skipping subsequent tests.")
            if projects: test_project = projects[0]
            else: test_project = None

        if test_project:
            log.info(f"--- Testing with Project: {test_project} ---")
            episodes = get_episodes(test_base_path, test_project)
            log.info(f"Episodes in {test_project}: {episodes}")

            if episodes:
                test_episodes = [episodes[0]] # Test with the first episode
                log.info(f"--- Testing with Episode(s): {test_episodes} ---")
                sequences = get_sequences(test_base_path, test_project, test_episodes)
                log.info(f"Sequences in {test_project}/{test_episodes}: {sequences}")

                if sequences:
                    test_sequences = [sequences[0]] # Test with the first sequence
                    log.info(f"--- Testing with Sequence(s): {test_sequences} ---")
                    shots = get_shots(test_base_path, test_project, test_episodes, test_sequences)
                    log.info(f"Shots in {test_project}/{test_episodes}/{test_sequences}: {shots}")

                    # Test preview function - requires constructing search paths as fixarc-handler would see them
                    # For shot mode preview, names_to_process would be specific shot paths
                    if shots:
                        # Construct full paths to selected shot directories for preview
                        shot_dir_paths_for_preview = [
                            os.path.join(test_base_path, test_project, "shots", test_episodes[0], test_sequences[0], shot_name)
                            for shot_name in shots[:1] # Preview for first shot found
                        ]
                        log.info(f"--- Previewing Nuke Scripts for first shot in {test_sequences[0]} (Max Versions: 1) ---")
                        preview_nk_scripts = get_nuke_scripts_for_preview(
                            base_path=test_base_path,
                            project_name=test_project,
                            mode="shot", # Assuming we're previewing at the shot level
                            names_to_process=shot_dir_paths_for_preview, # Full paths to shot dirs
                            max_versions=1
                        )
                        if preview_nk_scripts:
                            log.info(f"Preview scripts to be processed ({len(preview_nk_scripts)}):")
                            for s_path in preview_nk_scripts:
                                log.info(f"  - {s_path}")
                        else:
                            log.info("No scripts found for preview with current test settings.")
            
            # Test preview for an entire project
            log.info(f"--- Previewing Nuke Scripts for project '{test_project}' (Max Versions: 1) ---")
            project_preview_scripts = get_nuke_scripts_for_preview(
                base_path=test_base_path,
                project_name=test_project,
                mode="project",
                names_to_process=[], # Not used in project mode by this preview func
                max_versions=1
            )
            if project_preview_scripts:
                log.info(f"Project preview scripts ({len(project_preview_scripts)}):")
                # for s_path in project_preview_scripts: log.info(f"  - {s_path}")
            else:
                log.info(f"No scripts found for project '{test_project}' preview.")

    else:
        log.warning(f"No projects found in {test_base_path} to run detailed tests.") 