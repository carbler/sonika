import subprocess
import os
from typing import Optional, Type, List
from pydantic import BaseModel, Field
from .base import BaseTool

class BashInput(BaseModel):
    command: str = Field(description="The bash command to execute")
    workdir: Optional[str] = Field(default=None, description="Working directory for the command")
    timeout: Optional[int] = Field(default=30, description="Timeout in seconds")

class BashTool(BaseTool):
    name: str = "run_bash"
    description: str = """
    Execute a shell command. Returns stdout + stderr combined.
    Use for: file operations, running scripts, checking system state.
    """
    args_schema: Type[BaseModel] = BashInput
    risk_level: int = 1

    def _run(self, command: str, workdir: Optional[str] = None, timeout: int = 30) -> str:
        try:
            cwd = workdir if workdir else os.getcwd()
            
            # Ejecución segura con subprocess
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
                
            if result.returncode != 0:
                output += f"\n[Process exited with code {result.returncode}]"
                
            return output.strip()
            
        except subprocess.TimeoutExpired:
            return f"ERROR: Command timed out after {timeout} seconds"
        except Exception as e:
            return f"ERROR: Failed to execute command: {str(e)}"

class BashSafeTool(BashTool):
    """
    Versión restringida de Bash que bloquea comandos peligrosos comunes.
    """
    name: str = "run_bash_safe"
    risk_level: int = 0
    
    FORBIDDEN: List[str] = ["rm", "sudo", "mv", "dd", "mkfs", ":(){:|:&};:"]

    def _run(self, command: str, workdir: Optional[str] = None, timeout: int = 30) -> str:
        cmd_parts = command.split()
        if any(part in self.FORBIDDEN for part in cmd_parts):
             return f"ERROR: Command '{command}' contains forbidden operations in safe mode."
        
        return super()._run(command, workdir, timeout)
