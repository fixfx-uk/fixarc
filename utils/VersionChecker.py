import os
import sys

sg = None
def import_sg():
    global sg
    import shotgun_api3 # type: ignore
    sg = shotgun_api3.Shotgun("https://fixfx.shotgunstudio.com",
                        script_name="FixPTK",
                        api_key="mpzw(chuoyv5ysxvcuoVvewzc")
    
import_sg()

def get_shot_list(project, episode):
    """
    Retrieves a list of shots for the specified project and episode from Shotgun.
    Each shot is represented as a dictionary containing relevant metadata.

    Args:
        project: The name of the project to retrieve shots for.
        episode: The name of the episode to filter shots by.
    Returns:
        A list of shot codes for the specified project and episode.
    """

    shots = sg.find("Shot", [["project.Project.name", "is", project], 
                             ["sg_status_list", "is_not", "omt"]],
                             ["code", "sg_episode"])
    
    print(f" Example: {shots[0] if shots else 'No shots found'}")
    
    shot_version_list = []
    for shot in shots:
        episode_code = shot.get('sg_episode', {}).get('name') if shot.get('sg_episode') else None
        if episode_code != episode:
            continue  # Skip shots that do not belong to the specified episode
        latest = sg.find_one(
            "Version",
            [["entity", "is", shot]],
            ["code"],
            order=[{"field_name": "created_at", "direction": "desc"}],
        )
        #print(f"Found shot: {shot['code']} - {shot.get('description', 'No description')}")
        version = latest.get('code') if latest else None
        if version is None:
            print(f"No latest version found for shot {shot['code']}. Skipping.")
            continue  # Skip this shot if no latest version is found
        version_number = version.split('_')[-1].split('v')[-1]  

        shot_version_list.append((shot['code'], version_number))

    return shot_version_list

def check_shot_versions(shot_version_list, project, arc_path):
    """
    Checks the versions of shots against the files in the specified archive path.

    Args:
        shot_version_list: A list of tuples containing shot codes and their latest version numbers.
        project: The name of the project.
        arc_path: The path to the archive directory containing shot files.
    Returns:
        A tuple containing two lists:
            - matching_shots: A list of shot codes that have matching versions in the archive.
            - unmatched_shots: A list of shot codes that do not have matching versions in the archive.
    """

    matching_shots = []
    skipped_shots = []
    unmatched_shots = []

    for shot_code, version_number in shot_version_list:
        shot_ep = "_".join(shot_code.split('_')[:2])  # Extract episode from shot code
        path_to_nk_files = os.path.join(arc_path, project, shot_ep, shot_code, "project", "nuke")
        if not os.path.exists(path_to_nk_files):
            #print(f"Path does not exist for shot {shot_code}: {path_to_nk_files}")
            skipped_shots.append(shot_code)
            continue

        nk_files = [f for f in os.listdir(path_to_nk_files) if f.endswith('.nk')]
        if not nk_files:
            #print(f"No .nk files found for shot {shot_code} in path: {path_to_nk_files}")
            unmatched_shots.append(shot_code)
            continue   

        sorted_versions = []
        for nk_file in nk_files:
            nk_version_number = nk_file.split('_')[-1].split('v')[-1].split('.')[0]  # Extract version number from filename
            sorted_versions.append((nk_version_number, nk_file))

        sorted_versions.sort(key=lambda x: int(x[0]))  # Sort by version number
        if sorted_versions and sorted_versions[-1][0] == version_number:
            matching_shots.append(shot_code)
            #print(f"Matching version found for shot {shot_code}: {sorted_versions[-1][1]}")
        else:
            print(f"Highest version in archive for shot {shot_code} does not match latest version from Shotgun. Expected: {version_number}, Found: {sorted_versions[-1][0] if sorted_versions else 'None'}")
            unmatched_shots.append(shot_code)

    return matching_shots, unmatched_shots, skipped_shots


if __name__ == "__main__":
    
    args = sys.argv[1:]
    project = args[0] 
    episode = args[1]
    arc_path = args[2]
    

    shot_version_list = get_shot_list(project, episode)

    matching_shots, unmatched_shots, skipped_shots = check_shot_versions(shot_version_list, project, arc_path)

    print(f"Matching shots length: {len(matching_shots)}")
    print(f"Unmatched shots length: {len(unmatched_shots)}")
    
    print(f"Skipped shots length: {len(skipped_shots)}")

    print(f"\n\n Unmatched shots: {unmatched_shots}")
