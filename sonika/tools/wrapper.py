from typing import Any, Dict, Optional, Callable
from langchain_core.tools import BaseTool
from pydantic import PrivateAttr

from sonika.permissions import PermissionManager, PermissionMode

class PermissionAwareTool(BaseTool):
    """
    Wraps a tool to add permission checks before execution.
    """
    _wrapped_tool: BaseTool = PrivateAttr()
    _permission_manager: PermissionManager = PrivateAttr()
    _ask_callback: Callable[[str, Dict[str, Any]], bool] = PrivateAttr()

    def __init__(
        self, 
        tool: BaseTool, 
        permission_manager: PermissionManager,
        ask_callback: Callable[[str, Dict[str, Any]], bool]
    ):
        super().__init__(
            name=tool.name,
            description=tool.description,
            args_schema=tool.args_schema,
            return_direct=tool.return_direct,
        )
        self._wrapped_tool = tool
        self._permission_manager = permission_manager
        self._ask_callback = ask_callback

    def _run(self, *args, **kwargs) -> Any:
        mode = self._permission_manager.current_mode
        
        # Merge args and kwargs into a single params dict for display
        # This is simplified; robust arg parsing depends on args_schema
        params = kwargs.copy()
        if args:
            params["args"] = args

        if mode == PermissionMode.PLAN:
            return f"[PLAN MODE] Tool '{self.name}' call simulated. Params: {params}"
        
        if mode == PermissionMode.ASK:
            allowed = self._ask_callback(self.name, params)
            if not allowed:
                return f"Tool execution denied by user."
        
        # Execute the wrapped tool
        return self._wrapped_tool._run(*args, **kwargs)

    async def _arun(self, *args, **kwargs) -> Any:
        # For now, just delegate to sync run if async not supported by wrapper logic
        # Ideally we should support async prompt
        return self._run(*args, **kwargs)
