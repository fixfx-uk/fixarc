# fixarc/exceptions.py
"""Custom exception classes for the Fix Archive (fixarc) tool."""

# Use fixfx base exception if available, otherwise standard Exception
try:
    # Attempt to import from fixfx.core, assuming fixfx is installed correctly
    from fixfx.core.exceptions import FixFXException
    _BaseException = FixFXException
    _uses_fixfx_base = True
except ImportError:
    # Fallback to standard Python Exception if fixfx is not available
    _BaseException = Exception
    _uses_fixfx_base = False


class ArchiveError(_BaseException):
    """Base class for fixarc specific errors."""
    # Add logger integration if using fixfx base and desired
    # def __init__(self, message: str, *args: object) -> None:
    #     if _uses_fixfx_base:
    #         # Requires logger to be accessible, might need adjustment
    #         # from . import log # Assuming log is available? Risky import here.
    #         # log.error(f"{self.__class__.__name__}: {message}")
    #         super().__init__(message, *args) # Pass message to fixfx base
    #     else:
    #         super().__init__(message, *args)
    pass # Keep it simple for now

class ParsingError(ArchiveError):
    """Error during Nuke script parsing or manifest processing."""
    pass

class DependencyError(ArchiveError):
    """Error related to finding or validating dependencies (missing files/sequences)."""
    pass

class ArchiverError(ArchiveError):
    """Error during the file archiving process (copying, structure creation)."""
    pass

class RepathingError(ArchiveError):
    """Error during the script repathing process."""
    pass

class GizmoError(ArchiveError):
    """Error during the gizmo baking process."""
    pass

class ConfigurationError(ArchiveError):
    """Error related to invalid configuration, arguments, or environment setup."""
    pass

class PruningError(ArchiveError):
    """Error during the script pruning (node identification or saving) process."""
    pass

class NukeExecutionError(ArchiveError):
    """Error specifically related to the execution of the Nuke subprocess."""
    pass