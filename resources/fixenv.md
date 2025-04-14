# __init__.py

```py
from .constants import (
    OS, OS_WIN, OS_LIN, OS_MAC,
    BIN_DIR, PIPE_DIR, PYENV_DIR, CONFIG_DIR, ENV_DIR, CONFIG_FILE,
    STUDIO_TOOLS_DIR, RELEASES_DIR, NUKE_DIR, DEV_DIR, MAIN_DIR,
    STORAGE_SERVER, FIXSTORE_UNC, FIXSECURE_UNC, FIXPOOL_UNC,
    FIXSTORE_WIN_SERVER, FIXSTORE_WIN_DRIVE,
    FIXSECURE_WIN_SERVER, FIXSECURE_WIN_DRIVE,
    FIXPOOL_WIN_SERVER, FIXPOOL_WIN_DRIVE,
    FIXSTORE_LIN_SERVER, FIXSTORE_LIN_DRIVE,
    FIXSECURE_LIN_SERVER, FIXSECURE_LIN_DRIVE,
    FIXPOOL_LIN_SERVER, FIXPOOL_LIN_DRIVE,
    FIXSTORE_MAC_MNT, FIXSTORE_MAC_DRIVE,
    FIXSECURE_MAC_DRIVE, FIXPOOL_MAC_DRIVE,
    GIT_HOSTNAME, GIT_ORGANIZATION, GIT_URL,
    DRIVE_MAP, SERVER_DRIVE_MAP,
    FIXSTORE_DRIVE, FIXSECURE_DRIVE, FIXPOOL_DRIVE,
    PIPE_PATH, STUDIO_TOOLS_PATH, CONFIG_PATH,
    PYENV_WIN_PATH, NUKE_DEV_PATH, NUKE_MAIN_PATH,
    PYENV_OS_MAP,
    PYENV_PATH,
    PYENV_BIN_PATH,
    PYENV_VERSIONS_PATH,
    PYENV_VERSION_PATH,
    PYENV_LIB_PATH,
    PYENV_SITE_PACKAGES_PATH,
    PYTHON_VERSION,
    PYENV_LIB_DIR,
    PYENV_SITE_PACKAGES_DIR,
    PYENV_VERSIONS_DIR,
    PYENV_LIN_DIR,
    PYENV_WIN_DIR,
    PYENV_WIN_BIN_PATH,
    PYENV_WIN_VERSIONS_PATH,
    PYENV_WIN_VERSION_PATH,
    PYENV_WIN_LIB_PATH,
    PYENV_WIN_SITE_PACKAGES_PATH,
    PYENV_LIN_BIN_PATH,
    PYENV_LIN_VERSIONS_PATH,
    PYENV_LIN_VERSION_PATH,
    PYENV_LIN_LIB_PATH,
    PYENV_LIN_SITE_PACKAGES_PATH
)

from .core import (
    load, save, normalize_path, set_env_var, append_to_env_var, update_studio_environment,
    update_config, get_pipe_path, get_releases_path, get_releases, update_package_list,
    sanitize_path, unc_to_win_drive, win_to_lin_drive, lin_to_win_drive,
    get_pipe_projects, get_pipe_projects_version, print_pipe_versions, get_package_path
)

__all__ = [
    # Constants
    'OS', 'OS_WIN', 'OS_LIN', 'OS_MAC',
    'BIN_DIR', 'PIPE_DIR', 'PYENV_DIR', 'CONFIG_DIR', 'ENV_DIR', 'CONFIG_FILE',
    'STUDIO_TOOLS_DIR', 'RELEASES_DIR', 'NUKE_DIR', 'DEV_DIR', 'MAIN_DIR',
    'STORAGE_SERVER', 'FIXSTORE_UNC', 'FIXSECURE_UNC', 'FIXPOOL_UNC',
    'FIXSTORE_WIN_SERVER', 'FIXSTORE_WIN_DRIVE',
    'FIXSECURE_WIN_SERVER', 'FIXSECURE_WIN_DRIVE',
    'FIXPOOL_WIN_SERVER', 'FIXPOOL_WIN_DRIVE',
    'FIXSTORE_LIN_SERVER', 'FIXSTORE_LIN_DRIVE',
    'FIXSECURE_LIN_SERVER', 'FIXSECURE_LIN_DRIVE',
    'FIXPOOL_LIN_SERVER', 'FIXPOOL_LIN_DRIVE',
    'FIXSTORE_MAC_MNT', 'FIXSTORE_MAC_DRIVE',
    'FIXSECURE_MAC_DRIVE', 'FIXPOOL_MAC_DRIVE',
    'GIT_HOSTNAME', 'GIT_ORGANIZATION', 'GIT_URL',
    'DRIVE_MAP', 'SERVER_DRIVE_MAP',
    'FIXSTORE_DRIVE', 'FIXSECURE_DRIVE', 'FIXPOOL_DRIVE',
    'PIPE_PATH', 'STUDIO_TOOLS_PATH', 'CONFIG_PATH',
    'PYENV_WIN_PATH', 'NUKE_DEV_PATH', 'NUKE_MAIN_PATH',
    'PYENV_OS_MAP',
    'PYENV_PATH',
    'PYENV_BIN_PATH',
    'PYENV_VERSIONS_PATH',
    'PYENV_VERSION_PATH',
    'PYENV_LIB_PATH',
    'PYENV_SITE_PACKAGES_PATH',
    'PYTHON_VERSION',
    'PYENV_LIB_DIR',
    'PYENV_SITE_PACKAGES_DIR',
    'PYENV_VERSIONS_DIR',
    'PYENV_LIN_DIR',
    'PYENV_WIN_DIR',
    'PYENV_WIN_BIN_PATH',
    'PYENV_WIN_VERSIONS_PATH',
    'PYENV_WIN_VERSION_PATH',
    'PYENV_WIN_LIB_PATH',
    'PYENV_WIN_SITE_PACKAGES_PATH',
    'PYENV_LIN_BIN_PATH',
    'PYENV_LIN_VERSIONS_PATH',
    'PYENV_LIN_VERSION_PATH',
    'PYENV_LIN_LIB_PATH',
    'PYENV_LIN_SITE_PACKAGES_PATH',
    
    # Core functions
    'load', 'save', 'normalize_path',
    'set_env_var', 'append_to_env_var', 'update_studio_environment', 'update_package_list',
    'update_config', 'get_pipe_path', 'get_releases_path', 'get_releases',
    'sanitize_path', 'unc_to_win_drive', 'win_to_lin_drive', 'lin_to_win_drive',
    'get_pipe_projects', 'get_pipe_projects_version', 'print_pipe_versions', 'get_package_path'
]
```

