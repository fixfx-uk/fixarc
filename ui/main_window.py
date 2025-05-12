# fixarc/ui/main_window.py
"""
Main window implementation for the Fixarc Handler UI using PyQt5.
"""

import sys
import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any

from PyQt5 import QtWidgets, QtCore, QtGui

# Use fixenv for constants/defaults if available
try:
    import fixenv
    from fixenv.core import normalize_path
    DEFAULT_VENDOR = fixenv.constants.STUDIO_SHORT_NAME
    DEFAULT_BASE_PATH_FUNC = lambda: normalize_path(fixenv.constants.FIXSTORE_DRIVE + '/proj') if hasattr(fixenv.constants, 'FIXSTORE_DRIVE') else None
except ImportError:
    DEFAULT_VENDOR = "FixFX" # Hardcoded fallback
    DEFAULT_BASE_PATH_FUNC = 'Z:/proj'


# Import UI utilities and package logger
from . import data_utils, log
# Import fixarc exceptions if available for more specific error handling
try:
    from fixarc.exceptions import ConfigurationError
except ImportError:
    ConfigurationError = ValueError # Fallback exception type


class FixarcHandlerWindow(QtWidgets.QMainWindow):
    """Main application window for the Fixarc Handler UI."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Fixarc Handler UI")
        self.setGeometry(100, 100, 800, 750) # x, y, width, height

        self.current_base_path: Optional[str] = None
        self.process: Optional[QtCore.QProcess] = None
        self.fixarc_handler_path: Optional[str] = self._find_fixarc_handler()

        self._setup_ui()
        self._connect_signals()
        self._initialize_state()

        log.info("Fixarc Handler UI initialized.")

    def _find_fixarc_handler(self) -> Optional[str]:
        """Attempts to locate the fixarc-handler script/executable."""
        # 1. Check alongside this script (if running from source)
        script_dir = Path(__file__).parent.parent # Go up to fixarc package level
        handler_in_bin = script_dir / "bin" / "fixarc-handler" # Assuming a structure
        if handler_in_bin.is_file():
             log.debug(f"Found fixarc-handler in bin: {handler_in_bin}")
             return str(handler_in_bin)

        # 2. Check system PATH (using shutil.which)
        import shutil
        handler_in_path = shutil.which("fixarc-handler")
        if handler_in_path:
             log.debug(f"Found fixarc-handler in PATH: {handler_in_path}")
             return handler_in_path

        log.error("Could not find 'fixarc-handler' executable/script.")
        # Optionally prompt user to locate it here
        return None

    # -------------------------------------------------------------------------
    # UI Setup
    # -------------------------------------------------------------------------

    def _setup_ui(self):
        """Creates and arranges widgets."""
        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QtWidgets.QVBoxLayout(main_widget)

        # --- Selection Filters ---
        filter_group = QtWidgets.QGroupBox("Selection Filters")
        filter_layout = QtWidgets.QGridLayout()
        filter_group.setLayout(filter_layout)

        filter_layout.addWidget(QtWidgets.QLabel("Project*:"), 0, 0)
        self.project_combo = QtWidgets.QComboBox()
        filter_layout.addWidget(self.project_combo, 0, 1)

        filter_layout.addWidget(QtWidgets.QLabel("Episode(s):"), 1, 0, QtCore.Qt.AlignTop)
        self.episode_list = QtWidgets.QListWidget()
        self.episode_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.episode_list.setMaximumHeight(100)
        filter_layout.addWidget(self.episode_list, 1, 1)

        filter_layout.addWidget(QtWidgets.QLabel("Sequence(s):"), 2, 0, QtCore.Qt.AlignTop)
        self.sequence_list = QtWidgets.QListWidget()
        self.sequence_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.sequence_list.setMaximumHeight(100)
        filter_layout.addWidget(self.sequence_list, 2, 1)

        filter_layout.addWidget(QtWidgets.QLabel("Available Shots:"), 3, 0, QtCore.Qt.AlignTop)
        shot_v_layout = QtWidgets.QVBoxLayout()
        self.shot_list = QtWidgets.QListWidget()
        self.shot_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        shot_v_layout.addWidget(self.shot_list)
        self.shot_filter_input = QtWidgets.QLineEdit()
        self.shot_filter_input.setPlaceholderText("Filter shots...")
        shot_v_layout.addWidget(self.shot_filter_input)
        filter_layout.addLayout(shot_v_layout, 3, 1)

        main_layout.addWidget(filter_group)

        # --- Output & Archiving Options ---
        output_group = QtWidgets.QGroupBox("Output & Archiving Options")
        output_layout = QtWidgets.QGridLayout()
        output_group.setLayout(output_layout)

        output_layout.addWidget(QtWidgets.QLabel("Archive Root*:"), 0, 0)
        self.archive_root_input = QtWidgets.QLineEdit()
        self.browse_archive_root_btn = QtWidgets.QPushButton("Browse...")
        output_layout.addWidget(self.archive_root_input, 0, 1)
        output_layout.addWidget(self.browse_archive_root_btn, 0, 2)

        output_layout.addWidget(QtWidgets.QLabel("Max Versions:"), 1, 0)
        max_ver_layout = QtWidgets.QHBoxLayout()
        self.max_versions_combo = QtWidgets.QComboBox()
        self.max_versions_combo.addItems(["Latest Only", "All Versions", "Custom Number"])
        self.max_versions_spinbox = QtWidgets.QSpinBox()
        self.max_versions_spinbox.setMinimum(1)
        self.max_versions_spinbox.setValue(3)
        self.max_versions_spinbox.setEnabled(False) # Disabled initially
        max_ver_layout.addWidget(self.max_versions_combo)
        max_ver_layout.addWidget(self.max_versions_spinbox)
        output_layout.addLayout(max_ver_layout, 1, 1, 1, 2) # Span 1 row, 2 columns

        output_layout.addWidget(QtWidgets.QLabel("Client Config:"), 2, 0)
        self.client_config_input = QtWidgets.QLineEdit()
        self.browse_client_config_btn = QtWidgets.QPushButton("Browse...")
        output_layout.addWidget(self.client_config_input, 2, 1)
        output_layout.addWidget(self.browse_client_config_btn, 2, 2)

        main_layout.addWidget(output_group)

        # --- Fixarc Tool Settings ---
        fixarc_group = QtWidgets.QGroupBox("Fixarc Tool Settings (for --fixarc-options)")
        fixarc_layout = QtWidgets.QGridLayout()
        fixarc_group.setLayout(fixarc_layout)

        self.bake_gizmos_check = QtWidgets.QCheckBox("Bake Gizmos")
        self.update_paths_check = QtWidgets.QCheckBox("Update Paths (relative to archive)")
        self.fixarc_dry_run_check = QtWidgets.QCheckBox("Dry Run (fixarc only)")

        fixarc_layout.addWidget(self.bake_gizmos_check, 0, 0)
        fixarc_layout.addWidget(self.update_paths_check, 0, 1)
        fixarc_layout.addWidget(self.fixarc_dry_run_check, 0, 2)

        fixarc_layout.addWidget(QtWidgets.QLabel("Vendor Name:"), 1, 0)
        self.vendor_name_input = QtWidgets.QLineEdit(DEFAULT_VENDOR)
        fixarc_layout.addWidget(self.vendor_name_input, 1, 1, 1, 2)

        fixarc_layout.addWidget(QtWidgets.QLabel("Other Options:"), 2, 0)
        self.raw_fixarc_options_input = QtWidgets.QLineEdit()
        self.raw_fixarc_options_input.setPlaceholderText("--option value")
        fixarc_layout.addWidget(self.raw_fixarc_options_input, 2, 1, 1, 2)

        main_layout.addWidget(fixarc_group)

        # --- Execution & Logging ---
        exec_group = QtWidgets.QGroupBox("Execution & Logging")
        exec_layout = QtWidgets.QGridLayout()
        exec_group.setLayout(exec_layout)

        self.farm_check = QtWidgets.QCheckBox("Submit to Farm (via handler --farm)")
        exec_layout.addWidget(self.farm_check, 0, 0)

        exec_layout.addWidget(QtWidgets.QLabel("Log Verbosity:"), 0, 1)
        self.log_verbosity_combo = QtWidgets.QComboBox()
        self.log_verbosity_combo.addItems(["Info", "Debug"])
        exec_layout.addWidget(self.log_verbosity_combo, 0, 2)

        button_layout = QtWidgets.QHBoxLayout()
        self.preview_button = QtWidgets.QPushButton("Preview Scripts")
        self.execute_button = QtWidgets.QPushButton("Execute Archive")
        button_layout.addWidget(self.preview_button)
        button_layout.addWidget(self.execute_button)
        exec_layout.addLayout(button_layout, 1, 0, 1, 3) # Span 1 row, 3 columns

        main_layout.addWidget(exec_group)

        # --- Status & Logs ---
        log_group = QtWidgets.QGroupBox("Status & Logs")
        log_layout = QtWidgets.QVBoxLayout()
        log_group.setLayout(log_layout)
        self.log_output_area = QtWidgets.QTextEdit()
        self.log_output_area.setReadOnly(True)
        self.log_output_area.setFontFamily("Courier") # Monospaced font
        log_layout.addWidget(self.log_output_area)
        main_layout.addWidget(log_group)

        # --- Status Bar ---
        self.statusBar = QtWidgets.QStatusBar()
        self.setStatusBar(self.statusBar)
        self.status_base_path_label = QtWidgets.QLabel("Base:")
        self.status_shots_label = QtWidgets.QLabel("Shots: 0/0")
        self.status_feedback_label = QtWidgets.QLabel("Ready")
        self.change_base_path_btn = QtWidgets.QPushButton("Change Base Path...")
        self.change_base_path_btn.setStyleSheet("padding: 1px 5px;") # Make it smaller

        self.statusBar.addPermanentWidget(self.status_shots_label)
        self.statusBar.addPermanentWidget(self.status_base_path_label)
        self.statusBar.addPermanentWidget(self.change_base_path_btn)
        self.statusBar.addWidget(self.status_feedback_label) # Message area on the left

    # -------------------------------------------------------------------------
    # Signal Connections
    # -------------------------------------------------------------------------

    def _connect_signals(self):
        """Connects widget signals to handler slots."""
        self.project_combo.currentIndexChanged.connect(self._project_changed)
        self.episode_list.itemSelectionChanged.connect(self._episode_selection_changed)
        self.sequence_list.itemSelectionChanged.connect(self._sequence_selection_changed)
        self.shot_list.itemSelectionChanged.connect(self._shot_selection_changed)
        self.shot_filter_input.textChanged.connect(self._filter_shot_list_display)

        self.browse_archive_root_btn.clicked.connect(self._browse_archive_root)
        self.browse_client_config_btn.clicked.connect(self._browse_client_config)
        self.change_base_path_btn.clicked.connect(self._change_base_path)

        self.max_versions_combo.currentIndexChanged.connect(self._max_versions_changed)

        self.preview_button.clicked.connect(self._handle_preview_scripts)
        self.execute_button.clicked.connect(self._handle_execute_archiving)

    # -------------------------------------------------------------------------
    # Initial State & Population
    # -------------------------------------------------------------------------

    def _initialize_state(self):
        """Sets the initial state of the UI, including base path and projects."""
        try:
            default_path = data_utils.get_default_base_path()
            if default_path and os.path.isdir(default_path):
                self.current_base_path = default_path
                log.info(f"Using default base path: {self.current_base_path}")
            else:
                log.warning("Could not determine a valid default base path.")
                # Prompt user or show error
                QtWidgets.QMessageBox.warning(self, "Base Path Not Found",
                                            "Could not automatically determine the project base path (e.g., Z:/proj).\nPlease set it manually using the 'Change Base Path...' button.")
        except Exception as e:
            log.error(f"Error getting default base path: {e}")

        self._update_status_bar()
        self._populate_projects()

        # Set default max versions combo
        self.max_versions_combo.setCurrentIndex(0) # Latest Only
        # Check if handler is found
        if not self.fixarc_handler_path:
             self.execute_button.setEnabled(False)
             self.preview_button.setEnabled(False)
             self.status_feedback_label.setText("Error: fixarc-handler not found!")
             QtWidgets.QMessageBox.critical(self, "Handler Not Found",
                                            "The 'fixarc-handler' script/executable could not be located.\nPlease ensure it's in your system's PATH or installed correctly.")


    def _populate_projects(self):
        """Populates the project combo box."""
        self.project_combo.blockSignals(True) # Prevent triggering change signal
        self.project_combo.clear()
        self.project_combo.addItem("") # Add empty option first
        if self.current_base_path:
            try:
                projects = data_utils.get_projects(self.current_base_path)
                self.project_combo.addItems(projects)
                log.debug(f"Populated {len(projects)} projects.")
            except Exception as e:
                log.error(f"Failed to populate projects: {e}")
                QtWidgets.QMessageBox.critical(self, "Error", f"Failed to list projects in {self.current_base_path}:\n{e}")
        self.project_combo.blockSignals(False)
        self._clear_downstream_lists(clear_episodes=True) # Clear everything below project

    def _populate_episodes(self):
        """Populates the episode list based on selected project."""
        self.episode_list.clear()
        selected_project = self.project_combo.currentText()
        if self.current_base_path and selected_project:
            try:
                episodes = data_utils.get_episodes(self.current_base_path, selected_project)
                self.episode_list.addItems(episodes)
                log.debug(f"Populated {len(episodes)} episodes for project '{selected_project}'.")
            except Exception as e:
                log.error(f"Failed to populate episodes for {selected_project}: {e}")
        self._clear_downstream_lists(clear_sequences=True) # Clear sequence and shot

    def _populate_sequences(self):
        """Populates the sequence list based on selected project and episodes."""
        self.sequence_list.clear()
        selected_project = self.project_combo.currentText()
        selected_episodes = self._get_selected_items(self.episode_list)
        if self.current_base_path and selected_project and selected_episodes:
            try:
                sequences = data_utils.get_sequences(self.current_base_path, selected_project, selected_episodes)
                self.sequence_list.addItems(sequences)
                log.debug(f"Populated {len(sequences)} sequences for episodes: {selected_episodes}.")
            except Exception as e:
                log.error(f"Failed to populate sequences for {selected_episodes}: {e}")
        self._clear_downstream_lists(clear_shots=True) # Clear shot only

    def _populate_shots(self):
        """Populates the shot list based on selected project, episodes, and sequences."""
        self.shot_list.clear()
        selected_project = self.project_combo.currentText()
        selected_episodes = self._get_selected_items(self.episode_list)
        selected_sequences = self._get_selected_items(self.sequence_list)

        # If no episodes selected, populate with all shots for the project (or based on sequences if selected)
        # If no sequences selected, populate based on selected episodes

        if self.current_base_path and selected_project:
            try:
                # Pass empty lists if nothing is selected at that level
                shots = data_utils.get_shots(self.current_base_path, selected_project,
                                             selected_episodes, selected_sequences)
                self.shot_list.addItems(shots)
                log.debug(f"Populated {len(shots)} shots based on current filters.")
            except Exception as e:
                log.error(f"Failed to populate shots: {e}")
        self._filter_shot_list_display() # Apply filter immediately

    def _clear_downstream_lists(self, clear_episodes=False, clear_sequences=False, clear_shots=False):
        """Clears lists below a certain level."""
        if clear_episodes:
            self.episode_list.clear()
            clear_sequences = True # If episodes cleared, sequences must be too
        if clear_sequences:
            self.sequence_list.clear()
            clear_shots = True # If sequences cleared, shots must be too
        if clear_shots:
            self.shot_list.clear()
            self.shot_filter_input.clear()
            self._update_status_bar() # Update counts


    # -------------------------------------------------------------------------
    # Event Handlers / Slots
    # -------------------------------------------------------------------------

    def _project_changed(self):
        log.debug(f"Project changed to: {self.project_combo.currentText()}")
        self._populate_episodes()
        self._populate_shots() # Show all shots initially for the project

    def _episode_selection_changed(self):
        selected_episodes = self._get_selected_items(self.episode_list)
        log.debug(f"Episode selection changed: {selected_episodes}")
        self._populate_sequences()
        self._populate_shots()

    def _sequence_selection_changed(self):
        selected_sequences = self._get_selected_items(self.sequence_list)
        log.debug(f"Sequence selection changed: {selected_sequences}")
        self._populate_shots()

    def _shot_selection_changed(self):
        self._update_status_bar() # Just update counts

    def _filter_shot_list_display(self):
        """Hides/shows items in the shot list based on the filter input."""
        filter_text = self.shot_filter_input.text().lower()
        visible_count = 0
        total_count = self.shot_list.count()
        for i in range(total_count):
            item = self.shot_list.item(i)
            is_match = filter_text in item.text().lower()
            item.setHidden(not is_match)
            if is_match:
                visible_count += 1

        # Update status bar with filtered counts
        selected_count = len(self._get_selected_items(self.shot_list)) # Count selected among visible
        self.status_shots_label.setText(f"Shots: {selected_count} sel / {visible_count} vis / {total_count} tot")

    def _browse_archive_root(self):
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Archive Root Directory")
        if dir_path:
            self.archive_root_input.setText(normalize_path(dir_path))

    def _browse_client_config(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Client Config JSON", filter="JSON files (*.json)")
        if file_path:
            self.client_config_input.setText(normalize_path(file_path))

    def _change_base_path(self):
        dir_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Project Base Path (e.g., Z:/proj)")
        if dir_path:
            norm_path = normalize_path(dir_path)
            if os.path.isdir(norm_path):
                self.current_base_path = norm_path
                log.info(f"User changed base path to: {self.current_base_path}")
                self._update_status_bar()
                self._clear_downstream_lists(clear_episodes=True) # Clear everything
                self._populate_projects()
            else:
                 QtWidgets.QMessageBox.warning(self, "Invalid Path", f"The selected path is not a valid directory:\n{norm_path}")


    def _max_versions_changed(self):
        """Enables/disables the spinbox based on combo selection."""
        is_custom = self.max_versions_combo.currentText() == "Custom Number"
        self.max_versions_spinbox.setEnabled(is_custom)

    def _handle_preview_scripts(self):
        """Gathers selections and calls data_utils to preview scripts."""
        log.info("Previewing scripts...")
        self.log_output_area.clear()
        self.log_output_area.append("--- Script Preview ---")
        self.status_feedback_label.setText("Previewing...")
        QtWidgets.QApplication.processEvents() # Update UI

        project, episodes, sequences, shots, mode = self._get_current_scope_and_names()

        if not self.current_base_path or not project:
            self.log_output_area.append("Error: Project or Base Path not set.")
            self.status_feedback_label.setText("Preview failed: Project missing")
            return

        # Determine names_to_process based on mode for preview
        names_for_preview = []
        if mode == "project":
            names_for_preview = [] # Handled by mode="project"
        elif mode == "episode":
            names_for_preview = episodes
        elif mode == "sequence":
            names_for_preview = sequences
        elif mode == "shot":
            # For shot mode preview, we need the *full paths* to the shot directories
            # This requires reconstructing them based on the selected project/ep/seq
            names_for_preview = self._get_full_shot_paths(project, episodes, sequences, shots)


        max_versions = 0 # Default to All for preview unless specified?
        if self.max_versions_combo.currentText() == "Latest Only":
            max_versions = 1
        elif self.max_versions_combo.currentText() == "Custom Number":
            max_versions = self.max_versions_spinbox.value()

        try:
            scripts = data_utils.get_nuke_scripts_for_preview(
                base_path=self.current_base_path,
                project_name=project,
                mode=mode,
                names_to_process=names_for_preview, # Pass appropriate list based on mode
                max_versions=max_versions
            )
            if scripts:
                self.log_output_area.append(f"Found {len(scripts)} scripts to process:")
                for script in scripts:
                    self.log_output_area.append(f"  - {script}")
            else:
                self.log_output_area.append("No Nuke scripts found matching the current selection and criteria.")
            self.status_feedback_label.setText("Preview complete.")

        except Exception as e:
            log.error(f"Error during script preview: {e}", exc_info=True)
            self.log_output_area.append(f"\nError during preview:\n{e}")
            self.status_feedback_label.setText("Preview failed.")


    def _handle_execute_archiving(self):
        """Builds command and executes fixarc-handler using QProcess."""
        log.info("Execute button clicked.")
        self.log_output_area.clear()

        # --- Validation ---
        selected_project = self.project_combo.currentText()
        archive_root = self.archive_root_input.text()

        if not selected_project:
            QtWidgets.QMessageBox.warning(self, "Input Missing", "Please select a Project.")
            return
        if not archive_root or not os.path.isdir(archive_root): # Check if dir exists now
            QtWidgets.QMessageBox.warning(self, "Input Missing", "Please specify a valid Archive Root directory.")
            return
        if not self.fixarc_handler_path:
             QtWidgets.QMessageBox.critical(self, "Error", "Cannot execute: 'fixarc-handler' path not found.")
             return

        # --- Determine Mode and Args ---
        project, episodes, sequences, shots, mode = self._get_current_scope_and_names()
        names_for_mode = []
        mode_flag = f"--{mode}"
        if mode == "project":
            names_for_mode = [project] # Handler expects project name for --project mode
            mode_flag = "--project" # Explicitly set for clarity
        elif mode == "episode":
            names_for_mode = episodes
        elif mode == "sequence":
            names_for_mode = sequences
        elif mode == "shot":
            names_for_mode = shots

        # --- Build Command ---
        # Start with handler path and mandatory args
        cmd = ["python", self.fixarc_handler_path] # Assume running via python for now
        # cmd = [self.fixarc_handler_path] # If it's a direct executable/wrapper

        cmd.extend(["--project", project]) # Always provide project context
        cmd.extend([mode_flag] + names_for_mode)
        cmd.extend(["--archive-root", normalize_path(archive_root)])

        # Add optional handler args
        if self.max_versions_combo.currentText() == "Latest Only":
            cmd.extend(["--max-versions", "1"])
        elif self.max_versions_combo.currentText() == "All Versions":
            cmd.extend(["--max-versions", "0"]) # Assuming 0 means all
        elif self.max_versions_combo.currentText() == "Custom Number":
            cmd.extend(["--max-versions", str(self.max_versions_spinbox.value())])

        client_config = self.client_config_input.text()
        if client_config:
            cmd.extend(["--client-config", normalize_path(client_config)])

        if self.farm_check.isChecked():
            cmd.append("--farm")

        verbosity = self.log_verbosity_combo.currentIndex() # 0=Info, 1=Debug
        if verbosity == 1:
            cmd.append("-vv") # Assuming -vv for debug

        # Build --fixarc-options string
        fixarc_opts = self._build_fixarc_options_string()
        if fixarc_opts:
            cmd.extend(["--fixarc-options", fixarc_opts])

        # --- Execute ---
        log.info(f"Executing command: {' '.join(cmd)}")
        self.log_output_area.append(f"Executing: {' '.join(cmd)}\n" + "="*40)
        self.status_feedback_label.setText("Executing...")
        self.execute_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        QtWidgets.QApplication.processEvents() # Update UI

        if self.process is None:
            self.process = QtCore.QProcess(self)
            self.process.setProcessChannelMode(QtCore.QProcess.MergedChannels) # Combine stdout/stderr
            self.process.readyReadStandardOutput.connect(self._handle_stdout)
            # self.process.readyReadStandardError.connect(self._handle_stderr) # Not needed if merged
            self.process.finished.connect(self._process_finished)
            self.process.errorOccurred.connect(self._handle_error) # Handle process errors

        # Start the process
        program = cmd[0]
        arguments = cmd[1:]
        self.process.start(program, arguments)

    # -------------------------------------------------------------------------
    # QProcess Handlers
    # -------------------------------------------------------------------------

    def _handle_stdout(self):
        """Reads stdout from the process and appends to the log area."""
        if not self.process: return
        data = self.process.readAllStandardOutput()
        try:
            text = bytes(data).decode('utf-8', errors='replace')
            self.log_output_area.moveCursor(QtGui.QTextCursor.End)
            self.log_output_area.insertPlainText(text)
            self.log_output_area.moveCursor(QtGui.QTextCursor.End)
        except Exception as e:
            log.error(f"Error decoding process output: {e}")
            self.log_output_area.append(f"\n[Error decoding output: {e}]\n")

    # def _handle_stderr(self): # Not needed if merging channels
    #     """Reads stderr from the process and appends to the log area."""
    #     # ... implementation ...

    def _process_finished(self, exitCode, exitStatus):
        """Handles the process finishing."""
        log.info(f"Process finished. Exit Code: {exitCode}, Status: {exitStatus}")
        self.log_output_area.append("="*40 + f"\nProcess finished with exit code: {exitCode}")

        if exitStatus == QtCore.QProcess.NormalExit and exitCode == 0:
            self.status_feedback_label.setText("Execution successful.")
            QtWidgets.QMessageBox.information(self, "Success", "Archive process completed successfully.")
        else:
            status_text = "crashed" if exitStatus == QtCore.QProcess.CrashExit else f"failed (code {exitCode})"
            self.status_feedback_label.setText(f"Execution {status_text}.")
            QtWidgets.QMessageBox.critical(self, "Execution Failed", f"Archive process {status_text}.\nCheck logs for details.")

        self.execute_button.setEnabled(True)
        self.preview_button.setEnabled(True)
        self.process = None # Allow creating a new one next time

    def _handle_error(self, error):
        """Handles QProcess errors (e.g., command not found)."""
        error_string = self.process.errorString() if self.process else "Unknown QProcess Error"
        log.error(f"QProcess Error occurred: {error} - {error_string}")
        self.log_output_area.append(f"\n--- QPROCESS ERROR ---\n{error_string}\n---------------------\n")
        self.status_feedback_label.setText(f"Process Error: {error_string}")
        QtWidgets.QMessageBox.critical(self, "Process Error", f"Failed to start or run the process:\n{error_string}")

        self.execute_button.setEnabled(True)
        self.preview_button.setEnabled(True)
        self.process = None

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _get_selected_items(self, list_widget: QtWidgets.QListWidget) -> List[str]:
        """Returns a list of text for currently selected items."""
        return [item.text() for item in list_widget.selectedItems()]

    def _update_status_bar(self):
        """Updates the status bar labels."""
        base_path_display = f"Base: {self.current_base_path}" if self.current_base_path else "Base: Not Set"
        self.status_base_path_label.setText(base_path_display)

        # Update shot counts based on *visible* items if filter is active
        visible_count = 0
        total_count = self.shot_list.count()
        for i in range(total_count):
            if not self.shot_list.item(i).isHidden():
                visible_count += 1
        selected_count = len(self._get_selected_items(self.shot_list))
        self.status_shots_label.setText(f"Shots: {selected_count} sel / {visible_count} vis / {total_count} tot")

    def _get_current_scope_and_names(self) -> Tuple[str, List[str], List[str], List[str], str]:
        """Determines the most specific scope selected and returns names."""
        project = self.project_combo.currentText()
        episodes = self._get_selected_items(self.episode_list)
        sequences = self._get_selected_items(self.sequence_list)
        shots = self._get_selected_items(self.shot_list)

        mode = "project"
        if shots: mode = "shot"
        elif sequences: mode = "sequence"
        elif episodes: mode = "episode"

        return project, episodes, sequences, shots, mode

    def _get_full_shot_paths(self, project, episodes, sequences, shot_names) -> List[str]:
        """Constructs full paths to selected shot directories."""
        # This needs careful implementation based on actual structure and selections
        # For simplicity, assume we need *at least* project + episode + sequence selected
        # if we are trying to resolve shot *names* to paths.
        # If 'episodes' or 'sequences' are empty, it implies 'all' in the context of the
        # parent selection, which makes resolving individual shot names ambiguous without
        # iterating the filesystem again here.
        #
        # A better approach for preview/execution might be to always operate on the full paths
        # derived *during* the population phase, but that complicates the UI state management.
        #
        # Let's return an empty list and log a warning if context is insufficient.
        full_paths = []
        if not project or not episodes or not sequences or not self.current_base_path:
             log.warning("Cannot reliably determine full shot paths for preview/execution without Project, Episode, and Sequence context.")
             return []

        # Assume single episode/sequence selection for simplicity here, multi-select complicates path finding
        if len(episodes) != 1 or len(sequences) != 1:
             log.warning("Shot path preview/execution currently assumes single Episode and Sequence selection for context.")
             # Could iterate all combinations, but might be slow/complex
             return []

        base_shot_dir = Path(self.current_base_path) / project / "shots" / episodes[0] / sequences[0]

        for shot_name in shot_names:
            full_paths.append(normalize_path(str(base_shot_dir / shot_name)))

        return full_paths


    def _build_fixarc_options_string(self) -> str:
        """Constructs the string for the --fixarc-options argument."""
        opts = []
        if self.bake_gizmos_check.isChecked():
            opts.append("--bake-gizmos")
        if self.update_paths_check.isChecked():
            opts.append("--update-script") # Corresponds to fixarc's --update-script
        if self.fixarc_dry_run_check.isChecked():
            opts.append("--dry-run") # Corresponds to fixarc's --dry-run

        vendor = self.vendor_name_input.text().strip()
        if vendor and vendor != DEFAULT_VENDOR: # Only add if non-empty and different from default
             opts.extend(["--vendor", f'"{vendor}"']) # Quote if vendor name has spaces

        # Add raw options, splitting by space but respecting quotes
        import shlex
        raw_opts_str = self.raw_fixarc_options_input.text().strip()
        if raw_opts_str:
            try:
                opts.extend(shlex.split(raw_opts_str))
            except ValueError as e:
                log.warning(f"Could not parse raw fixarc options '{raw_opts_str}': {e}")
                QtWidgets.QMessageBox.warning(self, "Parsing Error", f"Could not parse 'Other Options':\n{raw_opts_str}\n\nError: {e}")
                # Optionally clear the input or prevent execution

        return " ".join(opts) # Join with spaces

    def closeEvent(self, event):
        """Ensure process is terminated on window close."""
        if self.process and self.process.state() == QtCore.QProcess.Running:
            log.warning("Terminating active process on window close.")
            self.process.terminate()
            if not self.process.waitForFinished(1000): # Wait 1 sec
                log.warning("Process did not terminate gracefully, killing.")
                self.process.kill()
        event.accept()


# --- Main execution ---
def main_ui():
    """Entry point to launch the UI."""
    # Ensure a QApplication instance exists
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication(sys.argv)

    # Set application style if desired (optional)
    # app.setStyle("Fusion")

    window = FixarcHandlerWindow()
    window.show()

    # Start the event loop only if we created the QApplication instance
    if app is QtWidgets.QApplication.instance():
        sys.exit(app.exec_())
    # Otherwise, assume event loop is managed elsewhere (e.g., Nuke GUI)

if __name__ == '__main__':
    # This allows running the UI directly for testing
    main_ui()