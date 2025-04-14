# deadline\PostJobScript.py

```py
import subprocess
import sys
import json
from Deadline.Scripting import *
from concurrent.futures import ThreadPoolExecutor, as_completed

def run_command(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)

    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip())

    stderr = process.communicate()[1]
    if stderr:
        print(stderr.strip(), file=sys.stderr)

def threaded_run_command(commands, WORK_NUM=3):
    def run_command_wrapper(cmd):
        try:
            run_command(cmd)
        except Exception as e:
            print(f"Command {cmd} generated an exception: {e}")

    with ThreadPoolExecutor(max_workers=WORK_NUM) as executor:
        futures = {executor.submit(run_command_wrapper, cmd): cmd for cmd in commands}
        for future in as_completed(futures):
            pass

def __main__(*args):
    deadlinePlugin = args[0]

    json_path = deadlinePlugin.GetJobInfoEntry("ExtraInfo1")
    with open(json_path, 'r') as f:
        data = json.load(f)

    commands = data['commands']
    print(commands)
    threaded_run_command(commands, WORK_NUM=6)
```

# deadline\PreJobScript.py

```py
import subprocess
import sys
import json
import os

from Deadline.Scripting import RepositoryUtils

def run_command(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)

    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip())

    stderr = process.communicate()[1]
    if stderr:
        print(stderr.strip(), file=sys.stderr)

def __main__(*args):
    deadlinePlugin = args[0]
    worker  = deadlinePlugin.GetSlaveName()
    
    json_path = deadlinePlugin.GetJobInfoEntry("ExtraInfo0")
    with open(json_path, 'r') as f:
        data = json.load(f)    

    command = data['PreScriptJobCommand']
    print(f"Updating delivery_template with: {command}")
    run_command(command)

    with open(json_path, 'r') as f:
        data = json.load(f)

    job = deadlinePlugin.GetJobInfoEntry("JobId")
    RepositoryUtils.AddSlavesToMachineLimitList(job, [worker])
    RepositoryUtils.SetMachineLimitWhiteListFlag(job, True)
    deadline_job = RepositoryUtils.GetJob(job, True)
    for i,mode in enumerate(data['modes']):
        key = f'WriteNode{i}EndFrame'
        current = deadline_job.GetJobPluginInfoKeyValue(key)
        updated = str(int(data[key]))
        print(f"Changing end for {mode} from {current} to {updated}")
        deadline_job.SetJobPluginInfoKeyValue(key, updated)
    RepositoryUtils.SaveJob(deadline_job)

    nuke_script_path = data['nuke_script_path']
    print(f"Adding aux files.")
    RepositoryUtils.AddAuxiliaryFile(deadlinePlugin.GetJob(),[nuke_script_path])
    print(f"Succesfully added {nuke_script_path}")

```

# FIXPTK.exe.lnk

This is a binary file of the type: Binary

# FIXPTK.ps1

```ps1
Set-ExecutionPolicy Bypass -Scope Process

# Set the current working directory
Set-Location -Path 'Z:\pipe\FIXPS\'

# Define the path to the Python executable
$pythonExe = 'Z:\pipe\.pyenv\pyenv-win\versions\3.7.9\python.exe'

# Define the path to the Python script
$pythonScript = 'python\FIXPTK.py'

# Run the Python script
& $pythonExe $pythonScript

# Optional: Pause to keep the window open if run interactively
#Read-Host -Prompt "Press Enter to exit"

```

# python\__init__.py

```py

```

# python\FIXPTK.py

