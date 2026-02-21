def _get_bash_tools():
    from .bash import BashTool
    return [BashTool]

def _get_bash_safe_tools():
    from .bash import BashSafeTool
    return [BashSafeTool]

def _get_files_tools():
    from .files import ReadFileTool, WriteFileTool, ListDirTool
    return [ReadFileTool, WriteFileTool, ListDirTool]

def _get_http_tools():
    from .http import HttpRequestTool
    return [HttpRequestTool]

def _get_integrations_tools():
    from sonika_ai_toolkit.tools.integrations import EmailTool, SaveContacto
    return [EmailTool, SaveContacto]

def _get_core_tools():
    from sonika_ai_toolkit.tools.core import (
        RunBashTool,
        ReadFileTool as CoreReadFileTool,
        WriteFileTool as CoreWriteFileTool,
        ListDirTool as CoreListDirTool,
        DeleteFileTool,
        CallApiTool,
        SearchWebTool
    )
    return [
        RunBashTool,
        CoreReadFileTool,
        CoreWriteFileTool,
        CoreListDirTool,
        DeleteFileTool,
        CallApiTool,
        SearchWebTool
    ]

# Mapeo de grupos de tools para carga fácil (ahora perezosa)
TOOL_GROUPS = {
    "bash": _get_bash_tools,
    "bash_safe": _get_bash_safe_tools,
    "files": _get_files_tools,
    "http": _get_http_tools,
    "integrations": _get_integrations_tools,
    "core": _get_core_tools,
}

__all__ = ["TOOL_GROUPS"]
