from .bash import BashTool, BashSafeTool
from .files import ReadFileTool, WriteFileTool, ListDirTool
from .http import HttpRequestTool

# Mapeo de grupos de tools para carga fácil
TOOL_GROUPS = {
    "bash": [BashTool],
    "bash_safe": [BashSafeTool],
    "files": [ReadFileTool, WriteFileTool, ListDirTool],
    "http": [HttpRequestTool],
}

__all__ = [
    "BashTool", "BashSafeTool",
    "ReadFileTool", "WriteFileTool", "ListDirTool",
    "HttpRequestTool",
    "TOOL_GROUPS"
]