```py
import time
import threading

sg = None
def import_shotgrid():
    global sg
    import shotgun_api3
    sg = shotgun_api3.Shotgun("https://fixfx.shotgunstudio.com",
                        script_name="StarterFIX",
                        api_key="mpzw(chuoyv5ysxvcuoVvewzc")

THREAD = threading.Thread(target=import_shotgrid)
THREAD.start()

from PyQt5.QtWidgets import *
from PyQt5.QtGui import QIcon, QColor,QBrush
from PyQt5.QtCore import QFile,QTextStream, Qt, pyqtSignal, QThread
import os
import sys
import json
import yaml
import shutil
import colorsys
import random
import platform
import glob
import subprocess

from concurrent.futures import ThreadPoolExecutor, as_completed
from custom_widgets.CustomWidgets import UserInputDialog, SplashScreen, ShotInputDialog, OptionsDialog, WarningDialog

THIS_FILE = os.path.abspath(__file__)
ROOT = os.path.abspath(os.curdir)

def run_command(command, splash=None, window=None):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)

    while True:
        output = process.stdout.readline()
        if output == '' and process.poll() is not None:
            break
        if output:
            print(output.strip())

    stderr = process.communicate()[1]
    if stderr:
        print(stderr.strip(), file=sys.stderr)

    if splash is not None and window:
        splash.finish(window) 

def threaded_run_command(commands, WORK_NUM=3):
    def run_command_wrapper(cmd):
        try:
            run_command(cmd)
        except Exception as e:
            print(f"Command {cmd} generated an exception: {e}")

    with ThreadPoolExecutor(max_workers=WORK_NUM) as executor:
        futures = {executor.submit(run_command_wrapper, cmd): cmd for cmd in commands}
        for future in as_completed(futures):
            pass

class CommandWorker(QThread):
    finished = pyqtSignal()  # Signal to indicate completion

    def __init__(self, commands, work_num):
        super().__init__()
        self.commands = commands
        self.work_num = work_num

    def run(self):
        threaded_run_command(self.commands, self.work_num)
        self.finished.emit()
    

class LazyLoader:
    def __init__(self):
        self.ui = None

    def load_ui(self):
        if self.ui is None:
            from designer.ui_FIXPTK import Ui_MainWindow
            self.ui = Ui_MainWindow()
        return self.ui
    
class MainWindow(QMainWindow):
    def __init__(self, app):
        super(MainWindow, self).__init__()

        self.worker = None
        self.ui = LazyLoader().load_ui()
        self.ui.setupUi(self)

        self.initialized = False
        self.app = app

        self.ui.stackedWidget.setCurrentIndex(3)
        self.ui.nuke_btn.setChecked(True)

        self.current_project = None
        
        self.connect_signals()        
        THREAD.join()
        self.load()        
        self.ui.project_combobox.currentIndexChanged.connect(self.on_project_change)
        #self.setWindowFlag(Qt.WindowStaysOnTopHint)

    def setup_available_roots(self):
        roots = sg.find("LocalStorage", [], ["code", 'windows_path', 'linux_path'])
        root_combobox = self.ui.home_project_root
        for root in roots:
            root_combobox.addItem(root['code'])
        self.update_current_root()

    def update_current_root(self):
        root = sg.find_one("Project",[["name", "is", self.current_project]], ['sg_project_root'])['sg_project_root']
        if root:
            self.ui.home_project_root.setCurrentText(root)
        else:
            self.ui.home_project_root.setCurrentIndex(-1)
    
    def load_published_shots(self):
        published_shots_gen = self.get_published_shots()
        table = self.ui.render_queu
        
        for row_index, shot_info in enumerate(published_shots_gen):
            table.insertRow(row_index)
            table.setItem(row_index, 0, QTableWidgetItem(shot_info['shot_code']))
            windows_path = shot_info['windows_path']
            item =  QTableWidgetItem(windows_path)
            if not os.path.exists(windows_path.replace("%04d", "1001")):
                path = self.find_file(os.path.basename(windows_path.replace("%04d", "1001")), os.path.dirname(windows_path.replace("%04d", "1001")))
                print(path)
                if not path:
                    path = windows_path
                item = QTableWidgetItem(path.replace("1001", "%04d"))
                if not os.path.exists(path) or not shot_info['last_frame']:
                    item.setForeground(QBrush(QColor(255, 0, 0)))
                

            table.setItem(row_index, 1, item)
            table.setItem(row_index, 2, QTableWidgetItem(shot_info['description']))
            table.setItem(row_index, 3, QTableWidgetItem(str(shot_info['version_number'])))   
            table.setItem(row_index, 4, QTableWidgetItem(str(shot_info['last_frame'])))   
        
        if table.rowCount() == 0:
            print("Could not find any published shots that have been QCed.")


    def get_published_shots(self):
        pub_shots = sg.find("Shot",
                            [["project.Project.name", 'is', self.current_project],
                            ['sg_status_list', "is", "pub"]],
                            ['code', 'sg_cut_out'])
        
        for shot in pub_shots:
            latest_published_exr = sg.find_one("PublishedFile",
                                            [["entity", 'is', shot],
                                                ['published_file_type.PublishedFileType.code', 'is', 'Rendered Image']],
                                            ['path', 'version_number', 'description'],
                                            [{'field_name': 'created_at', 'direction': 'desc'}])
            if latest_published_exr:
                QC = sg.find_one("Task",
                                [["entity", 'is', shot],
                                ['content', 'is', 'QC'],
                                ['sg_status_list', 'is', 'cmpt']])

                if QC:
                    windows_path = latest_published_exr['path']['local_path_windows']
                    folder_path = os.path.dirname(windows_path)
                    files = [f for f in os.listdir(folder_path) if f.endswith('.exr')]

                    # Get all frame numbers from filenames
                    frame_numbers = [int(f.split(".")[-2]) for f in files if f.split(".")[-2].isdigit()]
                    highest_frame = max(frame_numbers, default= shot['sg_cut_out'])

                    # Log warning if frames don't match
                    last_frame =  shot['sg_cut_out'] or 0
                    if last_frame != highest_frame:
                        print(
                            f"Frame discrepancy for shot {shot['code']}: sg_cut_out is {last_frame}, highest frame is {highest_frame}.")

                    yield {
                        'shot_code': shot['code'],
                        'windows_path': latest_published_exr['path']['local_path_windows'],
                        'description': latest_published_exr['description'],
                        'version_number': str(latest_published_exr['version_number']).zfill(3),
                        'last_frame': max(last_frame, highest_frame)
                    }

    def browse_folder_path(self, line_edit):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        starting_path = os.path.join(self.get_json_data(self.project_settings_path())['shotgrid_project_location'], self.current_project, 'delivery')  # Specify your starting path here
        folder_path = QFileDialog.getExistingDirectory(self, "Select Directory", starting_path, options=options)
        
        line_edit.setText(folder_path)

    def update_selected_description(self):
        selected_rows = set(index.row() for index in self.ui.render_queu.selectedIndexes())
        description = self.get_user_input("Enter description for selected shots:")
        for row in selected_rows:
            self.ui.render_queu.item(row, 2).setText(description)
    
    def copy_luts(self):
        if self.current_project == 'bos':
            ingest_folders = [os.path.abspath(self.ui.ingestion_folder_lut_linedit.text())]
            project_folder = r'X:\proj\bos\shots'

            for ingest_folder in ingest_folders:
                shots = [f for f in os.listdir(ingest_folder) if os.path.isdir(os.path.join(ingest_folder, f))]
                for shot in shots:
                    ingest_support_files_folder = os.path.join(ingest_folder, shot, 'support_files')
                    split = shot.split("_")
                    shot_name = ("_").join(split[:-2])
                    seq = ("_").join(split[:2])
                    episode = split[0]
                    destination_folder = os.path.join(project_folder, f"BOS_{episode}", f"BOS_{seq}", shot_name, "editorial", "support_files")
                    print('Copied LUT from --> to')
                    print(ingest_support_files_folder, destination_folder)
                    try:
                        shutil.copytree(ingest_support_files_folder, destination_folder)
                    except:
                        continue
        
        elif self.current_project == 'gol03':
            ingest_folders = [os.path.abspath(self.ui.ingestion_folder_lut_linedit.text())]
            print(ingest_folders)
            project_folder = r'Z:\proj\gol03\shots'

            for ingest_folder in ingest_folders:
                shots = [f for f in os.listdir(ingest_folder) if os.path.isdir(os.path.join(ingest_folder, f))]
                print(shots)
                for shot in shots:
                    pattern = os.path.join(ingest_folder, shot,'4608x3164', "*.cc")
                    print(pattern)

                    try:
                        ingest_support_file = glob.glob(pattern)[0]
                    
                        split = shot.split("_")
                        shot_name = ("_").join(split[:-1])
                        seq = ("_").join(split[:3])
                        episode = ("_").join(split[:2])

                        destination_folder = os.path.join(project_folder, episode, seq, shot_name, "editorial", "support_files")
                        print('Copied LUT from --> to')
                        print(ingest_support_file, destination_folder)
                        try:
                            shutil.copytree(ingest_support_files_folder, destination_folder)
                        except:
                            continue
                    except:
                        print(f"Could not find any for this shot {shot}")
        
        elif self.current_project == 'rod01':
            ingest_folders = [os.path.abspath(self.ui.ingestion_folder_lut_linedit.text())]
            project_folder = r'Z:\proj\rod01\shots'

            for ingest_folder in ingest_folders:
                shots = [f for f in os.listdir(ingest_folder) if os.path.isdir(os.path.join(ingest_folder, f)) and 'fg' in f]
                for shot in shots:
                    ingest_support_files_folder = os.path.join(ingest_folder, shot, 'support_files')
                    split = shot.split("_")
                    shot_name = ("_").join(split[:-2])
                    seq = ("_").join(split[:-3])
                    episode = ("_").join(split[:-4])
                    destination_folder = os.path.join(project_folder, episode, seq, shot_name, "editorial", "support_files")
                    # if not os.path.exists(destination_folder):
                    #     os.mkdir(destination_folder)
                    print('Copied LUT from --> to')
                    print(ingest_support_files_folder, destination_folder)
                    try:
                        shutil.copytree(ingest_support_files_folder, destination_folder)
                    except:
                        continue

        elif self.current_project == 'deb02':
            ingest_folders = [os.path.abspath(self.ui.ingestion_folder_lut_linedit.text())]
            project_folder = r'Z:\proj\deb02\shots'

            for ingest_folder in ingest_folders:
                shots = [f for f in os.listdir(ingest_folder) if os.path.isdir(os.path.join(ingest_folder, f)) and 'BG' in f.upper()]

                for shot in shots:
                    ingest_support_files_folder = os.path.join(ingest_folder, shot, 'support_files')
                    split = shot.split("_")

                    shot_name = ("_").join(split[:-2])
                    seq = ("_").join(split[:-3])
                    episode = ("_").join(split[:-4])

                    destination_folder = os.path.join(project_folder, episode, seq, shot_name, "editorial", "support_files")
                    print('Copied LUT from --> to')
                    print(ingest_support_files_folder, destination_folder)
                    try:
                        shutil.copytree(ingest_support_files_folder, destination_folder)
                    except:
                        continue
        else:
            print("Copying LUTS is only available for bos project.")

    def apply_template(self, mode, data, windows_path=None):
        table = self.ui.delivery_package_table
        index = next((row for row in range(table.rowCount()) if table.verticalHeaderItem(row).text() == mode), -1)
        template = table.cellWidget(index, 0).text()
        shot = data['shot']
        version =  data['version']
        width = ""
        height = ""

        if windows_path:
            width,height = get_exr_dimensions(windows_path)

        path = template.replace("{Shot}", shot).replace("{version}", version).replace("{SEQ}", "%04d").replace("{width}", width).replace("{height}", height)

        return path
    
    def export_selected_shots_for_delivery(self):
        dialog = WarningDialog(self)
        _,_, free = shutil.disk_usage("C:/")
        total_gb = int(free/(1024 ** 3))
        if total_gb<200:
            message = f"You have {total_gb}Gb left on your disk. In order to localize files you need at least 200Gb left. Would you like to proceed?"
            result = dialog.show(message)
            if result == QMessageBox.No:
                return
        
        selected_indexes = set(index.row() for index in self.ui.render_queu.selectedIndexes())
        if len(selected_indexes) == 0:
            print("No Shots selected. Please select at least one shot and try again.")
            return

        modes = [self.ui.delivery_package_table.verticalHeaderItem(i).text() for i in range(self.ui.delivery_package_table.rowCount())]
        dialog = OptionsDialog(modes, self)
        if dialog.exec_() == QDialog.Accepted:
            selected_options = dialog.get_selected_options()
            valid_modes = [m for m in modes if selected_options[m]]
        else:
            return

        
        template_nuke_script = self.ui.delivery_template.currentText() + ".nk"
        template_python_script = self.ui.delivery_template.currentText() + ".py"
        nuke_path = self.get_nuke_path()

        render_commands = []
        script_update_commands = []
        copy_commands = []
        deadline_jobs = []

        date = time.time()
        job_folder = os.path.abspath(f"./jobs/{date}")
        if not os.path.exists(job_folder):
            os.mkdir(job_folder)

        for index in selected_indexes:
            copy_commands_shot = []
            config = {
                    "BatchMode": False,
                    "BatchModeIsMovie": False,
                    "ContinueOnError": True if self.current_project == "gol03" else False,
                    "EnforceRenderOrder": False,
                    "GpuOverride": 0,
                    "NukeX": False,
                    "PerformanceProfiler": False,
                    "PerformanceProfilerDir": "",
                    "RamUse": 0,
                    "RenderMode": "Use Scene Settings",
                    "StackSize": 0,
                    "Threads": 0,
                    "UseGpu": True,
                    "UseSpecificGpu": False,
                    "Version": "15.0",
                    "Views": "",
                    "WriteNodesAsSeparateJobs": True
                }
            data = {}
            data['settings_path'] = os.path.abspath(self.project_settings_path())
            data['modes'] = valid_modes 
            shot = self.ui.render_queu.item(index, 0).text()
            windows_path = self.ui.render_queu.item(index, 1).text()

            delivery_folder = self.ui.delivery_folder_lineedit_3.text()
            job_shot_folder = os.path.abspath(f"./jobs/{date}/{shot}")

            job_info = {
            'Frames': f'0-{len(valid_modes)-1}',
            'Name': shot,
            'OverrideJobFailureDetection': True,
            'Plugin': 'Nuke',
            'Priority': 50,
            'ConcurrentTasks': 5,
            'BatchName': delivery_folder,
            'MachineLimit': 1,
            'EventOptIns':'ShotgirdVersionUpload',
            'OutputDirectory0': job_shot_folder,
            'OutputDirectory1': delivery_folder
            }

            
            if not os.path.exists(job_shot_folder):
                os.mkdir(job_shot_folder)


            publish_folder = self.find_publish_dir(windows_path)

            data['shot'] = shot        
            data['read_path'] = windows_path
            version = self.ui.render_queu.item(index, 3).text()
            data['notes'] = self.ui.render_queu.item(index, 2).text()
            data['version'] = version
            data['last_frame'] = int(self.ui.render_queu.item(index, 4).text())
            data['ShotgridSubmission'] = None
            nuke_script_path = os.path.join(job_shot_folder, f"{shot}.nk")
            shutil.copy2(template_nuke_script, nuke_script_path)
            data['nuke_script_path'] = nuke_script_path

            job_info_file_path = os.path.join(job_shot_folder, f"{shot}.json")
            data['job_directory'] = os.path.dirname(job_info_file_path)
            data['conform_script'] = os.path.join(publish_folder, f"{shot}_conform.nk")
            script_update_command = f'''"{nuke_path}" -t {template_python_script} {job_info_file_path}'''
            script_update_commands.append(script_update_command)
            data['PreScriptJobCommand'] = str(script_update_command)
            job_info['ExtraInfo0'] = job_info_file_path
            job_info['PreJobScript'] = os.path.abspath("../Deadline/PreJobScript.py")
            job_info['PostJobScript'] = os.path.abspath("../Deadline/PostJobScript.py")

            for i,mode in enumerate(valid_modes):
                # if exr seq render only a slate on 1000 into the publish folder and copy the whole seq to delivery folder afterwards
                if mode =="Comp":
                    data[f'WriteNode{i}'] = f"Write_{mode}"
                    data[f'WriteNode{i}StartFrame'] = 1000
                    data[f'WriteNode{i}EndFrame'] = 1000
                    
                    config[f'WriteNode{i}'] = f"Write_{mode}"
                    config[f'WriteNode{i}StartFrame'] = 1000
                    config[f'WriteNode{i}EndFrame'] = 1000
                    
                    write_path = windows_path.replace("%04d", "1000")
                    data[f'WriteNode{i}Path'] = write_path  

                    render_command = f'''"{nuke_path}" -i -X {data[f'WriteNode{i}']} --cont "{nuke_script_path}" 1000'''
                    render_commands.append(render_command)
                    data[f'{mode}_render_command'] = render_command

                    file_name_path = self.apply_template(mode, data, windows_path)
                    destination_path = os.path.dirname(os.path.join(delivery_folder, file_name_path))
                    copy_command = (
                                    f'powershell.exe -NoProfile -ExecutionPolicy Bypass '
                                    f'-File Z:/pipe/FIXPS/run_robocopy.ps1 '
                                    f'-SourcePath "{os.path.dirname(windows_path)}/" '
                                    f'-DestinationPath "{destination_path}" '
                                )

                # if movie render the file to delivery folder and copy to publish folder afterwards
                else:
                    file_name_path = self.apply_template(mode, data)
                    data[f'WriteNode{i}'] = f"Write_{mode}"
                    data[f'WriteNode{i}StartFrame'] = 1000
                    data[f'WriteNode{i}EndFrame'] = int(self.ui.render_queu.item(index, 4).text())

                    config[f'WriteNode{i}'] = f"Write_{mode}"
                    config[f'WriteNode{i}StartFrame'] = 1000
                    config[f'WriteNode{i}EndFrame'] = int(self.ui.render_queu.item(index, 4).text())

                    write_path = os.path.join(delivery_folder, file_name_path)
                    data[f'WriteNode{i}Path'] = write_path 

                    render_command = f'''"{nuke_path}" -i -X {data[f'WriteNode{i}']} --cont --gpu "{nuke_script_path}" 1000-{data[f'WriteNode{i}EndFrame']}'''
                    render_commands.append(render_command)
                    data['render_command'] = render_command
                    
                    publish_path = os.path.join(publish_folder, file_name_path)
                    copy_command = (
                                    f'powershell.exe -NoProfile -ExecutionPolicy Bypass '
                                    f'-File Z:/pipe/FIXPS/run_robocopy.ps1 '
                                    f'-SourcePath "{os.path.dirname(os.path.abspath(write_path))}" '
                                    f'-DestinationPath "{os.path.abspath(os.path.dirname(publish_path))}" '
                                    f'-FileName "{os.path.basename(write_path)}"'
                                )
                
                
                
                checkbox = self.findChild(QWidget, f"delivery_package_table_{mode}_shotgrid")
                if checkbox.isChecked():
                    data['ShotgridSubmission'] = write_path

                self.dumb_json_data(job_info_file_path, data)
                copy_commands.append(copy_command)
                copy_commands_shot.append(copy_command)
                shot_path = os.path.join(job_shot_folder, 'copy_commands.json')
                job_info['ExtraInfo1'] = shot_path
                self.dumb_json_data(shot_path, {'commands':copy_commands_shot})
         
            #config['SceneFile'] = nuke_script_path
            deadline_job = {"JobInfo": job_info, "PluginInfo":config}
            deadline_jobs.append(deadline_job)

        copy_commands_json_path = os.path.join(f"./jobs/{date}", "copy_commands.json")
        self.dumb_json_data(copy_commands_json_path ,{'commands': copy_commands})

        
        submit_to_deadline = selected_options['submit to Deadline']
        if submit_to_deadline:
            thread = threading.Thread(target=self.run_deadline, args=(deadline_jobs,))
            thread.start()

        else:
            print("Updating render scripts")
            self.worker = CommandWorker(script_update_commands, work_num=10)
            copy_upon_render = selected_options['copy to publish folder']
            
            self.worker.finished.connect(lambda: self.on_script_update_done(render_commands,copy_commands,copy_upon_render,submit_to_deadline, deadline_jobs))
            self.worker.start()

    def find_publish_dir(self, start_path):
        current_path = start_path
        while current_path != os.path.dirname(current_path):  # Check if we've reached the root
            if os.path.basename(current_path) == 'publish':
                return current_path
            current_path = os.path.dirname(current_path)  # Move to the parent directory
        return None  # If no "publish" directory is found

    def run_deadline(self,deadline_jobs):
        print("Submitting to deadline")
        sys.path.append("..")
        from Deadline.api.Deadline import DeadlineConnect as Connect
        Deadline = Connect.DeadlineCon("192.168.14.230", 8081)

        Deadline.EnableAuthentication(True)
        Deadline.SetAuthenticationCredentials("fixrs-001", "")
        
        jobid = Deadline.Jobs.SubmitJobs(deadline_jobs)
        print(jobid)

    def on_script_update_done(self, render_commands, copy_commands,copy_upon_render):
        print("Script update done. Sending to render ****************************")
        self.worker = CommandWorker(render_commands, work_num=6)
        if copy_upon_render:
            self.worker.finished.connect(lambda:self.on_render_done(copy_commands))
        else:
            self.worker.finished.connect(lambda:print("finished ==================="))
        self.worker.start()

    def copy_after_render(self):
        file_path, _ = QFileDialog.getOpenFileName(caption="Select a file containging copy_commands")
        copy_commands = self.get_json_data(file_path)['commands']
        self.on_render_done(copy_commands)

    def on_render_done(self, copy_commands):
        print("Render commands execution complete! Copying to publish folder")
        self.worker = CommandWorker(copy_commands, work_num=6)
        self.worker.finished.connect(lambda:print("===finished==="))
        self.worker.start()

    def get_nuke_path(self):
        system_platform = platform.system()

        if system_platform == 'Windows':
            OS = 'windows'
        elif system_platform == 'Darwin':
            OS = 'mac'
        elif system_platform == 'Linux':
            OS = 'linux'

        nuke_path = sg.find_one("Software", [["code", "is", "Nuke"]], [f'{OS}_path'])[f'{OS}_path']
        return nuke_path
    
    def deleteSelectedRows(self):
        table = self.ui.render_queu
        selected_rows = set()

        # Get all selected items
        for item in table.selectedItems():
            selected_rows.add(item.row())

        # Sort rows in reverse order and delete them
        for row in sorted(selected_rows, reverse=True):
            table.removeRow(row)
    
    def version_up(self, plus=True):
        table = self.ui.render_queu
        selected_rows = set()

        # Get all selected items
        for item in table.selectedItems():
            selected_rows.add(item.row())

        # Iterate over each selected row
        for row in selected_rows:
            # Get the current version from column 3
            current_version_item =table.item(row, 3)
            if current_version_item is not None:
                current_version_str = current_version_item.text()
                
                # Ensure the version is numeric and padded correctly
                if current_version_str.isdigit() and len(current_version_str) == 3:
                    current_version = int(current_version_str)
                    if plus == True:
                        new_version = current_version + 1
                    else:
                        new_version = current_version - 1
                    new_version_str = str(new_version).zfill(3)  # Format as 3-digit string
                    
                    # Update the cell with the new version
                    table.setItem(row, 3, QTableWidgetItem(new_version_str))

    def find_file(self, file_name, current_dir):
        # Check one directory down (first level subdirectories)

        if not os.path.exists(current_dir):
            current_dir = os.path.dirname(current_dir)
        for subdir in os.listdir(current_dir):
            subdir_path = os.path.join(current_dir, subdir)
            if os.path.isdir(subdir_path):
                file_in_subdir = os.path.join(subdir_path, file_name)
                if os.path.exists(file_in_subdir):
                    return file_in_subdir

        
        # Check if the file exists in the current directory
        current_path = os.path.join(current_dir, file_name)
        if os.path.exists(current_path):
            return current_path

        # Check one directory up (parent directory)
        parent_dir = os.path.dirname(current_dir)
        parent_path = os.path.join(parent_dir, file_name)
        if os.path.exists(parent_path):
            return parent_path

        # File not found in any of the checked locations
        return None

    def load_shots(self):
        published_shots_gen = self.get_shots()
        table = self.ui.render_queu
        
        for row_index, shot_info in enumerate(published_shots_gen):
            table.insertRow(row_index)
            table.setItem(row_index, 0, QTableWidgetItem(shot_info['shot_code']))
            
            windows_path = shot_info['windows_path']
            item =  QTableWidgetItem(windows_path)
            
            width, height = get_exr_dimensions(windows_path)
            resolution = f"{width}x{height}"

            if not os.path.exists(windows_path.replace("%04d", "1001")) or resolution in os.listdir(os.path.dirname(windows_path)):
                path = self.find_file(os.path.basename(windows_path.replace("%04d", "1001")), os.path.dirname(windows_path.replace("%04d", "1001")))
                print(path)
                if not path:
                    path = windows_path
                item = QTableWidgetItem(path.replace("1001", "%04d"))
                if not os.path.exists(path):
                    item.setForeground(QBrush(QColor(255, 0, 0)))
            table.setItem(row_index, 1, item)

            table.setItem(row_index, 2, QTableWidgetItem(shot_info['description']))
            table.setItem(row_index, 3, QTableWidgetItem(str(shot_info['version_number'])))   
            table.setItem(row_index, 4, QTableWidgetItem(str(shot_info['last_frame'])))   
        
        if table.rowCount() == 0:
            print("Could not find any published shots that have been QCed.")

    def get_shots(self):
        shots = ShotInputDialog.get_shots_from_user()
        
        for shot in shots:
            latest_published_exr = sg.find_one("PublishedFile",
                                            [["entity.Shot.code", 'is', shot],
                                            ['published_file_type.PublishedFileType.code', 'is', 'Rendered Image']],
                                            ['path', 'version_number', 'description', 'entity.Shot.sg_cut_out'],
                                            [{'field_name': 'created_at', 'direction': 'desc'}])
            if latest_published_exr:
                yield {
                    'shot_code': shot,
                    'windows_path': latest_published_exr['path']['local_path_windows'],
                    'description': latest_published_exr['description'],
                    'version_number': str(latest_published_exr['version_number']).zfill(3),
                    'last_frame': latest_published_exr['entity.Shot.sg_cut_out']
                }
    
    def toggle_delivery_checkbox(self, checked):
        if checked:
            self.add_row("Comp")
        else:
            table = self.ui.delivery_package_table
            for row in range(table.rowCount()):
                header = table.verticalHeaderItem(row)
                if header and header.text() == "Comp":
                    table.removeRow(row)
                    break

    def connect_signals(self):
        self.ui.nuke_delivery_checkbox.toggled.connect(self.toggle_delivery_checkbox)
        self.ui.delivery_table_add_btn.clicked.connect(self.load_shots)
        self.ui.delivery_template_open_btn.clicked.connect(self.open_nuke_script)
        self.ui.nuke_template_open_btn.clicked.connect(self.open_nuke_script)
        self.ui.delivery_copy_btn.clicked.connect(self.copy_after_render)

        self.ui.delivery_table_version_up_btn.clicked.connect(lambda: self.version_up(True))
        self.ui.delivery_table_version_down_btn.clicked.connect(lambda: self.version_up(False))
        self.ui.delivery_description_btn_3.clicked.connect(self.update_selected_description)
        self.ui.delivery_folder_btn_3.clicked.connect(lambda: self.browse_folder_path(self.ui.delivery_folder_lineedit_3))
        self.ui.ingestion_folder_lut_btn.clicked.connect(lambda: self.browse_folder_path(self.ui.ingestion_folder_lut_linedit))
        self.ui.ingestion_copy_luts_btn.clicked.connect(self.copy_luts)
        self.ui.delivery_load_shots_btn_2.clicked.connect(self.load_published_shots)
        self.ui.ingestion_btn.toggled.connect(self.on_ingestion_btn_1_toggled)
        self.ui.delivery_btn.toggled.connect(self.on_delivery_btn_1_toggled)
        self.ui.google_btn.toggled.connect(self.on_google_btn_1_toggled)
        self.ui.nuke_btn.toggled.connect(self.on_nuke_btn_1_toggled)
        self.ui.shotgrid_btn.toggled.connect(self.on_shotgrid_btn_1_toggled)
        self.ui.discord_btn.toggled.connect(self.on_discord_btn_1_toggled)
        self.ui.exit_btn.clicked.connect(self.exit)
        self.ui.save_btn.clicked.connect(self.save)
        self.ui.google_sync_btn.clicked.connect(self.run_google_sync)
        # Connect signals
        self.ui.delivery_add_file_btn.clicked.connect(self.add_row)
        self.ui.delivery_delete_file_btn.clicked.connect(lambda: self.deletePage(self.ui.delivery_package_table))
        self.ui.delivery_table_del_btn.clicked.connect(self.deleteSelectedRows)
        self.ui.home_setup_btn.clicked.connect(self.setup_project)
        self.ui.delivery_export_btn.clicked.connect(self.export_selected_shots_for_delivery)
        self.ui.discord_random_btn.clicked.connect(self.discord_embed_color_random)
        self.ui.discord_embedding_color.textChanged.connect(lambda: self.toggle_widget_color(self.ui.discord_colorpicker_btn))
        self.ui.discord_colorpicker_btn.clicked.connect(self.discord_embed_color_picked)
        # self.ui.nuke_shot_lut.stateChanged.connect(self.toggle_shot_lut)
        # self.ui.nuke_show_lut.stateChanged.connect(self.toggle_show_lut)
        self.ui.google_job_matrix_add_btn.clicked.connect(lambda: self.ui.google_job_matrix_list.addItem(self.ui.line_edit.text()))
        self.ui.google_job_matrix_del_btn.clicked.connect(lambda: self.ui.google_job_matrix_list.takeItem(self.ui.google_job_matrix_list.currentRow()))
        self.ui.google_job_matrix_check_connection_btn.clicked.connect(self.check_google_connection)
    
    def run_google_sync(self):
        sys.path.append("..")
        import Google.shotgrid_jobmatrix_timelog_sync
        thread = threading.Thread(target = Google.shotgrid_jobmatrix_timelog_sync.main, args=(self.current_project,) )
        thread.start()

    def check_google_connection(self):
        import gspread

        gc = gspread.service_account(filename=r'Z:\pipe\Google\service_account.json')
        for index in range(self.ui.google_job_matrix_list.count()):
            item = self.ui.google_job_matrix_list.item(index)
            name = item.text()
            try:
                gc.open(name)
                item.setBackground(QColor(0, 200, 0))
            except:
                print(f"Could not connect to {name}.")
                item.setBackground(QColor(200, 0, 0))
    
    def reset_window_flags(self):
        flags = self.windowFlags()
        if flags & Qt.WindowStaysOnTopHint:
            flags &= ~Qt.WindowStaysOnTopHint  # Clear the flag
        else:
            flags |= Qt.WindowStaysOnTopHint   # Set the flag

        self.setWindowFlags(flags)

    def open_nuke_script(self):
        # Get the .nk script name
        button =self.sender().objectName()

        if button == "nuke_template_open_btn":
            script = os.path.join(ROOT, "settings", self.current_project, "WriteFIX_Comp.nk")
        elif button == "delivery_template_open_btn":
            script = self.ui.delivery_template.currentText() + ".nk"
        
        # Get the nuke exe path
        nuke_exe = self.get_nuke_path()
        
        # Create the terminal command inside Nuke
        command = f'"{nuke_exe}" -V 0 "{script}"'

        # Send the FIXPS Main Window to background
        self.reset_window_flags()

        # Run the command
        try:
            # Set the NUKE_PATH env var to add callbacks in FIXPS/menu.py
            NUKE_PATH = os.path.dirname(os.path.abspath(__file__))
            os.environ['NUKE_PATH'] = NUKE_PATH
            # Open Nuke
            run_command(command)
        except:
            print("Could not open Nuke.")
        
        # Show the FIXPS Main Window again
        self.show()

        # Update the modified nuke knobs to match the FIXPS data
        color_settings = self.get_json_data(self.project_settings_path())
        self.ui.nuke_color_management.setCurrentText(color_settings['nuke_color_management'])
        self.ui.nuke_ocio_config.setText(color_settings['nuke_ocio_config'])
        self.ui.nuke_int8lut.setText(color_settings['nuke_int8lut'])
        self.ui.nuke_int16lut.setText(color_settings['nuke_int16lut'])
        self.ui.nuke_loglut.setText(color_settings['nuke_loglut'])
        self.ui.nuke_floatlut.setText(color_settings['nuke_floatlut'])
        self.ui.nuke_monitorlut.setText(color_settings['nuke_monitorlut'])
        self.ui.nuke_workingspacelut.setText(color_settings['nuke_workingspacelut'])

    def toggle_widget_color(self, widget, color = None):
        if not color:
            color = self.ui.discord_embedding_color.text()
        widget.setStyleSheet(f"background: #{color}")
    
    def discord_embed_color_picked(self):
        parent = QWidget()
        parent.setWindowFlag(Qt.WindowStaysOnTopHint)
        color_dialog = QColorDialog()
        color = color_dialog.getColor(parent=parent)
        if color:
            self.ui.discord_embedding_color.setText(color.name()[1:])

    def generate_random_color_code(self, min_saturation=0.5):
        # Generate random hue, saturation, and brightness
        hue = random.uniform(0, 1)
        saturation = random.uniform(min_saturation, 1)
        brightness = random.uniform(0.5, 1)

        # Convert to RGB
        rgb = colorsys.hsv_to_rgb(hue, saturation, brightness)

        # Convert to hexadecimal color code
        color_code = "{:02X}{:02X}{:02X}".format(
            int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255)
        )

        return color_code
    
    def discord_embed_color_random(self):
        color = self.generate_random_color_code()
        self.ui.discord_embedding_color.setText(color)

    def toggle_shot_lut(self):
        self.ui.nuke_shotlut_template.setEnabled(self.sender().isChecked())
    def toggle_show_lut(self):
        self.ui.nuke_showlut_template.setEnabled(self.sender().isChecked())

    def setup_project(self):
        root = self.ui.home_project_root.currentText()
        if root == "":
            message = QMessageBox()
            message.setWindowFlag(Qt.WindowStaysOnTopHint)
            message.setText("Please choose a project root and try again.")
            message.exec_()
            return
        
        index = self.ui.project_combobox.findText(self.current_project)
        self.ui.project_combobox.setItemIcon(index, QIcon("icon/in_progress.png"))
        self.ui.shotgrid_tank_name.setText(self.current_project)
        self.ui.shotgrid_project_root.setText(root)
        project_location = sg.find_one("LocalStorage", [["code", "is", root]], ['windows_path', 'linux_path'])
        
        self.ui.shotgrid_project_location.setText(project_location['windows_path'])
        self.ui.stackedWidget.setCurrentIndex(2)
        
        project_settings_path = self.create_project_settings()
        sg_project = sg.find_one("Project",[["name", "is", self.current_project]], ['name'])
        sg.update(
                "Project", 
                sg_project['id'],
                {'tank_name': self.current_project,"sg_project_root": root}
                )
        
        destination = os.path.normpath(f"settings/{sg_project['name']}/WriteFIX_Comp.nk")
        shutil.copy("settings/WriteFIX_Comp.nk", destination)

        source_dir = "settings/templates"
        destination_dir = os.path.normpath(f"settings/{sg_project['name']}/templates")
        shutil.copytree(source_dir, destination_dir)
       
    def create_project_settings(self):
        path = self.project_settings_path()
        self.clear_current_data()
        data = self.get_current_data()
        self.dumb_json_data(path,data)
        self.populate_delivery_template_combobox()
        return path

    def on_project_change(self, id):
        changes = self.get_project_changes()

        if changes == None:            
            self.load()
            self.update_current_root()

        else:
            reply = QMessageBox.question(
                self,
                'Save',
                'Do you want to save current progress before switching project?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                # Save the application (you can add your save logic here)
                self.save()
                self.load()
                self.update_current_root()

            else:
                # Discard changes and exit
                self.load()
                self.update_current_root()


    def get_current_data(self):
        current_data = {}

        for widget in self.app.allWidgets():
            name = widget.objectName()
            if any(keyword in name for keyword in ['nuke', 'shotgrid', 'discord', 'google', 'delivery']):
                if isinstance(widget, (QLineEdit, QCheckBox)):
                    current_data[name] = widget.text() if isinstance(widget, QLineEdit) else widget.isChecked()

                elif isinstance(widget, QListWidget):
                    item_data = []
                    for i in range(widget.count()):
                        item = widget.item(i)
                        item_data.append({
                            'text': item.text(),
                            'checked': item.checkState() == Qt.Checked
                        })
                    current_data[name] = item_data

                elif isinstance(widget, QTableWidget):
                    modes = []
                    for row in range(widget.rowCount()):
                        item = widget.verticalHeaderItem(row)
                        modes.append(item.text())
                    current_data[name] = modes

                elif isinstance(widget, QComboBox):
                    if name not in['project_combobox', "home_project_root"]:
                        current_data[name] = widget.currentText()
                elif isinstance(widget, QTextEdit):
                    current_data[name] = widget.toPlainText()

        current_data['status'] = "in_progress"

        return current_data
    
    def clear_current_data(self):
        for widget in self.app.allWidgets():
            name = widget.objectName()
            if any(keyword in name for keyword in ['nuke', 'discord', 'google', 'delivery']):
                if isinstance(widget, QLineEdit):
                    widget.clear()
                if isinstance(widget, QCheckBox):
                    widget.setChecked(False)
                elif isinstance(widget, QListWidget):
                    widget.clear()

                elif isinstance(widget, QTableWidget):
                    widget.clearContents()
                    widget.setRowCount(0)

                elif isinstance(widget, QComboBox):
                    widget.clear()
                elif isinstance(widget, QTextEdit):
                    widget.clear()

    def get_project_changes(self):
        current_data = self.get_current_data()
        path = self.project_settings_path(self.current_project)

        if os.path.exists(path):
            last_data = self.get_json_data(path)
            if current_data == last_data:
                return None
            else:
                return current_data
        else:
            return None
        
    def get_json_data(self,path):
        with open(path, 'r') as json_file:
            data = json.load(json_file)
        return data
    
    def load_shotgrid_projects(self):
        projects = sg.find("Project", [["sg_status", "is", "active"]], ["name"])

        for project in projects:
            project_name = project['name']
            project_settings_status = self.get_project_settings_status(project_name)
            
            self.ui.project_combobox.addItem(project_name)
            current_index = self.ui.project_combobox.findText(project_name)

            if project_settings_status == "active":
                icon = "icon/active.png"
            elif project_settings_status == "in_progress":
                icon = "icon/in_progress.png"
            else:
                icon = "icon/inactive.png"

            self.ui.project_combobox.setItemIcon(current_index, QIcon(icon))

    def get_project_settings_status(self, project):
        path = self.project_settings_path(project)
        if os.path.exists(path):
            project_settings_status = self.get_json_data(path)['status']
        else:
            project_settings_status = None
        return project_settings_status
    
    ## Function for searching
    def on_search_btn_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(5)
        search_text = self.ui.search_input.text().strip()
        if search_text:
            self.ui.label_9.setText(search_text)

    ## Function for changing page to user page
    def on_user_btn_clicked(self):
        self.ui.stackedWidget.setCurrentIndex(6)

    ## Change QPushButton Checkable status when stackedWidget index changed
    def on_stackedWidget_currentChanged(self, index):
        btn_list = self.ui.side_menu_layout.findChildren(QPushButton)
        
        for btn in btn_list:
            btn.setAutoExclusive(False)
            btn.setChecked(False)

    
    def on_ingestion_btn_1_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(1)

    def on_nuke_btn_1_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(2)

    def on_nuke_btn_2_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(2)

    def on_shotgrid_btn_1_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(3)

    def on_shotgrid_btn_2_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(3)

    def on_discord_btn_1_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(4)

    def on_discord_btn_2_toggled(self, ):
        self.ui.stackedWidget.setCurrentIndex(4)
    
    def on_google_btn_1_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(5)
    
    def on_google_btn_2_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(5)
    
    def on_delivery_btn_1_toggled(self):
        self.ui.stackedWidget.setCurrentIndex(6)


    def add_row(self, name = None):
        if not name:
            name = self.get_user_input("Enter new preset name:")
            if name == "Comp":
                print("Comp name is reserved for the WriteFIX EXR/DPX sequence.")
                return
            
        table = self.ui.delivery_package_table
        table.setColumnWidth(0,400)
        row_count = table.rowCount()
        header_texts = [table.verticalHeaderItem(row).text() for row in range(row_count) if table.verticalHeaderItem(row) is not None]
        if name not in header_texts:
            table.insertRow(row_count)
            item = QTableWidgetItem(name)
            table.setVerticalHeaderItem(row_count,item)
            self.populate_row(row_count, name)
            table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def toggle_QR_checboxes(self, state):
        if state ==2:
            for widget in self.app.allWidgets():
                if "_QR" in widget.name():
                    widget.setEnabled(False)
        else:
            for widget in self.app.allWidgets():
                if "_QR" in widget.name():
                    widget.setEnabled(True)

    def populate_row(self, row, name = None):
        table = self.ui.delivery_package_table
        edit = QLineEdit()
        edit.setObjectName(f"delivery_package_table_{name}_template")
        
        data = self.get_json_data(self.project_settings_path())
        self.retrieve_widget_settings(edit,data )

        checkbox1_name = f"delivery_package_table_{name}_shotgrid"
        widget1, checkbox1 = self.table_checkbox(checkbox1_name)
        self.retrieve_widget_settings(checkbox1,data)

        # checkbox2_name = f"delivery_package_table_{name}_burnin"        
        # widget2, checkbox2 = self.table_checkbox(checkbox2_name)
        # self.retrieve_widget_settings(checkbox2,data)

        # widget3, checkbox3 = self.table_checkbox(f"delivery_package_table_{name}_luts")
        # self.retrieve_widget_settings(checkbox3,data)

        # checkbox4_name = f"delivery_package_table_{name}_handles"        
        # widget4, checkbox4 = self.table_checkbox(checkbox4_name)
        # self.retrieve_widget_settings(checkbox4,data)

        table.setCellWidget(row, 0, edit)
        table.setCellWidget(row, 1, widget1)
        # table.setCellWidget(row, 2, widget2)        
        # table.setCellWidget(row, 3, widget3)
        # table.setCellWidget(row, 4, widget4)
    
    def table_checkbox(self, name):
        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout()
        checkbox_widget.setLayout(checkbox_layout)
        checkbox = QCheckBox()
        checkbox.setObjectName(name)
        checkbox.setStyleSheet("QCheckBox::indicator"
                            "{"
                            "width :30px;"
                            "height : 30px;"
                            "}")
        checkbox_layout.addWidget(checkbox)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox_layout.setAlignment(checkbox, Qt.AlignCenter)
        
        return checkbox_widget, checkbox
    
    def get_user_input(self, title):
        dialog = UserInputDialog(title=title)
        if dialog.exec_() == QDialog.Accepted:
            input = dialog.line_edit.text()        
            return input

    def deletePage(self, table):
        current_index = table.currentRow()
        if current_index != -1 and self.ui.delivery_package_table.verticalHeaderItem(current_index).text() != "Comp":
            # Remove the current page from the toolbox
            table.removeRow(current_index)
            #table.setFixedHeight((table.rowCount())*50)
    
    def _save_flow_template(self, data):
        print("saving flow template")
        tamplate_path = os.path.join(f'Z:/pipe/Shotgrid/templates/{self.current_project}_templates.yml')

        if not os.path.exists(tamplate_path):
            template = {'paths':{}}
        else:        
            with open(tamplate_path, 'r') as file:
                template = yaml.safe_load(file)

        current_template = {}

        # Add Comp template
        if data['nuke_delivery_checkbox']:
            FIX_COMP = data["delivery_package_table_Comp_template"]
            if FIX_COMP != '{Shot}_v{version}/{Shot}_v{version}.{SEQ}.exr':
                current_template["FIX_Comp"] = {'definition': f'@shot_publish/{FIX_COMP}'}
            
        # Add Shot LUT template
        # if template:
        #     if data['nuke_shot_lut'] and "/" in data['nuke_shotlut_template']:
        #         shot_lut = data["nuke_shotlut_template"].replace("[", "(").replace("]", ")")
        #         current_template['shot_lut'] = {'definition': shot_lut}
        #     else:
        #         if 'shot_lut' in current_template.keys():
        #             current_template.pop('shot_lut')
        #         elif 'shot_lut' in template['paths'].keys():
        #             template['paths'].pop('shot_lut')
            
        #     # Add Show LUT template
        #     if data['nuke_show_lut'] and "/" in data['nuke_showlut_template']:
        #         show_lut = data["nuke_showlut_template"].replace("[", "(").replace("]", ")")
        #         current_template['show_lut'] = {'definition': show_lut}
        #     else:
        #         if 'show_lut' in current_template.keys():
        #             current_template.pop('show_lut')
        #         elif 'show_lut' in template['paths'].keys():
        #             template['paths'].pop('show_lut')

        #     template['paths'].update(current_template)
        
        with open(tamplate_path, 'w') as file:
            yaml.dump(template, file, default_flow_style=False)

    def save(self):
        splash = SplashScreen()
        splash.show()

        # Get current session data
        data = self.get_current_data()
        self.dumb_json_data(self.project_settings_path(),  dict(sorted(data.items())))
        
        # Save the templates to Flow PT configuration .yaml
        self._save_flow_template(data)

        # Update the WriteFIX.nk template
        # This template also holds the color, format, fps settings for tk-multi-setsettings application
        nuke_exe = self.get_nuke_path()
        nuke_script = os.path.join(ROOT, "settings", self.current_project, "WriteFIX_Comp.nk")
        python_script = os.path.join(os.path.dirname(THIS_FILE), "update_writefix_template.py")
        command = f'"{nuke_exe}" --tg {python_script} "{nuke_script}"'

        update_thread = threading.Thread(target=run_command, args=(command, splash, self))
        update_thread.start()

    def dumb_json_data(self,path,data):
        if not os.path.exists(os.path.dirname(path)):
            os.mkdir(os.path.dirname(path))
        with open(path, 'w') as json_file:
            json.dump(data, json_file, indent=4)

    def project_settings_path(self, project = None):
        if project == None:
            project = self.current_project
        return os.path.join("settings", project, "settings.json")
    
    def set_current_project(self):
        last_project = self.get_json_data('settings/preferences.json')['last_project']
        combobox = self.ui.project_combobox
        project = combobox.currentText()
        if last_project:
            if not self.initialized:
                project = last_project
            combobox.setCurrentIndex(combobox.findText(project))
            status = self.get_project_settings_status(project)
            if status not in ['active', 'in_progress']:
                self.ui.stackedWidget.setCurrentIndex(0)
                self.setup_available_roots()
            else:
                if not self.initialized:
                    self.ui.stackedWidget.setCurrentIndex(2)
        else:
            self.ui.stackedWidget.setCurrentIndex(0)
            self.setup_available_roots()

        self.ui.home_project_name.setText(project)
        return project
    
    def enable_side_menu(self, value=False):
        for i in range(self.ui.side_menu_layout.count()):
            widget = self.ui.side_menu_layout.itemAt(i).widget()
            if widget:
                widget.setEnabled(value)

    def load(self):
        if self.ui.project_combobox.count() == 0:
            self.load_shotgrid_projects()

        self.current_project = self.set_current_project()
        path = self.project_settings_path()

        if os.path.exists(path):
            for widget in self.app.allWidgets():
                data = self.get_json_data(path)
                self.retrieve_widget_settings(widget, data)

        self.populate_delivery_template_combobox()
        
        self.initialized = True

    def populate_delivery_template_combobox(self):
        self.ui.delivery_template.clear()
        templates_path = os.path.join(os.path.abspath(os.path.dirname(self.project_settings_path())), "templates")

        if os.path.exists(templates_path):
            templates = []
            for f in os.listdir(templates_path):
                template = os.path.join(templates_path, f.split(".")[0])
                if template not in templates:
                    templates.append(template)

            self.ui.delivery_template.addItems(templates)

    def retrieve_widget_settings(self, widget, data):
        name = widget.objectName()

        if name in data.keys():
            if isinstance(widget, QLineEdit):
                widget.setText(data[name])

            elif isinstance(widget, QCheckBox):
                widget.setChecked(data[name])

            elif isinstance(widget, QListWidget):
                widget.clear()
                for item_data in data[name]:
                    item = QListWidgetItem(item_data['text'])
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked if item_data['checked'] else Qt.Unchecked)
                    widget.addItem(item)

            elif isinstance(widget, QTableWidget):
                while widget.rowCount() > 0:
                # Remove each page individually
                    widget.removeRow(0)
                for row in data[name]:
                    if name != "Comp" and name:
                        self.add_row(row)

            elif isinstance(widget, QTextEdit):
                widget.setText(data[name])

            elif isinstance(widget, QComboBox):
                widget.setCurrentIndex(widget.findText(data[name]))

    def exit(self):
        self.close()
    
    def closeEvent(self, event):
        project_changes = self.get_project_changes()
        if project_changes != None:
            reply = QMessageBox.question(
                self,
                'Save',
                'Do you want to save the application before exiting?',
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                # Save the application (you can add your save logic here)
                self.save()
                self.dumb_json_data("settings/preferences.json", {"last_project":self.current_project})
                event.accept()
            elif reply == QMessageBox.No:
                # Discard changes and exit
                self.dumb_json_data("settings/preferences.json", {"last_project":self.current_project})
                event.accept()
            else:
                # Cancel the close event
                event.ignore()
        else:
            self.dumb_json_data("settings/preferences.json", {"last_project":self.current_project})
            event.accept()

def get_exr_dimensions(filepath):
    import OpenEXR
    
    path = filepath.replace("####", "1001").replace("%04d", "1001")
    if os.path.exists(path):
        # Open the EXR file
        exr_file = OpenEXR.InputFile(path)
        # Extract header information
        header = exr_file.header()

        # The data window gives the image bounds (min.x, min.y, max.x, max.y)
        data_window = header['dataWindow']
        
        # Calculate width and height
        width = data_window.max.x - data_window.min.x + 1
        height = data_window.max.y - data_window.min.y + 1
        
        return str(width), str(height)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    style_file = QFile("python\style.qss")
    style_file.open(QFile.ReadOnly | QFile.Text)
    style_stream = QTextStream(style_file)
    app.setStyleSheet(style_stream.readAll())   
    
    window = MainWindow(app)
    window.setWindowTitle("Fix Visual FX Project Toolkit")
    window.show()

    sys.exit(app.exec_())
```

