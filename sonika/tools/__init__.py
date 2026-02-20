from .bash import BashTool, BashSafeTool
from .files import ReadFileTool, WriteFileTool, ListDirTool
from .http import HttpRequestTool
from sonika_ai_toolkit.tools.integrations import EmailTool, SaveContacto
from sonika_ai_toolkit.tools.core import (
    RunBashTool,
    ReadFileTool as CoreReadFileTool,
    WriteFileTool as CoreWriteFileTool,
    ListDirTool as CoreListDirTool,
    DeleteFileTool,
    CallApiTool,
    SearchWebTool
)

# Mapeo de grupos de tools para carga fácil
TOOL_GROUPS = {
    "bash": [BashTool],
    "bash_safe": [BashSafeTool],
    "files": [ReadFileTool, WriteFileTool, ListDirTool],
    "http": [HttpRequestTool],
    "integrations": [EmailTool, SaveContacto],
    "core": [
        RunBashTool,
        CoreReadFileTool,
        CoreWriteFileTool,
        CoreListDirTool,
        DeleteFileTool,
        CallApiTool,
        SearchWebTool
    ]
}

__all__ = [
    "BashTool", "BashSafeTool",
    "ReadFileTool", "WriteFileTool", "ListDirTool",
    "HttpRequestTool",
    "EmailTool", "SaveContacto",
    "RunBashTool", "DeleteFileTool", "CallApiTool", "SearchWebTool",
    "TOOL_GROUPS"
]