# constants.py

```py
from pathlib import Path
import platform
import sys

# =======================================================================================================================================================
# GLOBAL CONSTANTS
# =======================================================================================================================================================

# Python Version
PYTHON_VERSION                  = sys.version.split()[0]                                            # Current default 3.10.11

# Operating System
OS                              = platform.system()                                                 # Get the OS name for the current session
OS_WIN                          = "Windows"                                                         # platform constant
OS_LIN                          = "Linux"                                                           # platform constant
OS_MAC                          = "Darwin"                                                          # platform constant

# Studio File Naming Conventions
BIN_DIR                         = "bin"                                                             # used to store executables or binary files.
CONFIG_DIR                      = ".config"                                                         # hidden folder for various configs
CONFIG_FILE                     = "studio_config.json"                                              #   Z:/pipe/.config/env/studio_config.json
ENV_DIR                         = "env"                                                             #   studio env configs directory
PIPE_DIR                        = "pipe"                                                            # pipeline code directory
PYENV_DIR                       = ".pyenv"                                                          # site-wide python environment directory                                                                                                    # Config
PYENV_LIB_DIR                   = "Lib"
PYENV_SITE_PACKAGES_DIR         = "site-packages"
PYENV_VERSIONS_DIR              = "versions"
PYENV_LIN_DIR                   = "pyenv-lin"                                                       # pyenv-lin directory
PYENV_WIN_DIR                   = "pyenv-win"                                                       # pyenv-win directory
RELEASES_DIR                    = "releases"                                                        # releases directory
STUDIO_TOOLS_DIR                = "Fixfx"                                                           # fixfx repo - pipeline and workflow management

NUKE_DIR                        = "Nuke"                                                            # Nuke repo directory
DEV_DIR                         = "dev"                                                             # dev directory
MAIN_DIR                        = "main"                                                            # main directory

# Network Storage and Universal Naming Convention
STORAGE_SERVER                  = "192.168.14.252"                                                  # Storage IP address
FIXSTORE_UNC                    = "FixStore"                                                        # Studio main storage naming convention
FIXSECURE_UNC                   = "FixSecure"                                                       # Studio secure storage naming convention
FIXPOOL_UNC                     = "FixPool"                                                         # Studio secondary storage naming convention

# Windows Storage Drive Names
FIXSTORE_WIN_SERVER             = f"\\\\{STORAGE_SERVER}\\{FIXSTORE_UNC}"                           # FixStore Drive  | Z: | Default Storage
FIXSTORE_WIN_DRIVE              = "Z:\\"                                                              # Z: Drive Letter

FIXSECURE_WIN_SERVER            = f"\\\\{STORAGE_SERVER}\\{FIXSECURE_UNC}"                          # FixSecure Drive | X: | FixStore w/ extra security
FIXSECURE_WIN_DRIVE             = "X:\\"                                                              # X: Drive Letter

FIXPOOL_WIN_SERVER              = f"\\\\{STORAGE_SERVER}\\{FIXPOOL_UNC}"                            # FixPool Drive   | Y: | Archive (Z: backup)
FIXPOOL_WIN_DRIVE               = "Y:\\"                                                              # Y: Drive Letter

# Linux Storage Drive Names (as SERVER variables)
FIXSTORE_LIN_SERVER             = f"/mnt/{FIXSTORE_UNC}"                                            # FixStore Drive in Linux style
FIXSTORE_LIN_DRIVE              = "/z/"                                                               # Linux-style drive letter for FixStore
FIXSECURE_LIN_SERVER            = f"/mnt/{FIXSECURE_UNC}"                                           # FixSecure Drive in Linux style
FIXSECURE_LIN_DRIVE             = "/x/"                                                               # Linux-style drive letter for FixSecure
FIXPOOL_LIN_SERVER              = f"/mnt/{FIXPOOL_UNC}"                                             # FixPool Drive in Linux style
FIXPOOL_LIN_DRIVE               = "/y/"                                                               # Linux-style drive letter for FixPool

# Mac Storage Drive Mounts (assuming similar to Linux)
FIXSTORE_MAC_MNT                = f"/Volumes/{FIXSTORE_UNC}"                                        # Mac Storage Mount Point (TODO)
FIXSTORE_MAC_DRIVE              = f"{FIXSTORE_MAC_MNT}/{FIXSTORE_UNC}"                              # FixStore Drive (TODO)
FIXSECURE_MAC_DRIVE             = f"{FIXSTORE_MAC_MNT}/{FIXSECURE_UNC}"                             # FixSecure Drive (TODO)
FIXPOOL_MAC_DRIVE               = f"{FIXSTORE_MAC_MNT}/{FIXPOOL_UNC}"                               # FixPool Drive (TODO)

GIT_HOSTNAME                    = "github.com"                                                      # Git hostname
GIT_ORGANIZATION                = "fixfx-uk"                                                        # Git Organization
GIT_URL                         = f"https://{GIT_HOSTNAME}/{GIT_ORGANIZATION}"                      # Git repos https URL

# OS Agnostic Naming Conventions
DRIVE_MAP                       = {OS_WIN:
                                    (FIXSTORE_WIN_DRIVE, FIXSECURE_WIN_DRIVE, FIXPOOL_WIN_DRIVE),   # Z:, X:, Y:
                                   OS_LIN:
                                    (FIXSTORE_LIN_DRIVE, FIXSECURE_LIN_DRIVE, FIXPOOL_LIN_DRIVE),   # /mnt/FixStore/FixStore
                                   OS_MAC:
                                    (FIXSTORE_MAC_DRIVE, FIXSECURE_MAC_DRIVE, FIXPOOL_MAC_DRIVE),   # /Volume/FixStore/FixStore
                                   }

# =======================================================================================================================================================
# SERVER TO DRIVE MAPPING
# =======================================================================================================================================================
# Dictionary mapping UNC server paths to drive letters
SERVER_DRIVE_MAP                = {FIXSTORE_WIN_SERVER: FIXSTORE_WIN_DRIVE.rstrip("\\"),            # \\192.168.14.252\\FixStore    : Z:
                                   FIXSECURE_WIN_SERVER: FIXSECURE_WIN_DRIVE.rstrip("\\"),          # \\192.168.14.252\\FixSecure   : Z:
                                   FIXPOOL_WIN_SERVER: FIXPOOL_WIN_DRIVE.rstrip("\\")               # \\192.168.14.252\\FixPool     : Z:
                                   }

# =======================================================================================================================================================
# CURRENT SESSION CONSTANTS
# =======================================================================================================================================================

# Drives
FIXSTORE_DRIVE                  = DRIVE_MAP.get(OS, DRIVE_MAP[OS_LIN])[0]                           # Resolved storage name for current OS
FIXSECURE_DRIVE                 = DRIVE_MAP.get(OS, DRIVE_MAP[OS_LIN])[1]                           # Resolved storage name for current OS
FIXPOOL_DRIVE                   = DRIVE_MAP.get(OS, DRIVE_MAP[OS_LIN])[2]                           # Resolved storage name for current OS

# Core Paths
PIPE_PATH                       = Path(FIXSTORE_DRIVE) / PIPE_DIR                                   # Z:/pipe

# Core Paths
STUDIO_TOOLS_PATH               = PIPE_PATH / STUDIO_TOOLS_DIR                                      # Z:/pipe/Fixfx

# Full Paths
CONFIG_PATH                     = PIPE_PATH / CONFIG_DIR / ENV_DIR / CONFIG_FILE                    # Z:/pipe/.config/env/studio_config.json

# Windows Python Environment Paths
PYENV_WIN_PATH                  = PIPE_PATH / PYENV_DIR / PYENV_WIN_DIR                             # Z:/pipe/.pyenv/pyenv-win
PYENV_WIN_BIN_PATH              = PYENV_WIN_PATH / BIN_DIR                                          # Z:/pipe/.pyenv/bin
PYENV_WIN_VERSIONS_PATH         = PYENV_WIN_PATH / PYENV_VERSIONS_DIR                               # Z:/pipe/.pyenv/pyenv-win/versions
PYENV_WIN_VERSION_PATH          = PYENV_WIN_VERSIONS_PATH / PYTHON_VERSION                          # Z:/pipe/.pyenv/pyenv-win/versions/3.9.1
PYENV_WIN_LIB_PATH              = PYENV_WIN_VERSION_PATH / PYENV_LIB_DIR                            # Z:/pipe/.pyenv/pyenv-win/versions/3.9.1/Lib
PYENV_WIN_SITE_PACKAGES_PATH    = PYENV_WIN_LIB_PATH / PYENV_SITE_PACKAGES_DIR                      # Z:/pipe/.pyenv/pyenv-win/versions/3.9.1/Lib/site-packages

# Linux Python Environment Paths
PYENV_LIN_PATH                  = PIPE_PATH / PYENV_DIR / PYENV_LIN_DIR                             # Z:/pipe/.pyenv/pyenv-lin
PYENV_LIN_BIN_PATH              = PYENV_LIN_PATH / BIN_DIR                                          # Z:/pipe/.pyenv/pyenv-lin/bin
PYENV_LIN_VERSIONS_PATH         = PYENV_LIN_PATH / PYENV_VERSIONS_DIR                               # Z:/pipe/.pyenv/pyenv-lin/versions
PYENV_LIN_VERSION_PATH          = PYENV_LIN_VERSIONS_PATH / PYTHON_VERSION                          # Z:/pipe/.pyenv/pyenv-lin/versions/3.9.1
PYENV_LIN_LIB_PATH              = PYENV_LIN_VERSION_PATH / PYENV_LIB_DIR                            # Z:/pipe/.pyenv/pyenv-lin/versions/3.9.1/Lib
PYENV_LIN_SITE_PACKAGES_PATH    = PYENV_LIN_LIB_PATH / PYENV_SITE_PACKAGES_DIR                      # Z:/pipe/.pyenv/pyenv-lin/versions/3.9.1/Lib/site-packages    

# Nuke
NUKE_DEV_PATH                   = PIPE_PATH / NUKE_DIR / DEV_DIR                                    # Z:/pipe/Nuke/dev
NUKE_MAIN_PATH                  = PIPE_PATH / NUKE_DIR / MAIN_DIR                                   # Z:/pipe/Nuke/main

# OS Agnostic Python Environment Paths
PYENV_OS_MAP                    = {OS_WIN: (PYENV_WIN_PATH,                                         # PYENV_PATH
                                            PYENV_WIN_BIN_PATH,                                     # PYENV_BIN_PATH
                                            PYENV_WIN_VERSIONS_PATH,                                # PYENV_VERSIONS_PATH
                                            PYENV_WIN_VERSION_PATH,                                 # PYENV_VERSION_PATH
                                            PYENV_WIN_LIB_PATH,                                     # PYENV_LIB_PATH
                                            PYENV_WIN_SITE_PACKAGES_PATH                            # PYENV_SITE_PACKAGES_PATH
                                           ),
                                   OS_LIN: (PYENV_LIN_PATH,                                         # PYENV_PATH
                                            PYENV_LIN_BIN_PATH,                                     # PYENV_BIN_PATH
                                            PYENV_LIN_VERSIONS_PATH,                                # PYENV_VERSIONS_PATH
                                            PYENV_LIN_VERSION_PATH,                                 # PYENV_VERSION_PATH
                                            PYENV_LIN_LIB_PATH,                                     # PYENV_LIB_PATH
                                            PYENV_LIN_SITE_PACKAGES_PATH                            # PYENV_SITE_PACKAGES_PATH
                                           ),
                                   OS_MAC: (PYENV_LIN_PATH,                                         # PYENV_PATH
                                            PYENV_LIN_BIN_PATH,                                     # PYENV_BIN_PATH
                                            PYENV_LIN_VERSIONS_PATH,                                # PYENV_VERSIONS_PATH
                                            PYENV_LIN_VERSION_PATH,                                 # PYENV_VERSION_PATH
                                            PYENV_LIN_LIB_PATH,                                     # PYENV_LIB_PATH
                                            PYENV_LIN_SITE_PACKAGES_PATH                            # PYENV_SITE_PACKAGES_PATH
                                           )  # Using Linux paths for Mac for now
                                  }

# Current Session Python Environment Paths
PYENV_PATH                      = PYENV_OS_MAP.get(OS, PYENV_OS_MAP[OS_LIN])[0]
PYENV_BIN_PATH                  = PYENV_OS_MAP.get(OS, PYENV_OS_MAP[OS_LIN])[1]
PYENV_VERSIONS_PATH             = PYENV_OS_MAP.get(OS, PYENV_OS_MAP[OS_LIN])[2]
PYENV_VERSION_PATH              = PYENV_OS_MAP.get(OS, PYENV_OS_MAP[OS_LIN])[3]
PYENV_LIB_PATH                  = PYENV_OS_MAP.get(OS, PYENV_OS_MAP[OS_LIN])[4]
PYENV_SITE_PACKAGES_PATH        = PYENV_OS_MAP.get(OS, PYENV_OS_MAP[OS_LIN])[5]


```