# python\menu.py

```py
import nuke
import os
import json

def update_callback():
    try:
        root = nuke.root()
        name = root['name'].value()
        project_dir = (os.path.sep).join(name.split("/")[:-1])
        settings_path = os.path.join(project_dir, "settings.json")
        with open(settings_path, 'r')as f:
            settings = json.load(f)

        cm = root['colorManagement']
        ws = root['workingSpaceLUT']
        monitor = root['monitorLut']
        int8 = root['int8Lut']
        int16 = root['int16Lut']
        log = root['logLut']
        floatt = root['floatLut']
        ocio = root['OCIO_config']
        settings['nuke_color_management'] = cm.value()
        settings['nuke_workingspacelut'] = ws.value()
        settings['nuke_monitorlut'] = monitor.value()
        settings['nuke_int8lut'] = int8.value()
        settings['nuke_int16lut'] = int16.value()
        settings['nuke_loglut'] = log.value()
        settings['nuke_floatlut'] = floatt.value()
        settings['nuke_ocio_config'] = ocio.value()
        
        with open(settings_path, 'w')as f:
            settings = json.dump(settings, f, indent=4)
        nuke.tprint("Sucesfully saved color settings to json file.")
    except:
        pass

nuke.addOnScriptClose(update_callback)
```

# python\style.qss

