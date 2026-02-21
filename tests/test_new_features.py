import pytest
import time
import subprocess
from sonika.permissions import PermissionManager, PermissionMode
from sonika.tools.wrapper import PermissionAwareTool
from langchain_core.tools import BaseTool

class MockTool(BaseTool):
    name: str = "mock"
    description: str = "desc"
    def _run(self, x: int):
        return "executed"

def test_startup_speed():
    start = time.time()
    subprocess.run(["sonika", "--help"], capture_output=True, check=True)
    duration = time.time() - start
    assert duration < 1.0, f"Startup took {duration:.2f}s, expected < 1.0s"

def test_permission_modes():
    pm = PermissionManager(PermissionMode.ASK)
    assert pm.current_mode == PermissionMode.ASK
    assert pm.should_ask() is True
    assert pm.should_execute() is True
    
    pm.cycle_mode() # -> AUTO
    assert pm.current_mode == PermissionMode.AUTO
    assert pm.should_ask() is False
    assert pm.should_execute() is True
    
    pm.cycle_mode() # -> PLAN
    assert pm.current_mode == PermissionMode.PLAN
    assert pm.should_ask() is False
    assert pm.should_execute() is False

def test_permission_aware_tool_ask():
    mock_tool = MockTool()
    pm = PermissionManager(PermissionMode.ASK)
    
    was_asked = False
    def ask_callback(name, params):
        nonlocal was_asked
        was_asked = True
        return True # Allowed
    
    wrapped = PermissionAwareTool(mock_tool, pm, ask_callback)
    
    result = wrapped.invoke({"x": 1})
    assert was_asked
    assert result == "executed"

def test_permission_aware_tool_deny():
    mock_tool = MockTool()
    pm = PermissionManager(PermissionMode.ASK)
    
    def ask_callback(name, params):
        return False # Denied
    
    wrapped = PermissionAwareTool(mock_tool, pm, ask_callback)
    
    result = wrapped.invoke({"x": 1})
    assert "denied" in result
    assert result != "executed"

def test_permission_aware_tool_plan():
    mock_tool = MockTool()
    pm = PermissionManager(PermissionMode.PLAN)
    
    wrapped = PermissionAwareTool(mock_tool, pm, lambda n,p: True)
    
    result = wrapped.invoke({"x": 1})
    assert "PLAN MODE" in result
    assert result != "executed"

def test_permission_aware_tool_auto():
    mock_tool = MockTool()
    pm = PermissionManager(PermissionMode.AUTO)
    
    was_asked = False
    def ask_callback(name, params):
        nonlocal was_asked
        was_asked = True
        return True
    
    wrapped = PermissionAwareTool(mock_tool, pm, ask_callback)
    
    result = wrapped.invoke({"x": 1})
    assert not was_asked
    assert result == "executed"
