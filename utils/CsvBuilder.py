import os
import sys
import csv

sg = None
def import_sg():
    global sg
    import shotgun_api3 # type: ignore
    sg = shotgun_api3.Shotgun("https://fixfx.shotgunstudio.com",
                        script_name="FixPTK",
                        api_key="mpzw(chuoyv5ysxvcuoVvewzc")
    
import_sg()

def get_csv_data(project):
    """
    Retrieves data for the specified project from Shotgun and returns it as a list of dictionaries.
    Each dictionary contains the shot code and the corresponding .mov file paths.

    Args:
        project: The name of the project to retrieve data for.
    Returns:
        A list of dictionaries, each containing:
            - 'shot_code': The code of the shot.
            - 'scope_of_work': The scope of work for the shot. - description of the shot.
            - 'final_cost': The final cost associated with the shot.
            - 'status': The status of the shot.
            - 'sequence': The sequence the shot belongs to.
            - 'episode': The episode the shot belongs to.
            - 'vendor': The vendor associated with the shot - 'FixFx'
            - 'shot_type': The type of the shot (e.g., 'VFX', 'Animation').
            - 'final_version': The final version number of the shot.
            - 'scene': The scene associated with the shot.
            - 'key_shot': A boolean indicating if the shot is a key shot.
    """

    shots = sg.find("Shot", [["project.Project.name", "is", project], 
                             ["sg_status_list", "is_not", "omt"]], 
                             ["code", "description", "sg_latest_cost", "sg_status_list", "sg_sequence", "sg_episode", "sg_scene"])
                             
    
    data = []
    counter = 0
    for shot in shots:
        shot_code = shot.get('code')
        scope_of_work = shot.get('description', '')
        final_cost = shot.get('sg_latest_cost', 0)
        status = shot.get('sg_status_list', '')
        sequence = shot.get('sg_sequence', {}).get('name', '')
        episode = shot.get('sg_episode', {}).get('name', '')
        vendor = 'FixFx'  
        shot_type = 'VFX'  

        final_version_data = sg.find_one("Version", [["code", "is", shot_code]], order=[{"field_name": "created_at", "direction": "desc"}])
        if final_version_data:
            version_number = final_version_data['code'].split('v')[-1]  # Extract version number from string like 'v001'
            final_version = version_number
        else:
            final_version = 'N/A'
        scene = shot.get('sg_scene', '')
        key_shot = True if status == 'key' else False

        data.append({
            'shot_code': shot_code,
            'scope_of_work': scope_of_work,
            'final_cost': final_cost,
            'status': status,
            'sequence': sequence,
            'episode': episode,
            'vendor': vendor,
            'shot_type': shot_type,
            'final_version': final_version,
            'scene': scene,
            'key_shot': key_shot
        })
        counter += 1
        if counter == 5:
            break  # Limit to first 5 shots for testing purposes
    return data


def write_csv(data, destination, filename):
    """
    Writes the provided data to a CSV file at the specified destination.

    Args:
        data: A list of dictionaries containing shot data.
        destination: The directory where the CSV file will be saved.
        filename: The name of the CSV file to create.
    """

    if not os.path.exists(destination):
        os.makedirs(destination)

    csv_path = os.path.join(destination, filename)
    
    with open(csv_path, mode='w', newline='', encoding='utf-8') as csv_file:
        fieldnames = ['shot_code', 'scope_of_work', 'final_cost', 'status', 'sequence', 'episode', 'vendor', 'shot_type', 'final_version', 'scene', 'key_shot']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

        writer.writeheader()
        for row in data:
            writer.writerow(row)

if __name__ == "__main__":
    
    args = sys.argv[1:]
    project = args[0] 
    csv_destination = args[1]
    csv_filename = args[2]

    data = get_csv_data(project)
    write_csv(data, csv_destination, csv_filename)