```qss
* {
    color: #f2f2f2;  /* Change text color to white */
}

/* Style for disabled text */
*:disabled {
    color: #b3b3cc;  /* Change disabled text color to gray */
}
/*= Style for mainwindow START
  ==================================================== */
  	QWidget {
		background-color: #313a46
	}
  
	QMainWindow {
		background-color: #313a46;
	}
	QDialog{
		background-color: #313a46;
	}
	QToolTip {
    background-color: #1b2027; /* Dark blue background */
    color: white; /* White text */
    border: 1px solid white; /* Optional: White border around tooltip */
    padding: 5px; /* Optional: Padding inside tooltip */
    border-radius: 3px; /* Optional: Rounded corners */
	}
/*= END
  ==================================================== */

/*= Style for button to change menu style START
  ==================================================== */
	QLineEdit{
		background-color: #4b596b8a;
		border-radius: 0px;
	}
	QComboBox{
		background-color: #4b596b8a;
		border-radius: 0px;
	}
	QPushButton{
		background-color: #4b596b8a;
		border:none;
		border-radius: 3px;
		padding: 4px 0px 4px 0px;
		color: #f2f2f2;
	}
	QPushButton:hover{
		background-color: rgba(0, 50, 150, 0.5)
	}
	QPushButton:pressed {
		background-color: rgba( 0, 50, 150, 0.85);
	}
	QTableWidget{
		background-color: #4b596b8a;
		border-radius: 0px;
		selection-background-color: #4181C0;
	}
	#menu_btn {
		padding: 5px;
		border: none;
		width: 30px;
		height: 30px;
	}
	#menu_btn:hover {
		background-color: rgba( 186, 201, 215, 1);
	}
	#menu_btn {
		color: #fff;
	}
	QHeaderView::section {
		background-color: #4b596b8a;
	}
	QTableWidget QTableCornerButton::section{
		background-color: #4b596b8a;
	}
/*= END
  ==================================================== */

/*= Style for header widget START
  ==================================================== */

/*= END
  ==================================================== */
	#widget_3{
		background-color: rgba( 86, 101, 115, 0.5)

	}

/*= Style for menu with icon only START
  ==================================================== */
  	/* style for widget */
	#icon_menu_widget {
		background-color: #313a46;
		width:50px;
	}

    /* style for QPushButton and QLabel */
	#icon_menu_widget QPushButton, QLabel {
		height:50px;
		border:none;
		/* border-bottom: 1px solid #b0b0b0; */
	}

	#icon_menu_widget QPushButton:hover {
		background-color: rgba( 86, 101, 115, 0.5);
	}

	/* style for logo image */
	#logo_label_1 {
		padding: 5px
	}
/*= END
  ==================================================== */

/*= Style for menu with icon and text START
  ==================================================== */
	/* style for widget */
	#full_menu_widget {
		background-color: #1b2027;
	}

	/* style for QPushButton */
	#full_menu_widget QPushButton {
		background-color: rgba(0,0,0,0);
		border:none;
		border-radius: 3px;
		text-align: left;
		padding: 8px 0 8px 15px;
		color: #788596;
	}

	#full_menu_widget QPushButton:hover {
		background-color: rgba( 86, 101, 115, 0.5);
	}

	#full_menu_widget QPushButton:checked {
		background-color: rgba( 86, 101, 115, 0.5);
		color: #fff;
	}
	
	#full_menu_widget QPushButton:pressed {
		background-color: rgba( 86, 101, 115, 0.85);
	}

	/* style for logo image */
	#logo_label_2 {
		padding: 5px;
		color: #fff;
	}

	/* style for APP title */
	#logo_label_3 {
		padding-right: 10px;
		color: #fff;
	}
/*= END
  ==================================================== */

/*= Style for search button START
  ==================================================== */
	#search_btn {
		border: none;
	}
/*= END
  ==================================================== */

/*= Style for search input START
  ==================================================== */
	#search_input {
		border: none;
		padding: 5px 10px;
	}

	#search_input:focus {
		background-color: #70B9FE;
	}
/*= END
  ==================================================== */

/*= Style for user information button START
  ==================================================== */
	#user_btn {
		border: none;
	}
/*= END
  ==================================================== */

/* Style the entire QTabWidget */
QTabWidget {
	background-color: rgba( 0, 0, 0, 0);
	color: #788596;
}

/* Style the pane of QTabWidget */
QTabWidget::pane {
    border-top: 2px solid white; /* Top border for the tab content area */
}

/* Style the tab bar (the area holding the tabs) */
QTabBar {
    background-color: rgba( 0, 0, 0, 0);
}

/* Style each individual tab */
QTabBar::tab {
    background-color: rgba( 0 0, 0, 0);
    border: none;
    padding: 5px 10px;
    margin-right: 1px;
}

/* Style the selected tab */
QTabBar::tab:selected {
	background-color: rgba( 86, 101, 115, 0.5);
	color: #fff;
}

/* Style the tab when hovered */
QTabBar::tab:hover {
    background-color: rgba( 86, 101, 115, 0.85);
}
```

