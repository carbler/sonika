import os
import glob
from typing import Optional, Type, List
from pydantic import BaseModel, Field
from .base import BaseTool

# --- Read File ---
class ReadFileInput(BaseModel):
    file_path: str = Field(description="Path to the file to read")

class ReadFileTool(BaseTool):
    name: str = "read_file"
    description: str = "Read a file and return its contents."
    args_schema: Type[BaseModel] = ReadFileInput
    risk_level: int = 0

    def preview(self, params: dict) -> str:
        file_path = params.get("file_path", "")
        content = params.get("content", "")
        if not os.path.exists(file_path):
            return f"+++ {file_path}\n{content}"
        with open(file_path, "r", encoding="utf-8") as f:
            old_content = f.read()
        import difflib
        diff = difflib.unified_diff(
            old_content.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=file_path,
            tofile=file_path
        )
        return "".join(diff)

    def _run(self, file_path: str) -> str:
        try:
            if not os.path.exists(file_path):
                return f"ERROR: File not found: {file_path}"
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return f"ERROR: Could not read file: {str(e)}"

# --- Write File ---
class WriteFileInput(BaseModel):
    file_path: str = Field(description="Path to the file to write")
    content: str = Field(description="Content to write to the file")

class WriteFileTool(BaseTool):
    name: str = "write_file"
    description: str = "Write content to a file. Overwrites if exists. Creates directories if needed."
    args_schema: Type[BaseModel] = WriteFileInput
    risk_level: int = 1

    def preview(self, params: dict) -> str:
        file_path = params.get("file_path", "")
        content = params.get("content", "")
        if not os.path.exists(file_path):
            return f"+++ {file_path}\n{content}"
        with open(file_path, "r", encoding="utf-8") as f:
            old_content = f.read()
        import difflib
        diff = difflib.unified_diff(
            old_content.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=file_path,
            tofile=file_path
        )
        return "".join(diff)

    def _run(self, file_path: str, content: str) -> str:
        try:
            # Crear directorios si no existen
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
                
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote to {file_path}"
        except Exception as e:
            return f"ERROR: Could not write file: {str(e)}"

# --- List Dir ---
class ListDirInput(BaseModel):
    path: str = Field(description="Directory path to list")

class ListDirTool(BaseTool):
    name: str = "list_dir"
    description: str = "List files and directories at a given path."
    args_schema: Type[BaseModel] = ListDirInput
    risk_level: int = 0

    def preview(self, params: dict) -> str:
        file_path = params.get("file_path", "")
        content = params.get("content", "")
        if not os.path.exists(file_path):
            return f"+++ {file_path}\n{content}"
        with open(file_path, "r", encoding="utf-8") as f:
            old_content = f.read()
        import difflib
        diff = difflib.unified_diff(
            old_content.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=file_path,
            tofile=file_path
        )
        return "".join(diff)

    def _run(self, path: str) -> str:
        try:
            if not os.path.exists(path):
                return f"ERROR: Path not found: {path}"
                
            files = os.listdir(path)
            return "\n".join(files)
        except Exception as e:
            return f"ERROR: Could not list directory: {str(e)}"
