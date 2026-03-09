def _get_core_tools():
    from sonika_ai_toolkit.tools.core import (
        RunBashTool,
        BashSafeTool,
        ReadFileTool,
        WriteFileTool,
        ListDirTool,
        DeleteFileTool,
        FindFileTool,
        CallApiTool,
        SearchWebTool,
        RunPythonTool,
        FetchWebPageTool,
        GetDateTimeTool,
        EmailSMTPTool,
        SQLiteTool,
        PostgreSQLTool,
        MySQLTool,
        RedisTool,
    )
    return [
        RunBashTool,
        BashSafeTool,
        ReadFileTool,
        WriteFileTool,
        ListDirTool,
        DeleteFileTool,
        FindFileTool,
        CallApiTool,
        SearchWebTool,
        RunPythonTool,
        FetchWebPageTool,
        GetDateTimeTool,
        EmailSMTPTool,
        SQLiteTool,
        PostgreSQLTool,
        MySQLTool,
        RedisTool,
    ]

def _get_integrations_tools():
    from sonika_ai_toolkit.tools.integrations import EmailTool, SaveContacto
    return [EmailTool, SaveContacto]

def _get_scheduler_tools():
    from sonika.tools.cron import CronTool
    return [CronTool]


TOOL_GROUPS = {
    "core": _get_core_tools,
    "integrations": _get_integrations_tools,
    "scheduler": _get_scheduler_tools,
}


def register_tool_group(name: str, loader):
    """Register a custom tool group loader (callable returning list of tool classes)."""
    TOOL_GROUPS[name] = loader


__all__ = ["TOOL_GROUPS", "register_tool_group"]