# python\update_writefix_template.py

```py
import sys
def setup_template(nuke_script):
    import nuke
    import json
    import os

    project_dir = (os.path.sep).join(nuke_script.split(os.path.sep)[:-1])
    settings_path = os.path.join(project_dir, "settings.json")

    with open(settings_path, 'r')as f:
        settings = json.load(f)

    nuke.scriptOpen(nuke_script)
    root = nuke.root()
    
    # Set Default Nuke Script Settings
    root['fps'].setValue(float(settings['nuke_fps']))
    project = project_dir.split(os.path.sep)[-1]
    format = f"{settings['nuke_format_w']} {settings['nuke_format_h']} 0 0 {settings['nuke_format_w']} {settings['nuke_format_h']} {settings['nuke_format_pixelaspect']} {project}"
    try:
        root['format'].setValue(project)
    except:
        nuke.addFormat(format)
        root['format'].setValue(project)

    #Set Burn ins
    try:
        nuke.toNode("TOP_LEFT")['message'].setValue(settings['delivery_burnin_topleft'])
        nuke.toNode("TOP_RIGHT")['message'].setValue(settings['delivery_burnin_topright'])
        nuke.toNode("TOP_CENTER")['message'].setValue(settings['delivery_burnin_topmid'])
        nuke.toNode("BOTTOM_LEFT")['message'].setValue(settings['delivery_burnin_botleft'])
        nuke.toNode("BOTTOM_CENTER")['message'].setValue(settings['delivery_burnin_botmid'])
        nuke.toNode("BOTTOM_RIGHT")['message'].setValue(settings['delivery_burnin_botright'])
        nuke.toNode("SLATE")['message'].setValue(settings['delivery_slate'])
    except:
        print("Could not set BURNINS and SLATE")
    # Set Color Settings
    cm = root['colorManagement']
    cm.setValue(settings['nuke_color_management'])
    ws = root['workingSpaceLUT']
    ws.setValue(settings['nuke_workingspacelut'])
    monitor = root['monitorLut']
    monitor.setValue(settings['nuke_monitorlut'])
    monitor_out = root['monitorOutLUT']
    monitor_out.setValue(settings['nuke_monitorlut'])
    int8 = root['int8Lut']
    int8.setValue(settings['nuke_int8lut'])
    int16 = root['int16Lut']
    int16.setValue(settings['nuke_int16lut'])
    log = root['logLut']
    log.setValue(settings['nuke_loglut'])
    floatt = root['floatLut']
    floatt.setValue(settings['nuke_floatlut'])
    ocio = root['OCIO_config']
    ocio.setValue(settings['nuke_ocio_config'])

    # Check if SHow/Shot LUT nodes are available
    try:
        nuke.toNode("Show_LUT").setSelected(settings['nuke_show_lut'])
        nuke.toNode("Shot_LUT").setSelected(settings['nuke_shot_lut'])
    except:
        print("Could not find LUT nodes.")

    nuke.scriptSave(nuke_script)

if __name__ == "__main__":
    # Check if at least one argument is provided
    if len(sys.argv) < 2:
        print("Usage: python render_script.py <argument>")
        sys.exit(1)

    # Access the argument    
    nuke_script = sys.argv[1]
    setup_template(nuke_script)
```

