def _get_core_tools():
    from sonika_ai_toolkit.tools.core import (
        RunBashTool,
        ReadFileTool,
        WriteFileTool,
        ListDirTool,
        DeleteFileTool,
        FindFileTool,
        CallApiTool,
        SearchWebTool,
    )
    return [
        RunBashTool,
        ReadFileTool,
        WriteFileTool,
        ListDirTool,
        DeleteFileTool,
        FindFileTool,
        CallApiTool,
        SearchWebTool,
    ]

def _get_integrations_tools():
    from sonika_ai_toolkit.tools.integrations import EmailTool, SaveContacto
    return [EmailTool, SaveContacto]

TOOL_GROUPS = {
    "core": _get_core_tools,
    "integrations": _get_integrations_tools,
}

__all__ = ["TOOL_GROUPS"]
