"""Read-only HPC text file viewer core."""
from .viewer import FileViewer
from .policy import FilePolicy, ReadOnlyFileAccess, FileViewerError, FileChanged
__version__ = "0.1.0"
