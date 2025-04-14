"""Custom exceptions for the Fix Archive tool."""

# Use fixfx base exception if available, otherwise standard Exception
try:
    # Attempt to import from fixfx.core, assuming fixfx is installed correctly
    from fixfx.core.exceptions import FixFXException
    _BaseException = FixFXException
    # If using fixfx's logger integration in exceptions, ensure logger is passed or accessible
    # For simplicity here, we won't automatically log within these exceptions, rely on calling code.
except ImportError:
    # Fallback to standard Python Exception if fixfx is not available
    _BaseException = Exception


class ArchiveError(_BaseException):
    """Base class for fix-archive specific errors."""
    pass

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