# core.py

```py
import os
import json
from typing import Dict, List, Optional, Union
from pathlib import Path

from deployment.metadata import get_project_version
from fixenv import PIPE_PATH
from .constants import CONFIG_PATH, PIPE_PATH, RELEASES_DIR, SERVER_DRIVE_MAP, OS, OS_WIN, OS_LIN, OS_MAC, FIXSTORE_LIN_DRIVE
from .logger import get_logger
# Initialize package-level logger
log = get_logger(__name__)

# Cached configuration and timestamp
_cached_config = None
_config_timestamp = 0

def load() -> Dict[str, Union[str, List[str]]]:
    """Loads the studio environment configuration from the JSON file with caching.

    The function implements a caching mechanism where the configuration is stored in memory
    and only reloaded if the config file has been modified (detected via timestamp comparison).
    This optimizes performance by reducing disk I/O operations.

    Returns:
        Dict[str, Union[str, List[str]]]: The loaded configuration data or an empty dictionary on error.
    """
    global _cached_config, _config_timestamp
    log.debug(__name__)
    try:
        current_timestamp = CONFIG_PATH.stat().st_mtime
        if _cached_config is None or _config_timestamp != current_timestamp:
            with open(CONFIG_PATH, "r") as f:
                _cached_config = json.load(f)
            _config_timestamp = current_timestamp
        return _cached_config
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading config: {e}")
        return {}

def save(config: Dict[str, Union[str, List[str]]]) -> None:
    """Saves the given configuration to the JSON file using forward slashes for paths.

    Args:
        config (Dict[str, Union[str, List[str]]]): The configuration data to save.
    """
    try:
        for key, value in config.items():
            if isinstance(value, list):
                config[key] = [normalize_path(path) for path in value]
            elif isinstance(value, str):
                config[key] = normalize_path(value)

        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")

def sanitize_path(path: Union[str, Path]) -> str:
    """Return a sanitized absolute path for the current OS.

    - Replaces UNC paths with drive letters (on Windows only).
    - Ensures the correct slash style is used when comparing UNC.
    - Resolves the path to an absolute system-native path.

    Args:
        path (Union[str, Path]): Input file or directory path.

    Returns:
        str: Sanitized absolute path.
    """
    # Convert to string and normalize slashes for the current OS
    path_str = str(path)

    # Normalize slashes based on the OS
    if OS == OS_WIN:
        path_str = path_str.replace('/', '\\')  # Use backslashes for Windows
        path_str = unc_to_win_drive(path_str)
        path_str = lin_to_win_drive(path_str)
    else:  # For Linux and macOS
        path_str = path_str.replace('\\', '/')  # Use forward slashes
        path_str = win_to_lin_drive(path_str)

    # Resolve the path to an absolute path
    return os.path.abspath(path_str)

def unc_to_win_drive(path_str: str) -> str:
    """Replace UNC paths with drive letters for Windows.

    Args:
        path_str (str): The path string to process.

    Returns:
        str: The path string with UNC paths replaced by drive letters.
    """
    for unc, drive in SERVER_DRIVE_MAP.items():
        normalized_unc = unc.replace('/', '\\')
        if path_str.startswith(normalized_unc):
            return path_str.replace(normalized_unc, drive, 1)
    return path_str

def win_to_lin_drive(path_str: str) -> str:
    """Convert Windows drive letters to Linux-style paths.

    Args:
        path_str (str): The path string to process.

    Returns:
        str: The path string with Windows drive letters replaced by Linux-style paths.
    """
    for unc, drive in SERVER_DRIVE_MAP.items():
        if path_str.startswith(drive):
            return path_str.replace(drive, FIXSTORE_LIN_DRIVE, 1)
    return path_str

def lin_to_win_drive(path_str: str) -> str:
    """Convert Linux-style paths to Windows drive letters.

    Args:
        path_str (str): The path string to process.

    Returns:
        str: The path string with Linux-style paths replaced by Windows drive letters.
    """
    for unc, drive in SERVER_DRIVE_MAP.items():
        if path_str.startswith(FIXSTORE_LIN_DRIVE):
            return path_str.replace(FIXSTORE_LIN_DRIVE, drive, 1)
    return path_str

def normalize_path(path: Union[str, Path]) -> str:
    """Return a forward-slashed version of the sanitized path.

    Args:
        path (Union[str, Path]): The input path.

    Returns:
        str: Path with forward slashes, usable across platforms.
    """
    # Directly normalize the path without calling sanitize_path
    path_str = str(path)
    if OS == OS_WIN:
        path_str = path_str.replace('\\', '/')
    return path_str

def update_package_list(config_list: List[str], release_path: str, new_package: str) -> List[str]:
    """Replaces a path in the list that starts with release_path or appends new_package if no match."""
    updated = []
    replaced = False
    for path in config_list:
        if normalize_path(path).startswith(release_path):
            updated.append(new_package)
            replaced = True
        else:
            updated.append(path)
    if not replaced:
        updated.append(new_package)
    return updated

def set_env_var(key: str, value: str) -> None:
    """Sets an environment variable.

    Args:
        key (str): The environment variable name.
        value (str): The value to assign.
    """
    # Use normalize_path directly to avoid recursion
    normalized_path = normalize_path(value)
    log.debug(f"Setting environment variable: {key} = {normalized_path}")
    os.environ[key] = normalized_path


def append_to_env_var(key: str, values: Union[str, List[str]], prepend: bool = True) -> None:
    """Appends one or more values to an environment variable, preventing duplicates.

    Args:
        key (str): The environment variable name.
        values (Union[str, List[str]]): The value(s) to append.
        prepend (bool): Whether to prepend the value(s) instead of appending. Defaults to True.
    """
    log.debug(f"Appending to environment variable: {key}, Values: {values}, Prepend: {prepend}")
    if isinstance(values, str):
        values = [values]

    normalized_values = [normalize_path(value) for value in values]

    current = os.environ.get(key, "")
    parts = [normalize_path(part) for part in current.split(os.pathsep) if part]

    for value in normalized_values:
        if value not in parts:
            if prepend:
                parts.insert(0, value)
            else:
                parts.append(value)

    log.debug(f"os.environ[{key}] = {os.pathsep.join(parts)}")

    os.environ[key] = os.pathsep.join(parts)

def update_studio_environment() -> None:
    """Primary entry point to update studio environment variables."""
    config = load()
    log.debug(f"{config}")
    for key, value in config.items():
        log.debug(f"{key} = {value}")
        if isinstance(value, list):
            append_to_env_var(key, value, prepend=True)
        else:
            set_env_var(key, value)

def update_config(key: str, value: Union[str, List[str]], package_name: str = None) -> None:
    """Adds or updates an entry in the configuration file and updates the environment.

    Args:
        key (str): The environment variable name.
        value (Union[str, List[str]]): The value to assign.
        package_name (str, optional): Name of the package to update in PYTHONPATH. Defaults to None.
    """
    # Load the config
    config = load()
    log.debug(f"Loaded config: {config}")

    # Normalize the input value
    normalized_value = normalize_path(value) if isinstance(value, str) else [normalize_path(v) for v in value]
    log.debug(f"Normalized value: {normalized_value}")

    # Ensure normalized_value is a list
    if not isinstance(normalized_value, list):
        normalized_value = [normalized_value]

    # Handle PYTHONPATH updates for a specific package
    if key == "PYTHONPATH" and package_name:
        log.debug(f"Updating PYTHONPATH for package: {package_name}")

        # Get the normalized release path for the package
        current_release_path = normalize_path(get_releases_path(package_name))
        log.debug(f"Current release path: {current_release_path}")

        # Initialize PYTHONPATH if it doesn't exist
        if key not in config or not isinstance(config[key], list):
            config[key] = []

        config[key] = update_package_list(config[key], current_release_path, normalized_value[0])
        log.debug(f"Updated PYTHONPATH: {config[key]}")

    else:
        # For non-PYTHONPATH keys, simply update the value
        config[key] = normalized_value if isinstance(value, list) else normalized_value[0]
        log.debug(f"Updated config: {config}")

    # Save the updated config
    save(config)
    log.debug("Saved config to file")

    # Update the environment variable
    if isinstance(config[key], list):
        joined_value = os.pathsep.join(config[key])
        set_env_var(key, joined_value)
    else:
        set_env_var(key, config[key])

def get_pipe_path(project_name: str) -> Path:
    """Return the project directory path.

    Args:
        project_name (str): Name of the project.

    Returns:
        Path: The absolute path to the project directory with a capitalized folder name.
    """
    return PIPE_PATH / project_name.capitalize()

def get_releases_path(project_name: str) -> Path:
    """Return the releases directory path for a given project.

    Args:
        project_name (str): Name of the project.

    Returns:
        Path: The absolute path to the project's releases directory.
    """
    return get_pipe_path(project_name) / RELEASES_DIR

def get_releases(project_name: str, fullpath: bool = False) -> List[Union[str, Path]]:
    """Return the version folders of currently available releases for a given project.

    Args:
        project_name (str): Name of the project.
        fullpath (bool): If True, return the full paths to the version folders. Defaults to False.

    Returns:
        List[Union[str, Path]]: The list of version folder names or full paths.
    """
    releases_path = get_releases_path(project_name)
    version_folders = os.listdir(releases_path)

    if fullpath:
        # return the complete file path
        return [releases_path / folder for folder in version_folders]

    # Otherwise, just return the list of versions
    return version_folders


def get_pipe_projects(pipe_path: Path = PIPE_PATH) -> List[str]:
    """List all projects in the PIPE_PATH that follow the convention PIPE_PATH/{Project}/{project}.json
    where {project} is the lowercase version of {Project}.

    Args:
        pipe_path (Path): The path to the directory containing project directories.

    Returns:
        List[str]: A list of project names.
    """
    projects = []
    # Look for immediate subdirectories in PIPE_PATH
    for project_dir in pipe_path.iterdir():
        if not project_dir.is_dir():
            continue

        # Check if project_dir/{project_dir.name.lower()}.json exists
        json_file = project_dir / f"{project_dir.name.lower()}.json"
        if json_file.is_file():
            projects.append(project_dir.name)

    return projects


def get_pipe_projects_version(pipe_path: Path = PIPE_PATH) -> Dict[str, str]:
    """Get a dictionary of project names and their current versions.

    Args:
        pipe_path (Path): The path to the directory containing project metadata files.

    Returns:
        Dict[str, str]: A dictionary of project names and their versions.
    """
    projects = get_pipe_projects(pipe_path)
    versions = {}
    for project in projects:
        versions[project] = get_project_version(project)
    return versions


def print_pipe_versions(pipe_path: Path = PIPE_PATH) -> None:
    """Print the project names and their current versions.

    Args:
        pipe_path (Path): The path to the directory containing project metadata files.
    """
    versions = get_pipe_projects_version(pipe_path)
    for project, version in versions.items():
        print(f"{project}: {version}")


def get_package_path(project: str, version: Optional[str] = None) -> Path:
    """Get the package release path for a specific version of a project.

    Args:
        project (str): The name of the project.
        version (Optional[str]): The version to get the path for. If None, uses current version.

    Returns:
        Path: The path to the released package version
    """
    if version is None:
        version = get_project_version(project)
    return get_releases_path(project) / version / project.lower()

```

