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
                             ["sg_status_list", "is_not", "omt"],
                             ["sg_episode.Episode.code", "is", episode]], 
                             ["code", "description"])
    
    shot_list = []
    for shot in shots:
        #print(f"Found shot: {shot['code']} - {shot.get('description', 'No description')}")
        description = shot.get('description', 'No description')

        if "wig" not in description.lower():
            shot_list.append((shot['code'], description))
            continue  # Skip further checks if "wig" is not in the description

        elif "wig" in description.lower():
            if "and" in description.lower():
                shot_list.append((shot['code'], description))
                print(f"Added shot {shot['code']} with description '{description}' because it contains 'wig' and 'and'.")
                continue
            elif "additional" in description.lower():
                shot_list.append((shot['code'], description))
                print(f"Added shot {shot['code']} with description '{description}' because it contains 'wig' and 'additional'.")
                continue
            elif "\n" in description:
                # If the description contains a newline
                shot_list.append((shot['code'], description))
                print(f"Added shot {shot['code']} with description '{description}' because it contains 'wig' and a newline.")
                continue
            else:
                print(f"Skipping shot {shot['code']} with description '{description}' due to 'wig' in description without 'and', 'additional', or newline.")
                continue  # Skip this shot

        
    

    return shot_list


if __name__ == "__main__":
    
    args = sys.argv[1:]
    project = args[0] 
    episode = args[1]
    

    data = get_shot_list(project, episode)

    print(f"Shot list for project '{project}' and episode '{episode}':")
    count = 0
    shot_str = ""
    for shot_code, description in data:
        print(f"Shot Code: {shot_code}, Description: {description}")
        shot_str += f"{shot_code} "
        count += 1
        #if count >= 5:
        #    break  # Limit to first 5 shots for testing purposes

    print(shot_str.strip())  # Print the shot codes as a single string
