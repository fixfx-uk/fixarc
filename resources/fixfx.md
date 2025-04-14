# __init__.py

```py
from .core.logger import get_logger
from .core.exceptions import (
    FixFXException,
    FixEnvException,
    FixDataException,
    FixDeploymentException,
    FixGitException,
    FixConfigException,
    FixNetworkException,
    FixValidationException
)

# Initialize package-level logger
log = get_logger(__name__)

__all__ = [
    # Logger
    'log', 'get_logger',
    
    # Exceptions
    'FixFXException',
    'FixEnvException',
    'FixDataException',
    'FixDeploymentException',
    'FixGitException',
    'FixConfigException',
    'FixNetworkException',
    'FixValidationException'
]
```

# core\__init__.py

```py
from fixfx.core.logger import get_logger

# Initialize package-level logger
log = get_logger(__name__)

# Automatically generate __all__ by filtering for public symbols (not starting with "_")
__all__ = ["log"]+[
    name for name in dir()
    if not name.startswith("_")  # Ignore internal/private names
    and name not in ["os", "Path"]  # Ignore unwanted imports
]
```

# core\exceptions.py

```py
"""Custom exception classes for the FixFX pipeline.

Provides structured error handling with automatic logging
for improved debugging and consistency.

Example:
    from fixfx.core.exceptions import FixEnvException

    raise FixEnvException("Failed to load FIXENV variables.")
"""

from fixfx.core import log


class FixFXException(Exception):
    """Base class for all FixFX exceptions with automatic logging."""
    def __init__(self, message: str, *args: object) -> None:
        super().__init__(message, *args)
        log.error(f"{self.__class__.__name__}: {message}")

class FixEnvException(FixFXException):
    """Exception for FixFX environment-related issues."""
    pass

class FixDataException(FixFXException):
    """Exception for FixFX data-related issues."""
    pass

class FixDeploymentException(FixFXException):
    """Exception for FixFX deployment-related issues."""
    pass

class FixGitException(FixFXException):
    """Exception for FixFX Git-related issues."""
    pass

class FixConfigException(FixFXException):
    """Exception for FixFX configuration issues."""
    pass

class FixNetworkException(FixFXException):
    """Exception for network-related issues in FixFX."""
    pass

class FixValidationException(FixFXException):
    """Exception for data validation errors in FixFX."""
    pass

```