# logger.py

```py
"""Enhanced logging utilities for the FixFX pipeline.

Provides a standardized logger with dynamic log file paths based
on the calling package for improved log organization.

Example:
    from fixfx.core.logger import get_logger

    log = get_logger(__name__)
    log.info("This is a sample log entry.")
"""

import logging
import os
import sys
import inspect
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Constants
LOG_ROOT = "Z:/pipe/.logs"
LOG_FORMAT = '[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

class CustomFormatter(logging.Formatter):
    """Custom formatter for console logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Formats log messages without color coding."""
        log_message = super().format(record)
        return log_message

def _get_calling_package() -> str:
    """Dynamically identifies the calling package/module for logging."""
    stack = inspect.stack()
    for frame in stack:
        module = inspect.getmodule(frame[0])
        if module and module.__name__ != __name__:
            parts = module.__name__.split('.')
            return parts[0] if parts else 'unknown'  # Extract top-level package name
    return 'unknown'

def get_logger(name: str, log_level: int = logging.DEBUG) -> logging.Logger:
    """Configures and returns a logger for FixFX tools with dynamic log paths.

    Args:
        name: The name of the logger, typically `__name__`.
        log_level: The logging level (default: `logging.DEBUG`).

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    if logger.hasHandlers():  # Prevent duplicate handlers
        return logger

    logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(CustomFormatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(console_handler)

    # Dynamic log file path
    package_name = _get_calling_package()
    datestamp = datetime.now().strftime('%Y%m%d')
    log_dir = os.path.join(LOG_ROOT, package_name)
    log_file = os.path.join(log_dir, f"{datestamp}_{name.replace('.', '_')}.log")

    # Ensure log directory exists
    os.makedirs(log_dir, exist_ok=True)

    # File handler with rotation
    file_handler = RotatingFileHandler(log_file, maxBytes=2 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    logger.addHandler(file_handler)

    return logger

```