# README.md

```md
# fixptk
FixFX Production Toolkit. Provides a front end UI for setting up projects and studio environments and performing high level tasks like deliveries.

```

# run_robocopy.ps1

```ps1
param(
    [string]$SourcePath,
    [string]$DestinationPath,
    [string]$FileName = $null  # Optional, default is null
)

Function Get-RobocopyProgress {
    param(
        [Parameter(Mandatory, ValueFromPipeline)]
        $InputObject,
    
        [string]$SourcePath,
        [string]$DestinationPath
    )

    begin {
        [string]$file = " "
        [double]$percent = 0
        [double]$size = $Null
        [double]$count = (Get-ChildItem -Path $SourcePath -File -Recurse).Count
        [double]$filesLeft = $count
        [double]$number = 0
    }

    process {
        $Host.PrivateData.ProgressBackgroundColor='White' 
        $Host.PrivateData.ProgressForegroundColor='Black'

        # Split input, handle potential errors
        $data = $InputObject -split '\x09'
        
        try {
            # Handle filename
            If (![String]::IsNullOrEmpty($data[4])) {
                $file = $data[4] -replace '.+\\(?=(?:.(?!\\))+$)'
                $filesLeft--
                $number++
            }
            
            # Handle percentage - ensure it is a valid number
            If (![String]::IsNullOrEmpty($data[0])) {
                $percentString = ($data[0] -replace '%') -replace '\s'
                if ([double]::TryParse($percentString, [ref]$percent)) {
                    $percent = [math]::Max(0, [math]::Min(100, $percent)) # Ensure it's between 0 and 100
                } else {
                    Write-Warning "Invalid percentage format: $data[0]"
                    $percent = 0
                }
            }

            # Handle size - ensure it is a valid number
            If (![String]::IsNullOrEmpty($data[3])) {
                if (![double]::TryParse($data[3], [ref]$size)) {
                    Write-Warning "Invalid size format: $data[3]"
                    $size = 0
                }
            }

        } catch {
            Write-Warning "Error parsing robocopy data: $_"
        }

        # Convert size to readable format
        [String]$sizeString = switch ($size) {
            {$_ -ge 1TB} {
                "{0:n2} TB" -f ($size / 1TB)
            }
            {$_ -ge 1GB} {
                "{0:n2} GB" -f ($size / 1GB)
            }
            {$_ -ge 1MB} {
                "{0:n2} MB" -f ($size / 1MB)
            }
            {$_ -ge 1KB} {
                "{0:n2} KB" -f ($size / 1KB)
            }
            default {
                "$size B"
            }
        }

        # Display progress
        Write-Progress -Activity "   Currently Copying: ..\$file" `
                       -CurrentOperation  "Copying: $number of $count     Copied: $($number - 1) / $count     Files Left: $(($filesLeft + 1))" `
                       -Status "Size: $sizeString       Complete: $percent%" `
                       -PercentComplete $percent
    }
}

# Robocopy logic
try {
    if ($FileName) {
        # Copy a single file
        robocopy $SourcePath $DestinationPath $FileName /NJH /NDL /NC /BYTES /XO /R:5 /W:5
    } else {
        # Copy all files and directories
        robocopy $SourcePath $DestinationPath /E /NJH /NDL /NC /BYTES /XO /R:5 /W:5
    }
} catch {
    Write-Error "Error running robocopy: $_"
}

```