# core\logger.py

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
    """Custom formatter with color-coded output for console logs."""

    COLORS = {
        'DEBUG': '\033[94m',   # Blue
        'INFO': '\033[92m',    # Green
        'WARNING': '\033[93m', # Yellow
        'ERROR': '\033[91m',   # Red
        'CRITICAL': '\033[41m' # Red background
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        """Formats log messages with color coding for console output."""
        log_message = super().format(record)
        color = self.COLORS.get(record.levelname, self.RESET)
        return f"{color}{log_message}{self.RESET}"

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

# core\README.md

```md
# FixFX Core Utilities

The `fixfx.core` package contains essential utilities and foundational code for the FixFX studio pipeline. It is designed to provide a scalable, consistent foundation for tools like `fixenv`, `studio_data`, `deployment`, and others.

## Modules

### `logger.py`
The `logger` module provides a flexible and standardized logging system that dynamically organizes logs based on the calling package.

**Key Features:**
- Color-coded console output for improved visibility.
- Rotating file-based logging with logs organized by package.
- Dynamic log paths: `Z:/pipe/.logs/<package>/<datestamp>_<package>.log`.
- Ensures log folders are created automatically for new packages.
- Flexible log level control for debugging or production use.

**Usage Example:**
\`\`\`python
from fixfx.core.logger import get_logger

log = get_logger(__name__)
log.info("Starting FixFX...")
log.warning("Potential issue detected.")
log.error("Critical error occurred.")
\`\`\`

**Log File Structure:**
\`\`\`
Z:/pipe/.logs/
├── fixenv/
│   └── 20250319_fixenv.log
├── studio_data/
│   └── 20250319_studio_data.log
├── deployment/
│   └── 20250319_deployment.log
\`\`\`

---

### `exceptions.py`
The `exceptions` module provides structured exception handling for FixFX tools. Each exception type is designed for clear, actionable error reporting with integrated logging.

**Available Exceptions:**
- `FixFXException` — Base class for all FixFX exceptions.
- `FixEnvException` — For environment variable issues.
- `FixDataException` — For data-related issues.
- `FixDeploymentException` — For deployment-related errors.
- `FixGitException` — For Git-related problems.
- `FixConfigException` — For configuration file errors.
- `FixNetworkException` — For network issues like API failures.
- `FixValidationException` — For invalid data format issues.

**Usage Example:**
\`\`\`python
from fixfx.core.exceptions import FixEnvException

def load_environment():
    raise FixEnvException("Failed to load FIXENV variables.")
\`\`\`

---

## Best Practices
- Use the `logger` module to ensure consistent and informative log output across all tools.
- Implement custom exceptions to provide meaningful error messages and structured failure handling.
- Ensure all exceptions are logged for improved debugging and troubleshooting.

---

## Future Expansion
The `fixfx.core` package is designed for scalability. Future additions may include utilities for:
- Path handling
- Configuration loading
- Dependency management


```

# data\__init__.py

```py
from fixfx.core.logger import get_logger

# Initialize package-level logger
log = get_logger(__name__)

# Automatically generate __all__ by filtering for public symbols (not starting with "_")
__all__ = ["log"]+[
    name for name in dir()
    if not name.startswith("_")  # Ignore internal/private names
    and name not in ["os", "Path"]  # Ignore unwanted imports
]
```

# data\_patterns.py

```py
"""
_patterns.py
-----------
This private module defines all the token snippets and partial path snippets for the studio pipeline.
Each snippet captures a particular portion of the file path (e.g. episode, scope, turnover),
and then we compile them in an OrderedDict so that we can name the patterns and look them up
in a given path.

The final patterns are anchored with ^...$, ensuring that the entire string must match.

Usage:
    from base import patterns
    match = patterns.get_match(file_path)
    if match:
        # do something with match.groupdict()
"""

import re
from fixfx.data import log
from collections import OrderedDict
from typing import Union

###############################################
# TOKEN REGEX SNIPPETS
###############################################

WIN_DRIVE_RE                = r"(?P<drive>[A-Za-z]):"                   # Z:
WIN_DRIVE_REF               = r"(?P<drive>)"                            #  ↳ reference to Z:/
LIN_DRIVE_RE                = r"(?P<drive>)"
PROJECT_RE                  = r"(?P<project>[^/]+)"                         # bob01
PROJECT_REF                 = r"(?P=project)"                               #  ↳ reference to bob01
PROJ_DIR                    = r"proj"                                       # proj"
SCOPE_RE                    = r"(?P<scope>[^/]+)"                           # ingestion, shots
SCOPE_REF                   = r"(?P=scope)"                                 #  ↳ reference to ingestion, shots
SUBSCOPE_RE                 = r"(?P<subscope>TO)"                           # TO
SUBSCOPE_REF                = r"(?P=subscope)"                              #  ↳ reference to TO
EPISODE_RE                  = r"(?P<episode>[^/]+)"                         # BOB_101
EPISODE_REF                 = r"(?P=episode)"                               #  ↳ reference to BOB_101
SEQUENCE_RE                 = r"(?P<sequence>[^_]+)"                        # 002
SEQUENCE_REF                = r"(?P=sequence)"                              #  ↳ reference to 002
SHOT_RE                     = r"(?P<shot>[^_]+)"                            # 030
SHOT_REF                    = r"(?P=shot)"                                  #  ↳ reference to 030
STAGE_RE                    = r"(?P<stage>[^/]+)"                           # publish, Comp, etc.
STAGE_REF                   = r"(?P=stage)"                                 #  ↳ reference to the publish, etc.
TAG_RE                      = r"(?P<tag>[^_/]+)"                            # CLN
TAG_REF                     = r"(?P=tag)"                                   #  ↳ reference to CLN
TRACK_RE                    = r"(?P<track>[^_]+)"                           # PL01
TRACK_REF                   = r"(?P=track)"                                 #  ↳ reference to PL01
TURNOVER_RE                 = r"(?P<turnover>[^/]+)"                        # bob_101_20241014_vfx...
TURNOVER_REF                = r"(?P=turnover)"                              #  ↳ reference to bob_101_20241014_vfx...
TURNOVER_CONTEXT_RE         = r"(?P<turnover_context>[^/]+)"                # exr
TURNOVER_CONTEXT_REF        = r"(?P=turnover_context)"                      #  ↳ reference to exr
VERSION_RE                  = r"(?P<version>[^/\.\s]+)"                     # v001
VERSION_REF                 = r"(?P=version)"                               #  ↳ reference to v001
TASK_RE                     = r"(?P<task>[^_]+)"                            # plate, Comp
TASK_REF                    = r"(?P=task)"                                  #  ↳ reference to plate
USER_RE                     = r"(?P<user>[^/]+)"                            # oliver-l
USER_REF                    = r"(?P=user)"                                  #  ↳ reference to oliver-l
SOURCE_TYPE_RE              = r"(?P<source_type>[^/\.]+)"                   # nuke, work
SOURCE_TYPE_REF             = r"(?P=source_type)"                           #  ↳ reference to nuke, work
SOFTWARE_RE                 = r"(?P<software>[^/\.]+)"                      # nuke
SOFTWARE_REF                = r"(?P=software)"                              #  ↳ reference to nuke
FILE_TYPE_RE                = r"(?P<file_type>[^.]+)"                       # exr, mov, nk
FILE_TYPE_REF               = r"(?P=file_type)"                             #  ↳ reference to exr, mov, nuk
FRAME_RE                    = r"(?P<frame>\d+)"                             # 1001
FRAME_REF                   = r"(?P=frame)"                                 #  ↳ reference to 1001
PADDING_RE                  = r"(?P<padding>%0*\d*d|%\d*d|%\d+?d|\d{4})"    # %04d
PADDING_REF                 = r"(?P=padding)"                               #  ↳ reference to %04d
WIDTH_RE                    = r"(?P<width>\d+)"                             # 4096
WIDTH_REF                   = r"(?P=width)"                                 #  ↳ reference to 4096
HEIGHT_RE                   = r"(?P<height>\d+)"                            # 2304
HEIGHT_REF                  = r"(?P=height)"                                #  ↳ reference to 2304
RESOLUTION_DIR              = rf"{WIDTH_RE}x{HEIGHT_RE}"

###############################################
# PARTIAL PATH SNIPPETS (No ^ or $)
###############################################
WIN_DRIVE_PATH_RE           = rf"{WIN_DRIVE_RE}"
PROJECT_PATH_RE             = rf"{WIN_DRIVE_RE}/{PROJ_DIR}/{PROJECT_RE}"
SCOPE_PATH_RE               = rf"{PROJECT_PATH_RE}/{SCOPE_RE}"
SUBSCOPE_PATH_RE            = rf"{SCOPE_PATH_RE}/{SUBSCOPE_RE}"
EPISODE_PATH_RE             = rf"{SCOPE_PATH_RE}/{EPISODE_RE}"
SEQUENCE_PATH_RE            = rf"{EPISODE_PATH_RE}/{EPISODE_REF}_{SEQUENCE_RE}"
SHOT_PATH_RE                = rf"{SEQUENCE_PATH_RE}/{EPISODE_REF}_{SEQUENCE_REF}_{SHOT_RE}_{TAG_RE}"
STAGE_PATH_RE               = rf"{SHOT_PATH_RE}/{STAGE_RE}"
STAGE_SOURCE_TYPE_PATH_RE   = rf"{STAGE_PATH_RE}/{SOURCE_TYPE_RE}"
VERSION_PATH_RE             = rf"{STAGE_PATH_RE}/{EPISODE_REF}_{SEQUENCE_REF}_{SHOT_REF}_{TAG_REF}_{VERSION_RE}"
STAGE_FILE_PATH_RE          = (
                              rf"{STAGE_SOURCE_TYPE_PATH_RE}/"
                              rf"{EPISODE_REF}_{SEQUENCE_REF}_{SHOT_REF}_{TAG_REF}_{TASK_RE}_{VERSION_RE}\."
                              rf"{FILE_TYPE_RE}"
                              )
STAGE_SEQUENCE_PATH_RE      = (
                              rf"{VERSION_PATH_RE}/{RESOLUTION_DIR}/"
                              rf"{EPISODE_REF}_{SEQUENCE_REF}_{SHOT_REF}_{TAG_REF}_{VERSION_REF}\."
                              rf"{PADDING_RE}\."
                              rf"{FILE_TYPE_RE}"
                              )
STAGE_IMAGE_PATH_RE         = (
                              rf"{VERSION_PATH_RE}/{RESOLUTION_DIR}/"
                              rf"{EPISODE_REF}_{SEQUENCE_REF}_{SHOT_REF}_{TAG_REF}_{VERSION_REF}\."
                              rf"{FRAME_RE}\."
                              rf"{FILE_TYPE_RE}"
                              )
INGEST_IMAGE_PATH_RE        = (
                              rf"{SUBSCOPE_PATH_RE}/{EPISODE_RE}/{TURNOVER_RE}/{TURNOVER_CONTEXT_RE}/"
                              rf"{EPISODE_REF}_{SEQUENCE_RE}_{SHOT_RE}_{TAG_RE}_{TRACK_RE}_{VERSION_RE}/"
                              rf"{EPISODE_REF}_{SEQUENCE_REF}_{SHOT_REF}_{TAG_REF}_{TRACK_REF}_{VERSION_REF}\."
                              rf"{FRAME_RE}\."
                              rf"{FILE_TYPE_RE}"
                              )
INGEST_SEQUENCE_PATH_RE     = (
                              rf"{SUBSCOPE_PATH_RE}/{EPISODE_RE}/{TURNOVER_RE}/{TURNOVER_CONTEXT_RE}/"
                              rf"{EPISODE_REF}_{SEQUENCE_RE}_{SHOT_RE}_{TAG_RE}_{TRACK_RE}_{VERSION_RE}/"
                              rf"{EPISODE_REF}_{SEQUENCE_REF}_{SHOT_REF}_{TAG_REF}_{TRACK_REF}_{VERSION_REF}\."
                              rf"{PADDING_RE}\."
                              rf"{FILE_TYPE_RE}"
                              )
EDITORIAL_SEQUENCE_PATH_RE  = (
                              rf"{SEQUENCE_PATH_RE}/"
                              rf"{EPISODE_REF}_{SEQUENCE_REF}_{SHOT_RE}_{TAG_RE}/"
                              rf"{STAGE_RE}/"
                              rf"{EPISODE_REF}_{SEQUENCE_REF}_{SHOT_REF}_{TAG_REF}_{TASK_RE}_{VERSION_RE}/"
                              rf"{EPISODE_REF}_{SEQUENCE_REF}_{SHOT_REF}_{TAG_REF}_{TASK_REF}_{VERSION_REF}\."
                              rf"{PADDING_RE}\."
                              rf"{FILE_TYPE_RE}"
                              )
EDITORIAL_IMAGE_PATH_RE     = (
                              rf"{SEQUENCE_PATH_RE}/"
                              rf"{EPISODE_REF}_{SEQUENCE_REF}_{SHOT_RE}_{TAG_RE}/"
                              rf"{STAGE_RE}/"
                              rf"{EPISODE_REF}_{SEQUENCE_REF}_{SHOT_REF}_{TAG_REF}_{TASK_RE}_{VERSION_RE}/"
                              rf"{EPISODE_REF}_{SEQUENCE_REF}_{SHOT_REF}_{TAG_REF}_{TASK_REF}_{VERSION_REF}\."
                              rf"{FRAME_RE}\."
                              rf"{FILE_TYPE_RE}"
                              )
STAGE_QUICKTIME_PATH_RE     = (
                              rf"{STAGE_PATH_RE}/"
                              rf"{EPISODE_REF}_{SEQUENCE_REF}_{SHOT_REF}_{TAG_REF}_{VERSION_RE}\."
                              rf"{FILE_TYPE_RE}"
                              )
COMP_WIP_PATH_RE            = (
                              rf"{STAGE_SOURCE_TYPE_PATH_RE}/"
                              rf"{USER_RE}/"
                              rf"{SOFTWARE_RE}/"
                              rf"{EPISODE_REF}_{SEQUENCE_REF}_{SHOT_REF}_{TAG_REF}_{TASK_RE}_{VERSION_RE}\."
                              rf"{FILE_TYPE_RE}"
                              )

###############################################
# COMPILED PATTERNS (^ ... $)
###############################################
def _compile(pattern):
    """Wrapper for re.compile for easier readability"""
    return re.compile(pattern, re.VERBOSE | re.IGNORECASE)

PATTERNS                    = OrderedDict([
                                ("WIN_DRIVE",               _compile(rf"^{WIN_DRIVE_PATH_RE}$")),
                                ("PROJECT_PATH",            _compile(rf"^{PROJECT_PATH_RE}$")),
                                ("SCOPE_PATH",              _compile(rf"^{SCOPE_PATH_RE}$")),
                                ("EPISODE_PATH",            _compile(rf"^{EPISODE_PATH_RE}$")),
                                ("SUBSCOPE_PATH",           _compile(rf"^{SUBSCOPE_PATH_RE}$")),
                                ("SEQUENCE_PATH",           _compile(rf"^{SEQUENCE_PATH_RE}$")),
                                ("SHOT_PATH",               _compile(rf"^{SHOT_PATH_RE}$")),
                                ("STAGE_PATH",              _compile(rf"^{STAGE_PATH_RE}$")),
                                ("VERSION_PATH",            _compile(rf"^{VERSION_PATH_RE}$")),
                                ("STAGE_SEQUENCE_PATH",     _compile(rf"^{STAGE_SEQUENCE_PATH_RE}$")),
                                ("STAGE_IMAGE_PATH",        _compile(rf"^{STAGE_IMAGE_PATH_RE}$")),
                                ("INGEST_SEQUENCE_PATH",    _compile(rf"^{INGEST_SEQUENCE_PATH_RE}$")),
                                ("INGEST_IMAGE_PATH",       _compile(rf"^{INGEST_IMAGE_PATH_RE}$")),
                                ("EDITORIAL_SEQUENCE_PATH", _compile(rf"^{EDITORIAL_SEQUENCE_PATH_RE}$")),
                                ("EDITORIAL_IMAGE_PATH",    _compile(rf"^{EDITORIAL_IMAGE_PATH_RE}$")),
                                ("STAGE_FILE_PATH",         _compile(rf"^{STAGE_FILE_PATH_RE}$")),
                                ("STAGE_QUICKTIME_PATH",    _compile(rf"^{STAGE_QUICKTIME_PATH_RE}$")),
                                ("WIP_SOURCE_TYPE_PATH",    _compile(rf"^{STAGE_SOURCE_TYPE_PATH_RE}/?$")),
                                ("COMP_WIP_PATH",           _compile(rf"^{COMP_WIP_PATH_RE}$"))
                            ])

###############################################
# ADDITIONAL CONSTANTS
###############################################
# A master list of properties (token names).
PROPERTIES                  = (
                               "drive",
                               "project",
                               "scope",
                               "subscope",
                               "episode",
                               "sequence",
                               "shot",
                               "stage",
                               "tag",
                               "track",
                               "turnover",
                               "turnover_context",
                               "version",
                               "task",
                               "user",
                               "source_type",
                               "file_type",
                               "software",
                               "frame",
                               "padding",
                               "width",
                               "height",
                               )

###############################################
# MAIN HELPERS
###############################################
def get_pattern(file_path: str) -> Union[re.Pattern, None]:
    """
    Determine the first matching compiled regex pattern for a given file path.
    We can reverse to ensure more specific patterns match first if desired.
    """
    # If you want the last item in PATTERNS to have highest priority, do reversed(...).
    # Otherwise, proceed in normal order:
    for name, pat in reversed(PATTERNS.items()):
        if pat.match(file_path):
            log.info(f"{file_path}\n\tmatched: {name}\n\t\t{pat.pattern}")
            return pat
    return None

def get_match(file_path: str) -> Union[re.Match, None]:
    """
    Returns the match object for the first pattern that matches file_path,
    or None if no pattern matches.
    """
    pat = get_pattern(file_path)
    if pat:
        return pat.match(file_path)
    return None

```

# data\README.md

```md
# Studio Data Package

The **Studio Data Package** provides a unified system for parsing and extracting data from studio file paths. It uses a configurable set of regex patterns to capture tokens such as project, episode, sequence, shot, version, and more. This package is designed to support internal workflows (e.g. file naming conventions and pipeline integrations) and is intended for internal use only.

> **Note:** The internal configuration module (_patterns.py) is considered private. External code should only interact with the public API of the package (e.g. the `StudioData` class).

---

## Features

- **Configurable File Path Parsing:**  
  Define and manage regex patterns that capture tokens from file paths.

- **Dynamic Token Extraction:**  
  Automatically expose tokens (e.g. `episode`, `tag`, `version`, etc.) as properties via dynamic attribute lookup.

- **Normalization:**  
  Automatically normalize file paths to use forward slashes and remove trailing slashes.

- **Extensibility:**  
  Easily update token definitions and partial patterns without modifying the core parsing logic.

---

## Package Structure

- **_patterns.py** (private):  
  Contains token regex snippets, partial path snippets, and compiled regex patterns. This module is **private** and should not be imported directly.

- **studio_data.py** (public):  
  Contains the `StudioData` class, which uses the patterns defined in `_patterns.py` to parse file paths and provide easy access to captured tokens.

---

## Usage

### Basic Example

Below is an example of how to use the `StudioData` class:

\`\`\`python
from fixfx.data.studio_data import StudioData

# Provide a full file path
file_path = "Z:/proj/bob01/ingestion/TO/BOB_101/bob_101_20241014_vfx_pull_fix_fx_6/exr/BOB_101_002_061_DRT_PL01_V001/BOB_101_002_061_DRT_PL01_V001.%04d.exr"

# Create a StudioData instance from the file path
sd = StudioData(file_path)

# Access extracted tokens via properties
print("Project:", sd.project)      # e.g. "bob01"
print("Episode:", sd.episode)      # e.g. "BOB_101"
print("Sequence:", sd.sequence)    # e.g. "002"
print("Shot:", sd.shot)            # e.g. "061"
print("Tag:", sd.tag)              # e.g. "DRT"
print("Version:", sd.version)      # e.g. "V001"
print("File Type:", sd.file_type)  # e.g. "exr"
\`\`\`

### Pretty-Printing All Properties

You can pretty-print all captured tokens by adding a method (e.g. `pp_properties`) to `StudioData`:

\`\`\`python
sd.pp_properties()  # Displays a nicely formatted dictionary of all tokens.
\`\`\`

### Handling Unsupported Paths

If a file path does not match any of the known patterns, the package raises a `ValueError`. Your code can catch this exception to handle unsupported paths gracefully:

\`\`\`python
try:
    sd = StudioData("/path/to/unsupported/file.ext")
except ValueError as e:
    print("Unsupported file path:", e)
\`\`\`

---

## API Reference

### StudioData

**`StudioData(file_path: str)`**  
Creates a new instance by normalizing and parsing the given file path.  
- **Attributes (properties):**  
  - `project`
  - `episode`
  - `sequence`
  - `shot`
  - `tag`
  - `track`
  - `turnover`
  - `turnover_context`
  - `version`
  - `task`
  - `user`
  - `source_type`
  - `file_type`
  - `frame`
  - `padding`
  - `width`
  - `height`
  - ... (and any additional tokens defined in the configuration)

**Methods:**

- **`__getattr__(self, name: str) -> str`**  
  Dynamically returns the captured token for a given property name if it exists in the regex match.  

- **`pp_properties(self)`**  
  Pretty-prints all captured tokens.

---

## Developer Notes

- **Internal Configuration:**  
  The `_patterns.py` file is considered private. It defines all token snippets and compiles the regex patterns into an ordered dictionary. Changes here affect how file paths are parsed.

- **Extensibility:**  
  To add new tokens or modify existing ones, update the token snippets in `_patterns.py` and adjust the partial path snippets accordingly.

- **Testing:**  
  Unit tests are provided in the `tests/` directory. Run them with:
  \`\`\`bash
  python -m unittest discover -s tests
  \`\`\`

```

# data\studio_data.py

```py
"""
base.py
--------------
Provides the StudioData class that uses the _patterns module to parse file paths.
Once instantiated with a file path, the class can expose its extracted tokens
(episode, shot, version, etc.) via properties or dynamic attributes. This module
centralizes all logic for normalizing paths, attempting a match, and retrieving named
capture groups from the matched pattern.

Usage:
    from base import StudioData
    sd = StudioData("Z:/proj/bob01/shots/BOB_101/BOB_101_002/...")
    print(sd.episode)  # e.g. BOB_101
    print(sd.sequence) # e.g. 002
"""

from fixfx.data import _patterns, log


class StudioData:
    """
    Uses _patterns.get_match to find a match for the file_path, then dynamically
    exposes each token from _patterns.PROPERTIES as an attribute (via __getattr__).
    """

    def __init__(self, file_path: str):
        self._file_path = ""
        self.file_path = file_path
        self._match = _patterns.get_match(self.file_path)
        if not self._match:
            raise ValueError(f"No known pattern matches file path: {file_path}")

    @property
    def file_path(self) -> str:
        """
        Returns the normalized file path (no trailing slash, forward slashes only).
        """
        return self._file_path

    @file_path.setter
    def file_path(self, value: str):
        """
        Normalizes incoming paths:
          - Replace backslashes with forward slashes
          - Remove trailing slash (unless the path is exactly '/')
          - Log a warning if you're changing an existing path
        """
        normalized = value.replace('\\', '/')

        if len(normalized) > 1 and normalized.endswith('/'):
            normalized = normalized[:-1]

        self._file_path = normalized

    def __getattr__(self, name: str) -> str:
        """
        If 'name' is in _patterns.PROPERTIES, return the matched group.
        Otherwise, raise AttributeError.
        """
        if name in _patterns.PROPERTIES:
            # Return empty string if group wasn't captured
            return self._match.groupdict().get(name, "") or ""
        else:
            # Log an error if the attribute wasn't found
            log.error(f"No match for property '{name}' in _patterns.PROPERTIES")
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __repr__(self):
        return f"<StudioData path={self.file_path!r}>"

    def pp_properties(self):
        """
        Pretty-print all properties from _patterns.PROPERTIES that are captured.
        """
        from pprint import pprint
        data = {}
        for prop in _patterns.PROPERTIES:
            data[prop] = getattr(self, prop)
        pprint(data)


class PathConstructor:
    """
    Dynamically constructs valid file paths using tokens from _patterns.py.
    Provides dedicated getter methods for each *_PATH_RE pattern.

    ## Token Reference
    Each getter function uses tokens structured as follows:

    Example Path: Z:/proj/bob01/shots/BOB_101/
    Tokenized: {drive}/proj/{project}/{scope}/{episode}
    Example call: get_episode_path(drive="Z:", project="bob01", scope="shots", episode="BOB_101")

    Each function's token requirements align with its respective *_PATH_RE.
    """

    DEFAULTS = {"drive": "Z:"}

    def __init__(self, **kwargs):
        self.tokens = {**self.DEFAULTS, **kwargs}

    def construct(self, pattern_name: str, **kwargs) -> str:
        """Constructs a file path using the specified pattern and provided tokens."""
        if pattern_name not in _patterns.PATTERNS:
            log.error("Unknown pattern '{}'", pattern_name)
            raise ValueError(f"Unknown pattern '{pattern_name}' in _patterns.PATTERNS")

        # Build the path
        pattern = _patterns.PATTERNS[pattern_name].pattern.strip("^$")
        path = pattern
        for token, value in {**self.tokens, **kwargs}.items():
            ref_token = f"(?P<{token}>"
            if ref_token in path:
                path = path.replace(ref_token, value)

        # Normalize slashes and ensure no trailing slash
        path = path.replace("\\", "/").rstrip("/")

        return path

# ------------------------------
# Helper Functions for Simplification
# ------------------------------

def get_win_drive_path(drive="Z:") -> str:
    """
    Constructs a WIN_DRIVE_PATH.

    Args:
        drive (str): A windows drive. ie. Z:

    Example Usage:
        Example call: get_win_drive_path(drive="Z:")
        Tokenized: {drive}

    Returns:
        str: WIN_DRIVE_PATH. Example Path: Z:
    """
    return PathConstructor().construct("WIN_DRIVE", drive=drive)

def get_project_path(drive="Z:", project="") -> str:
    """
    Constructs a PROJECT_PATH.

    Args:
        drive (str): A windows drive. ie. Z:
        project (str): Project name. ie. bob01

    Example Usage:
        Example call: get_project_path(drive="Z:", project="bob01")
        Tokenized: {drive}/proj/{project}

    Returns:
        str: PROJECT_PATH. Example Path: Z:/proj/bob01
    """
    return PathConstructor().construct("PROJECT_PATH", drive=drive, project=project)

def get_scope_path(drive="Z:", project="", scope="") -> str:
    """
    Constructs a SCOPE_PATH.

    Args:
        drive (str): A windows drive. ie. Z:
        project (str): Project name. ie. bob01
        scope (str): Scope identifier. ie. shots

    Example Usage:
        Example call: get_scope_path(drive="Z:", project="bob01", scope="shots")
        Tokenized: {drive}/proj/{project}/{scope}

    Returns:
        str: SCOPE_PATH. Example Path: Z:/proj/bob01/shots
    """
    return PathConstructor().construct("SCOPE_PATH", drive=drive, project=project, scope=scope)

def get_subscope_path(drive="Z:", project="", scope="", subscope="TO") -> str:
    """
    Constructs a SUBSCOPE_PATH.

    Args:
        drive (str): A windows drive. ie. Z:
        project (str): Project name. ie. bob01
        scope (str): Scope identifier. ie. ingestion
        subscope (str): Sub-scope identifier. ie. TO

    Example Usage:
        Example call: get_subscope_path(drive="Z:", project="bob01", scope="ingestion", subscope="TO")
        Tokenized: {drive}/proj/{project}/{scope}/{subscope}

    Returns:
        str: SUBSCOPE_PATH. Example Path: Z:/proj/bob01/ingestion/TO
    """
    return PathConstructor().construct("SUBSCOPE_PATH", drive=drive, project=project, scope=scope, subscope=subscope)

def get_episode_path(drive="Z:", project="", scope="", episode="") -> str:
    """
    Constructs an EPISODE_PATH.

    Args:
        drive (str): A windows drive. ie. Z:
        project (str): Project name. ie. bob01
        scope (str): Scope identifier. ie. shots
        episode (str): Episode identifier. ie. BOB_101

    Example Usage:
        Example call: get_episode_path(drive="Z:", project="bob01", scope="shots", episode="BOB_101")
        Tokenized: {drive}/proj/{project}/{scope}/{episode}

    Returns:
        str: EPISODE_PATH. Example Path: Z:/proj/bob01/shots/BOB_101
    """
    return PathConstructor().construct("EPISODE_PATH", drive=drive, project=project, scope=scope, episode=episode)

def get_sequence_path(drive="Z:", project="", scope="", episode="", sequence="") -> str:
    """
    Constructs a SEQUENCE_PATH.

    Args:
        drive (str): A windows drive. ie. Z:
        project (str): Project name. ie. bob01
        scope (str): Scope identifier. ie. shots
        episode (str): Episode identifier. ie. BOB_101
        sequence (str): Sequence identifier. ie. 002

    Example Usage:
        Example call: get_sequence_path(drive="Z:", project="bob01", scope="shots", episode="BOB_101", sequence="002")
        Tokenized: {drive}/proj/{project}/{scope}/{episode}/{episode}_{sequence}

    Returns:
        str: SEQUENCE_PATH. Example Path: Z:/proj/bob01/shots/BOB_101/BOB_101_002
    """
    return PathConstructor().construct("SEQUENCE_PATH", drive=drive, project=project, scope=scope,
                                      episode=episode, sequence=sequence)

def get_shot_path(drive="Z:", project="", scope="", episode="", sequence="", shot="", tag="") -> str:
    """
    Constructs a SHOT_PATH.

    Args:
        drive (str): A windows drive. ie. Z:
        project (str): Project name. ie. bob01
        scope (str): Scope identifier. ie. shots
        episode (str): Episode identifier. ie. BOB_101
        sequence (str): Sequence identifier. ie. 002
        shot (str): Shot identifier. ie. 030
        tag (str): Tag identifier. ie. CLN

    Example Usage:
        Example call: get_shot_path(drive="Z:", project="bob01", scope="shots", episode="BOB_101",
                                   sequence="002", shot="030", tag="CLN")
        Tokenized: {drive}/proj/{project}/{scope}/{episode}/{episode}_{sequence}/{episode}_{sequence}_{shot}_{tag}

    Returns:
        str: SHOT_PATH. Example Path: Z:/proj/bob01/shots/BOB_101/BOB_101_002/BOB_101_002_030_CLN
    """
    return PathConstructor().construct("SHOT_PATH", drive=drive, project=project, scope=scope,
                                      episode=episode, sequence=sequence, shot=shot, tag=tag)

def get_stage_path(drive="Z:", project="", scope="", episode="", sequence="", shot="", tag="", stage="") -> str:
    """
    Constructs a STAGE_PATH.

    Args:
        drive (str): A windows drive. ie. Z:
        project (str): Project name. ie. bob01
        scope (str): Scope identifier. ie. shots
        episode (str): Episode identifier. ie. BOB_101
        sequence (str): Sequence identifier. ie. 002
        shot (str): Shot identifier. ie. 030
        tag (str): Tag identifier. ie. CLN
        stage (str): Stage identifier. ie. publish

    Example Usage:
        Example call: get_stage_path(drive="Z:", project="bob01", scope="shots", episode="BOB_101",
                                    sequence="002", shot="030", tag="CLN", stage="publish")
        Tokenized: {drive}/proj/{project}/{scope}/{episode}/{episode}_{sequence}/{episode}_{sequence}_{shot}_{tag}/{stage}

    Returns:
        str: STAGE_PATH. Example Path: Z:/proj/bob01/shots/BOB_101/BOB_101_002/BOB_101_002_030_CLN/publish
    """
    return PathConstructor().construct("STAGE_PATH", drive=drive, project=project, scope=scope,
                                      episode=episode, sequence=sequence, shot=shot, tag=tag, stage=stage)

def get_stage_source_type_path(drive="Z:", project="", scope="", episode="", sequence="", shot="",
                              tag="", stage="", source_type="") -> str:
    """
    Constructs a WIP_SOURCE_TYPE_PATH.

    Args:
        drive (str): A windows drive. ie. Z:
        project (str): Project name. ie. bob01
        scope (str): Scope identifier. ie. shots
        episode (str): Episode identifier. ie. BOB_101
        sequence (str): Sequence identifier. ie. 002
        shot (str): Shot identifier. ie. 030
        tag (str): Tag identifier. ie. CLN
        stage (str): Stage identifier. ie. Comp
        source_type (str): Source type. ie. work

    Example Usage:
        Example call: get_stage_source_type_path(drive="Z:", project="bob01", scope="shots", episode="BOB_101",
                                               sequence="002", shot="030", tag="CLN", stage="Comp", source_type="work")
        Tokenized: {drive}/proj/{project}/{scope}/{episode}/{episode}_{sequence}/{episode}_{sequence}_{shot}_{tag}/{stage}/{source_type}

    Returns:
        str: WIP_SOURCE_TYPE_PATH. Example Path: Z:/proj/bob01/shots/BOB_101/BOB_101_002/BOB_101_002_030_CLN/Comp/work
    """
    return PathConstructor().construct("WIP_SOURCE_TYPE_PATH", drive=drive, project=project, scope=scope,
                                      episode=episode, sequence=sequence, shot=shot, tag=tag, stage=stage,
                                      source_type=source_type)

def get_version_path(drive="Z:", project="", scope="", episode="", sequence="", shot="",
                    tag="", stage="", version="") -> str:
    """
    Constructs a VERSION_PATH.

    Args:
        drive (str): A windows drive. ie. Z:
        project (str): Project name. ie. bob01
        scope (str): Scope identifier. ie. shots
        episode (str): Episode identifier. ie. BOB_101
        sequence (str): Sequence identifier. ie. 002
        shot (str): Shot identifier. ie. 030
        tag (str): Tag identifier. ie. CLN
        stage (str): Stage identifier. ie. publish
        version (str): Version identifier. ie. v001

    Example Usage:
        Example call: get_version_path(drive="Z:", project="bob01", scope="shots", episode="BOB_101",
                                     sequence="002", shot="030", tag="CLN", stage="publish", version="v001")
        Tokenized: {drive}/proj/{project}/{scope}/{episode}/{episode}_{sequence}/{episode}_{sequence}_{shot}_{tag}/{stage}/{episode}_{sequence}_{shot}_{tag}_{version}

    Returns:
        str: VERSION_PATH. Example Path: Z:/proj/bob01/shots/BOB_101/BOB_101_002/BOB_101_002_030_CLN/publish/BOB_101_002_030_CLN_v001
    """
    return PathConstructor().construct("VERSION_PATH", drive=drive, project=project, scope=scope,
                                      episode=episode, sequence=sequence, shot=shot, tag=tag, stage=stage,
                                      version=version)

def get_stage_file_path(drive="Z:", project="", scope="", episode="", sequence="", shot="",
                        tag="", stage="", source_type="", task="", version="", file_type="") -> str:
    """
    Constructs a STAGE_FILE_PATH.

    Args:
        drive (str): A windows drive. ie. Z:
        project (str): Project name. ie. bob01
        scope (str): Scope identifier. ie. shots
        episode (str): Episode identifier. ie. BOB_101
        sequence (str): Sequence identifier. ie. 002
        shot (str): Shot identifier. ie. 030
        tag (str): Tag identifier. ie. CLN
        stage (str): Stage identifier. ie. publish
        source_type (str): Source type. ie. nuke
        task (str): Task identifier. ie. Comp
        version (str): Version identifier. ie. v001
        file_type (str): File type. ie. nk

    Example Usage:
        Example call: get_stage_file_path(drive="Z:", project="bob01", scope="shots", episode="BOB_101",
                                        sequence="002", shot="030", tag="CLN", stage="publish", source_type="nuke",
                                        task="Comp", version="v001", file_type="nk")
        Tokenized: {drive}/proj/{project}/{scope}/{episode}/{episode}_{sequence}/{episode}_{sequence}_{shot}_{tag}/{stage}/{source_type}/{episode}_{sequence}_{shot}_{tag}_{task}_{version}.{file_type}

    Returns:
        str: STAGE_FILE_PATH. Example Path: Z:/proj/bob01/shots/BOB_101/BOB_101_002/BOB_101_002_030_CLN/publish/nuke/BOB_101_002_030_CLN_Comp_v001.nk
    """
    return PathConstructor().construct("STAGE_FILE_PATH", drive=drive, project=project, scope=scope,
                                      episode=episode, sequence=sequence, shot=shot, tag=tag, stage=stage,
                                      source_type=source_type, task=task, version=version, file_type=file_type)

def get_stage_sequence_path(drive="Z:", project="", scope="", episode="", sequence="", shot="",
                           tag="", stage="", version="", width="", height="", padding="", file_type="") -> str:
    """
    Constructs a STAGE_SEQUENCE_PATH.

    Args:
        drive (str): A windows drive. ie. Z:
        project (str): Project name. ie. bob01
        scope (str): Scope identifier. ie. shots
        episode (str): Episode identifier. ie. BOB_101
        sequence (str): Sequence identifier. ie. 002
        shot (str): Shot identifier. ie. 030
        tag (str): Tag identifier. ie. CLN
        stage (str): Stage identifier. ie. publish
        version (str): Version identifier. ie. v001
        width (str): Width of the image. ie. 4096
        height (str): Height of the image. ie. 2304
        padding (str): Frame padding pattern. ie. %04d
        file_type (str): File type. ie. exr

    Example Usage:
        Example call: get_stage_sequence_path(drive="Z:", project="bob01", scope="shots", episode="BOB_101",
                                            sequence="002", shot="030", tag="CLN", stage="publish", version="v001",
                                            width="4096", height="2304", padding="%04d", file_type="exr")
        Tokenized: {drive}/proj/{project}/{scope}/{episode}/{episode}_{sequence}/{episode}_{sequence}_{shot}_{tag}/{stage}/{episode}_{sequence}_{shot}_{tag}_{version}/{width}x{height}/{episode}_{sequence}_{shot}_{tag}_{version}.{padding}.{file_type}

    Returns:
        str: STAGE_SEQUENCE_PATH. Example Path: Z:/proj/bob01/shots/BOB_101/BOB_101_002/BOB_101_002_030_CLN/publish/BOB_101_002_030_CLN_v001/4096x2304/BOB_101_002_030_CLN_v001.%04d.exr
    """
    return PathConstructor().construct("STAGE_SEQUENCE_PATH", drive=drive, project=project, scope=scope,
                                      episode=episode, sequence=sequence, shot=shot, tag=tag, stage=stage,
                                      version=version, width=width, height=height, padding=padding, file_type=file_type)

def get_stage_image_path(drive="Z:", project="", scope="", episode="", sequence="", shot="",
                        tag="", stage="", version="", width="", height="", frame="", file_type="") -> str:
    """
    Constructs a STAGE_IMAGE_PATH.

    Args:
        drive (str): A windows drive. ie. Z:
        project (str): Project name. ie. bob01
        scope (str): Scope identifier. ie. shots
        episode (str): Episode identifier. ie. BOB_101
        sequence (str): Sequence identifier. ie. 002
        shot (str): Shot identifier. ie. 030
        tag (str): Tag identifier. ie. CLN
        stage (str): Stage identifier. ie. publish
        version (str): Version identifier. ie. v001
        width (str): Width of the image. ie. 4096
        height (str): Height of the image. ie. 2304
        frame (str): Frame number. ie. 1001
        file_type (str): File type. ie. exr

    Example Usage:
        Example call: get_stage_image_path(drive="Z:", project="bob01", scope="shots", episode="BOB_101",
                                         sequence="002", shot="030", tag="CLN", stage="publish", version="v001",
                                         width="4096", height="2304", frame="1001", file_type="exr")
        Tokenized: {drive}/proj/{project}/{scope}/{episode}/{episode}_{sequence}/{episode}_{sequence}_{shot}_{tag}/{stage}/{episode}_{sequence}_{shot}_{tag}_{version}/{width}x{height}/{episode}_{sequence}_{shot}_{tag}_{version}.{frame}.{file_type}

    Returns:
        str: STAGE_IMAGE_PATH. Example Path: Z:/proj/bob01/shots/BOB_101/BOB_101_002/BOB_101_002_030_CLN/publish/BOB_101_002_030_CLN_v001/4096x2304/BOB_101_002_030_CLN_v001.1001.exr
    """
    return PathConstructor().construct("STAGE_IMAGE_PATH", drive=drive, project=project, scope=scope,
                                      episode=episode, sequence=sequence, shot=shot, tag=tag, stage=stage,
                                      version=version, width=width, height=height, frame=frame, file_type=file_type)

def get_ingest_image_path(drive="Z:", project="", scope="", subscope="TO", episode="", turnover="",
                         turnover_context="", sequence="", shot="", tag="", track="", version="",
                         frame="", file_type="") -> str:
    """
    Constructs an INGEST_IMAGE_PATH.

    Args:
        drive (str): A windows drive. ie. Z:
        project (str): Project name. ie. bob01
        scope (str): Scope identifier. ie. ingestion
        subscope (str): Sub-scope identifier. ie. TO
        episode (str): Episode identifier. ie. BOB_101
        turnover (str): Turnover identifier. ie. bob_101_20241014_vfx
        turnover_context (str): Turnover context. ie. exr
        sequence (str): Sequence identifier. ie. 002
        shot (str): Shot identifier. ie. 030
        tag (str): Tag identifier. ie. CLN
        track (str): Track identifier. ie. PL01
        version (str): Version identifier. ie. v001
        frame (str): Frame number. ie. 1001
        file_type (str): File type. ie. exr

    Example Usage:
        Example call: get_ingest_image_path(drive="Z:", project="bob01", scope="ingestion", subscope="TO",
                                          episode="BOB_101", turnover="bob_101_20241014_vfx", turnover_context="exr",
                                          sequence="002", shot="030", tag="CLN", track="PL01", version="v001",
                                          frame="1001", file_type="exr")
        Tokenized: {drive}/proj/{project}/{scope}/{subscope}/{episode}/{turnover}/{turnover_context}/{episode}_{sequence}_{shot}_{tag}_{track}_{version}/{episode}_{sequence}_{shot}_{tag}_{track}_{version}.{frame}.{file_type}

    Returns:
        str: INGEST_IMAGE_PATH. Example Path: Z:/proj/bob01/ingestion/TO/BOB_101/bob_101_20241014_vfx/exr/BOB_101_002_030_CLN_PL01_v001/BOB_101_002_030_CLN_PL01_v001.1001.exr
    """
    return PathConstructor().construct("INGEST_IMAGE_PATH", drive=drive, project=project, scope=scope,
                                      subscope=subscope, episode=episode, turnover=turnover,
                                      turnover_context=turnover_context, sequence=sequence, shot=shot,
                                      tag=tag, track=track, version=version, frame=frame, file_type=file_type)

def get_ingest_sequence_path(drive="Z:", project="", scope="", subscope="TO", episode="", turnover="",
                            turnover_context="", sequence="", shot="", tag="", track="", version="",
                            padding="", file_type="") -> str:
    """
    Constructs an INGEST_SEQUENCE_PATH.

    Args:
        drive (str): A windows drive. ie. Z:
        project (str): Project name. ie. bob01
        scope (str): Scope identifier. ie. ingestion
        subscope (str): Sub-scope identifier. ie. TO
        episode (str): Episode identifier. ie. BOB_101
        turnover (str): Turnover identifier. ie. bob_101_20241014_vfx
        turnover_context (str): Turnover context. ie. exr
        sequence (str): Sequence identifier. ie. 002
        shot (str): Shot identifier. ie. 030
        tag (str): Tag identifier. ie. CLN
        track (str): Track identifier. ie. PL01
        version (str): Version identifier. ie. v001
        padding (str): Frame padding pattern. ie. %04d
        file_type (str): File type. ie. exr

    Example Usage:
        Example call: get_ingest_sequence_path(drive="Z:", project="bob01", scope="ingestion", subscope="TO",
                                             episode="BOB_101", turnover="bob_101_20241014_vfx", turnover_context="exr",
                                             sequence="002", shot="030", tag="CLN", track="PL01", version="v001",
                                             padding="%04d", file_type="exr")
        Tokenized: {drive}/proj/{project}/{scope}/{subscope}/{episode}/{turnover}/{turnover_context}/{episode}_{sequence}_{shot}_{tag}_{track}_{version}/{episode}_{sequence}_{shot}_{tag}_{track}_{version}.{padding}.{file_type}

    Returns:
        str: INGEST_SEQUENCE_PATH. Example Path: Z:/proj/bob01/ingestion/TO/BOB_101/bob_101_20241014_vfx/exr/BOB_101_002_030_CLN_PL01_v001/BOB_101_002_030_CLN_PL01_v001.%04d.exr
    """
    return PathConstructor().construct("INGEST_SEQUENCE_PATH", drive=drive, project=project, scope=scope,
                                      subscope=subscope, episode=episode, turnover=turnover,
                                      turnover_context=turnover_context, sequence=sequence, shot=shot,
                                      tag=tag, track=track, version=version, padding=padding, file_type=file_type)

def get_editorial_sequence_path(drive="Z:", project="", scope="", episode="", sequence="", shot="",
                               tag="", stage="", task="", version="", padding="", file_type="") -> str:
    """
    Constructs an EDITORIAL_SEQUENCE_PATH.

    Args:
        drive (str): A windows drive. ie. Z:
        project (str): Project name. ie. bob01
        scope (str): Scope identifier. ie. editorial
        episode (str): Episode identifier. ie. BOB_101
        sequence (str): Sequence identifier. ie. 002
        shot (str): Shot identifier. ie. 030
        tag (str): Tag identifier. ie. CLN
        stage (str): Stage identifier. ie. publish
        task (str): Task identifier. ie. plate
        version (str): Version identifier. ie. v001
        padding (str): Frame padding pattern. ie. %04d
        file_type (str): File type. ie. exr

    Example Usage:
        Example call: get_editorial_sequence_path(drive="Z:", project="bob01", scope="editorial", episode="BOB_101",
                                                sequence="002", shot="030", tag="CLN", stage="publish", task="plate",
                                                version="v001", padding="%04d", file_type="exr")
        Tokenized: {drive}/proj/{project}/{scope}/{episode}/{episode}_{sequence}/{episode}_{sequence}_{shot}_{tag}/{stage}/{episode}_{sequence}_{shot}_{tag}_{task}_{version}/{episode}_{sequence}_{shot}_{tag}_{task}_{version}.{padding}.{file_type}

    Returns:
        str: EDITORIAL_SEQUENCE_PATH. Example Path: Z:/proj/bob01/editorial/BOB_101/BOB_101_002/BOB_101_002_030_CLN/publish/BOB_101_002_030_CLN_plate_v001/BOB_101_002_030_CLN_plate_v001.%04d.exr
    """
    return PathConstructor().construct("EDITORIAL_SEQUENCE_PATH", drive=drive, project=project, scope=scope,
                                      episode=episode, sequence=sequence, shot=shot, tag=tag, stage=stage,
                                      task=task, version=version, padding=padding, file_type=file_type)

def get_editorial_image_path(drive="Z:", project="", scope="", episode="", sequence="", shot="",
                            tag="", stage="", task="", version="", frame="", file_type="") -> str:
    """
    Constructs an EDITORIAL_IMAGE_PATH.

    Args:
        drive (str): A windows drive. ie. Z:
        project (str): Project name. ie. bob01
        scope (str): Scope identifier. ie. editorial
        episode (str): Episode identifier. ie. BOB_101
        sequence (str): Sequence identifier. ie. 002
        shot (str): Shot identifier. ie. 030
        tag (str): Tag identifier. ie. CLN
        stage (str): Stage identifier. ie. publish
        task (str): Task identifier. ie. plate
        version (str): Version identifier. ie. v001
        frame (str): Frame number. ie. 1001
        file_type (str): File type. ie. exr

    Example Usage:
        Example call: get_editorial_image_path(drive="Z:", project="bob01", scope="editorial", episode="BOB_101",
                                             sequence="002", shot="030", tag="CLN", stage="publish", task="plate",
                                             version="v001", frame="1001", file_type="exr")
        Tokenized: {drive}/proj/{project}/{scope}/{episode}/{episode}_{sequence}/{episode}_{sequence}_{shot}_{tag}/{stage}/{episode}_{sequence}_{shot}_{tag}_{task}_{version}/{episode}_{sequence}_{shot}_{tag}_{task}_{version}.{frame}.{file_type}

    Returns:
        str: EDITORIAL_IMAGE_PATH. Example Path: Z:/proj/bob01/editorial/BOB_101/BOB_101_002/BOB_101_002_030_CLN/publish/BOB_101_002_030_CLN_plate_v001/BOB_101_002_030_CLN_plate_v001.1001.exr
    """
    return PathConstructor().construct("EDITORIAL_IMAGE_PATH", drive=drive, project=project, scope=scope,
                                      episode=episode, sequence=sequence, shot=shot, tag=tag, stage=stage,
                                      task=task, version=version, frame=frame, file_type=file_type)


def get_stage_quicktime_path(drive="Z:", project="", scope="", episode="", sequence="", shot="", tag="", stage="",
                             version="", file_type="") -> str:
    """
    Constructs a STAGE_QUICKTIME_PATH.

    Args:
        drive (str): A windows drive. ie. Z:
        project (str): Project name. ie. bob01
        scope (str): Scope name. ie. shots
        episode (str): Episode name. ie. BOB_101
        sequence (str): Sequence number. ie. 002
        shot (str): Shot number. ie. 030
        tag (str): Tag name. ie. CLN
        stage (str): Stage name. ie. publish
        version (str): Version number. ie. v001
        file_type (str): File type. ie. mov

    Example Usage:
        Example call: get_stage_quicktime_path(drive="Z:", project="bob01", scope="shots", episode="BOB_101",
                                             sequence="002", shot="030", tag="CLN", stage="publish",
                                             version="v001", file_type="mov")
        Tokenized: {drive}/proj/{project}/{scope}/{episode}/{episode}_{sequence}/{episode}_{sequence}_{shot}_{tag}/{stage}/
                   {episode}_{sequence}_{shot}_{tag}_{version}.{file_type}

    Returns:
        str: STAGE_QUICKTIME_PATH. Example Path: Z:/proj/bob01/shots/BOB_101/BOB_101_002/BOB_101_002_030_CLN/publish/BOB_101_002_030_CLN_v001.mov
    """
    return PathConstructor().construct("STAGE_QUICKTIME_PATH", drive=drive, project=project, scope=scope,
                                      episode=episode, sequence=sequence, shot=shot, tag=tag, stage=stage,
                                      version=version, file_type=file_type)



def get_comp_wip_path(drive="Z:", project="", scope="", episode="", sequence="", shot="", tag="", stage="",
                      source_type="", user="", software="", task="", version="", file_type="") -> str:
    """
    Constructs a COMP_WIP_PATH.

    Args:
        drive (str): A windows drive. ie. Z:
        project (str): Project name. ie. bob01
        scope (str): Scope name. ie. shots
        episode (str): Episode name. ie. BOB_101
        sequence (str): Sequence number. ie. 002
        shot (str): Shot number. ie. 030
        tag (str): Tag name. ie. CLN
        stage (str): Stage name. ie. Comp
        source_type (str): Source type. ie. work
        user (str): User name. ie. oliver-l
        software (str): Software name. ie. nuke
        task (str): Task name. ie. comp
        version (str): Version number. ie. v001
        file_type (str): File type. ie. nk

    Example Usage:
        Example call: get_comp_wip_path(drive="Z:", project="bob01", scope="shots", episode="BOB_101",
                                      sequence="002", shot="030", tag="CLN", stage="Comp", source_type="work",
                                      user="oliver-l", software="nuke", task="comp", version="v001", file_type="nk")
        Tokenized: {drive}/proj/{project}/{scope}/{episode}/{episode}_{sequence}/{episode}_{sequence}_{shot}_{tag}/{stage}/
                   {source_type}/{user}/{software}/{episode}_{sequence}_{shot}_{tag}_{task}_{version}.{file_type}

    Returns:
        str: COMP_WIP_PATH. Example Path: Z:/proj/bob01/shots/BOB_101/BOB_101_002/BOB_101_002_030_CLN/Comp/work/oliver-l/nuke/BOB_101_002_030_CLN_comp_v001.nk
    """

    return PathConstructor().construct("COMP_WIP_PATH", drive=drive, project=project, scope=scope,
                                      episode=episode, sequence=sequence, shot=shot, tag=tag, stage=stage,
                                      source_type=source_type, user=user, software=software,
                                      task=task, version=version, file_type=file_type)




```

# README.md

```md
# FixFX Package

The `fixfx` package is a comprehensive Python toolkit designed to support FixFX's visual effects pipeline and workflow management. It includes utilities for Git release management, deployment scripts, data handling, and testing. This README outlines the package structure, usage examples, and test procedures.

## Table of Contents

- [File Structure](#file-structure)
- [Usage Examples](#usage-examples)
  - [Git Workflow & Aliases](#git-workflow--aliases)
- [Deployment Scripts](#deployment-scripts)
- [Running Unit Tests](#running-unit-tests)
- [Development Environment Shortcuts](#development-environment-shortcuts)

## File Structure

Below is a tree view of the project structure:

\`\`\`
fixfx/
├── README.md                 # This file
├── __init__.py               # Package initialization
├── bin/                      # Utility scripts and tools
│   ├── fix-deploy.sh         # Shell script for deploying code
│   └── fix-git.sh            # Custom Git helper script
├── data/                     # Data handling modules
│   ├── README.md             # Documentation for the data submodule
│   ├── studio_data.py        # Manages extraction and representation of studio data
│   ├── _patterns.py          # Contains reusable data patterns and regexes
│   └── __init__.py           # Module initializer for data handling
├── deployment/               # Deployment and release management
│   ├── __init__.py
│   ├── config.py             # Deployment-related configurations
│   ├── git.py                # Git operations and version handling functions
│   ├── metadata.py           # Handles deployment metadata
│   └── scripts/              # Deployment scripts
│       ├── release.py        # Script for managing releases (staging and finalizing)
│       ├── rollback.py       # Script for rolling back deployments
│       └── deploy_code.sh    # Shell script for automating deployments
└── tests/                    # Unit tests for the package
    ├── __init__.py
    ├── test_deployment.py    # Tests for deployment functionalities
    └── test_studio_data.py   # Tests for data handling functionalities
\`\`\`

## Usage Examples

### Git Workflow & Aliases

The package provides several functions and aliases to streamline Git operations:

### Commit & Branch Management

| Command             | Description                                                    |
|---------------------|----------------------------------------------------------------|
| `gcam "<msg>"`      | Add all changes and commit with a message.                     |
| `gcm "<msg>"`       | Commit only staged changes with a message.                     |
| `gbf <branch-name>` | Create and checkout a new feature branch.                      |
| `gbh <branch-name>` | Create and checkout a new hotfix branch.                       |
| `gbd <branch-name>` | Delete the specified branch.                                   |
| `gcb <branch-name>` | Create and checkout a new branch.                              |
| `gm`                | Checkout the main branch.                                      |
| `gs`                | Display the Git status.                                        |
| `gpom`              | Pull the latest changes from `origin/main`.                    |
| `ga`                | Stage all changes.                                             |
| `gp`                | Checkout the previous branch.                                  |
| `gmm`               | Merge the current branch into main and push to `origin`.       |
| `gmd`               | Merge develop into the current branch.                         |
| `gcd`               | Checkout the develop branch.                                   |
| `gpod`              | Pull the latest changes from develop.                          |
| `gmmd`              | Sync main with origin and merge into develop.                  |
| `gpu`               | Push the main branch to origin.                                |
| `gtma`              | Increment the **MAJOR** version (resets MINOR and PATCH to 0). |
| `gtm`               | Increment the **MINOR** version (resets PATCH to 0).           |
| `gtp`               | Increment the **PATCH** version.                               |

Each function automatically:
- Fetches tags from the remote.
- Determines the latest semantic version.
- Increments the correct version segment.
- Verifies the new tag does not already exist on the remote before pushing.

Example usage:

\`\`\`bash
# Create a new major release (e.g., from v1.2.3 to v2.0.0)
gtma

# Create a new minor release (e.g., from v1.2.3 to v1.3.0)
gtm

# Create a new patch release (e.g., from v1.2.3 to v1.2.4)
gtp
\`\`\`

### Data Submodule (`data/`)
The data submodule is responsible for managing and processing studio data:
- **`studio_data.py`**: Provides functions to extract and represent data related to projects, sequences, shots, and tasks.
- **`_patterns.py`**: Contains common patterns or regular expressions used throughout the data handling routines.
- **`README.md`**: Offers documentation specific to the data handling aspects of the package.
- **`__init__.py`**: Serves as the initializer, allowing easy import of data functions.

## Deployment Scripts

The `deployment` directory contains configuration files and scripts for deploying your package. Key updates include:

- **New Release Structure**: When a project is released, the repository is cloned into a folder structure like:

  \`\`\`
  <PIPE_PATH>/<ProjectName>/releases/<version>/<project in lowercase>
  \`\`\`

  For example, releasing the **Fixfx** project at version **v1.1.6** will clone the repository into:

  \`\`\`
  Z:\pipe\Fixfx\releases\v1.1.6\fixfx
  \`\`\`

- **Staging vs. Releasing**:
  - The **stage** command clones the repository without updating metadata.
  - The **release** command clones the repository and then updates the metadata JSON file.

- **Rollback**: The rollback script uses the same folder structure to revert to a previous version.

For detailed usage of the deployment tools, see the dedicated README in the `deployment` directory.

## Running Unit Tests

To ensure everything is working correctly, unit tests are provided. You can run tests using Python’s built-in unittest module or pytest:

### Using Unittest

From the project root, run:

\`\`\`bash
python -m unittest discover tests
\`\`\`

### Using Pytest

If you have [pytest](https://docs.pytest.org/) installed, simply run:

\`\`\`bash
pytest
\`\`\`

## Development Environment Shortcuts

For quick navigation during development, several aliases are provided:

- `dev` – Change to the pipeline development directory.
- `devnuke` – Navigate to the Nuke development directory.
- `pipe` – Change to the central pipeline directory.

Ensure the appropriate scripts (e.g., `bin/fix-git.sh`) are sourced in your shell configuration.

---

For further details on deployment processes, please see the dedicated [fixfx.deployment README](deployment/README.md).

```