# README.md

```md
# FixEnv

**FixEnv** is a lightweight, cross-platform environment configuration tool used by the FixFX pipeline. It provides a centralized, scriptable way to manage studio environment variables consistently across Windows, Linux, and macOS.

---

## Features

✅ Dynamic config loading via `studio_config.json`  
✅ Efficient in-memory caching for reduced disk I/O  
✅ Automatic UNC-to-drive path normalization  
✅ Smart env var updating and duplicate-safe path prepending  
✅ Platform-aware constants and paths (Windows, Linux, macOS)  
✅ Prebuilt CLI wrappers: `fixe.sh`, `fixe.bat`, `fixe.ps1`  
✅ Easily integrated into `.pyenv`-managed environments  

---

## Installation

### Editable Install for Dev Workflow
\`\`\`bash
pip install -e Z:/pipe/fixenv
\`\`\`

### Add Wrapper Scripts to `.pyenv`
This adds `fixe.sh`, `fixe.bat`, and `fixe.ps1` to your local bin directory:

\`\`\`python
from fixenv import PYENV_BIN_PATH
from fixenv.core import install_wrapper_scripts

install_wrapper_scripts(PYENV_BIN_PATH)
\`\`\`

---

## Usage

### Python API

**Load and apply environment:**
\`\`\`python
import fixenv
fixenv.update_studio_environment()
\`\`\`

**Add or modify variables:**
\`\`\`python
fixenv.update_config("PYTHONPATH", ["Z:/pipe/scripts", "Z:/pipe/Deadline"])
\`\`\`

### CLI (All Platforms)

\`\`\`bash
fixe  # invokes set_studio_env.py via wrapper
\`\`\`

Or directly:
\`\`\`bash
python -m fixenv.set_studio_env
\`\`\`

---

## Config File

All environment variables are stored in:

\`\`\`
Z:/pipe/.config/env/studio_config.json
\`\`\`

Example:
\`\`\`json
{
  "PATH": [
    "Z:/pipe/bin",
    "Z:/pipe/tools"
  ],
  "PYTHONPATH": [
    "Z:/pipe/python",
    "Z:/pipe/lib"
  ]
}
\`\`\`

---

## Development Layout

\`\`\`
fixenv/
├── bin/
│   ├── fixe.sh           # Bash wrapper for CLI
│   ├── fixe.bat          # Batch wrapper for CLI
│   ├── fixe.ps1          # PowerShell wrapper for CLI
│   └── set_studio_env.py # CLI script to update environment
├── constants.py          # All global and platform-specific paths
├── core.py               # Core logic for loading, saving, updating env
├── logger.py             # Styled, rotating log system
├── __init__.py           # Exposes main API and constants
├── .gitignore
└── README.md
\`\`\`

---

## Path Conventions

- Use **forward slashes** in JSON (`/`)
- Variables ending with `_PATH`, `_DIR`, `_FILE` follow naming best practices
- Automatically converts UNC paths to mapped drives if applicable

---

## Logging

Logs are written to:
\`\`\`
Z:/pipe/.logs/<module>/<timestamped_log>.log
\`\`\`

```

