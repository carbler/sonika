# 🤖 Agent Directives & Developer Guide for Sonika

Welcome to the `sonika` repository. This file (`AGENTS.md`) serves as the definitive reference for AI coding agents (like Cursor, GitHub Copilot, Cline, or generic autonomous agents) and human developers working in this codebase. Read and follow these instructions carefully before proposing or applying any modifications.

## 📌 Project Overview
**Sonika** is an autonomous tool execution layer and CLI for AI orchestrators (built primarily with `langchain`, `typer`, and `sonika-ai-toolkit`).
* **Python Version:** 3.11+
* **Core Libraries:** `langchain`, `langchain-core`, `pydantic>=2.0`, `typer`, `rich`, `pytest-asyncio`.

---

## 🛠️ Environment Setup & Execution Commands

### **Installation**
Set up the environment using standard Python `venv` and install the package in editable mode with development dependencies.
```bash
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### **Testing Commands**
Testing is executed using `pytest`. The project uses `pytest-asyncio` for asynchronous tests.
* **Run all tests:** `pytest tests/`
* **Run a single test file:** `pytest tests/test_new_features.py -v`
* **Run a specific test function:** `pytest tests/test_new_features.py::test_my_feature_name -v`
* **Run tests with standard output (for debugging print statements):** `pytest tests/ -s`

*Agent Directive:* After implementing a new feature or fixing a bug, **always** run the relevant tests locally using the commands above to ensure your changes didn't break existing functionality. Do not assume your code works without running the test suite.

### **Linting & Code Formatting**
The codebase relies on `ruff` for fast linting and formatting, and `mypy` for static type checking.
* **Check Linting (Ruff):** `ruff check .`
* **Fix Linting Errors (Auto-fix):** `ruff check . --fix`
* **Format Code:** `ruff format .`
* **Type Checking:** `mypy sonika/`

### **Running the CLI**
To test CLI features manually:
* `sonika --help`
* `sonika start "prompt text" --model "gemini:gemini-3-flash-preview"`
* Or via module execution: `python -m sonika.cli`

---

## 🏗️ Code Style & Conventions

### **1. Language and Naming**
* **Code Language:** Source code, variables, classes, and internal logic should generally be in **English**.
* **User-Facing Text:** Docstrings describing class usage, CLI `help=""` arguments, and console outputs (`rich` prints) are primarily written in **Spanish**. Ensure you follow this mixed-language convention unless explicitly asked to do otherwise.
* **Naming:** 
  * `snake_case` for variables, functions, and module names (`load_prompts`, `executor_bot`).
  * `PascalCase` for classes, Pydantic models, and Dataclasses (`ExecutorBot`, `ExecutionResult`).
  * `UPPER_SNAKE_CASE` for global constants.
  * Prefix private or internal functions/variables with a single underscore (e.g., `_persistent_asyncio_run`).

### **2. Types & Data Structures**
* **Strict Typing:** All function signatures and class methods **must** include type hints. Return types must also be declared (e.g., `def run() -> None:`).
* Use `Optional`, `List`, `Dict`, `Any` from the `typing` module, or built-in generics natively supported by Python 3.11+.
* **Data Structures:** 
  * Use `dataclasses.dataclass` for lightweight internal return structures (like `ExecutionResult`).
  * Use Pydantic `BaseModel` when defining schemas for LLMs or strict external validation.

### **3. Imports**
Organize imports logically:
1. Standard Library (`os`, `sys`, `typing`, `asyncio`, `dataclasses`)
2. Third-Party Libraries (`typer`, `pydantic`, `langchain`, `rich`, `dotenv`)
3. Internal Sonika Tooling (`sonika_ai_toolkit.*`)
4. Local application imports using relative dot-notation (`from .bot import ExecutorBot`)

### **4. Error Handling & Asynchronous Code**
* **Exceptions:** Do not use bare `except:` or catch generic `Exception` unless strictly necessary for top-level logging boundaries. Catch specific exceptions.
* **Results:** Prefer returning structured result objects (like `ExecutionResult` which encapsulates success/failure without throwing exceptions across boundaries).
  * Example: `return ExecutionResult(success=False, output="", error=str(e))`
* **Asyncio:** The CLI relies on `asyncio`. Use `async def` and `await` for I/O operations (network, file system, LLM calls). 
* Notice the persistent event loop pattern in `cli.py` to prevent event loop closures across sequential asynchronous Typer command executions. Maintain this pattern when touching CLI entry points.

---

## 🔧 Architecture & Creating New Tools (`sonika/tools/`)

### **Core Components**
* **`cli.py`**: The Typer CLI application entry point. Handles arguments and asyncio setup.
* **`factory.py`**: Dependency injection and component wiring.
* **`bot.py`**: `ExecutorBot` class, the main execution layer consuming the Orchestrator.
* **`registry.py`**: `ToolRegistry` for managing available LangChain tools.
* **`result.py`**: `ExecutionResult` standard dataclass for returning tool execution outcomes.

### **How to Create a New Tool**
When creating a new tool for the AI execution layer:
1. **Inheritance:** Your tool must inherit from `sonika.tools.base.BaseTool` (which extends LangChain's `BaseTool`).
2. **Implementation:** 
   * Implement the synchronous `_run(self, *args, **kwargs) -> Any` method.
   * Optionally implement the asynchronous `_arun(self, *args, **kwargs) -> Any` method if the tool performs I/O operations.
3. **Risk Levels:** Define the `risk_level` attribute:
   * `0`: Safe (read-only)
   * `1`: Side effects (e.g., write files, make API calls)
   * `2`: Destructive (e.g., delete resources)
4. **Documentation:** Provide clear docstrings. LangChain relies heavily on the class docstring and the Pydantic `args_schema` to route the agent appropriately.

---

## 🤖 General Agent Instructions (Cursor, Copilot, Cline, etc.)

* **Understand Before Modifying:** Do not assume the existence of a framework or library that is not in `pyproject.toml` or `requirements.txt`. Always verify imports.
* **Respect the Architecture:** Do not rewrite large chunks of the system blindly. Conform to the established `langchain` + `sonika-ai-toolkit` wrapper patterns. 
* **Self-Verification:** If asked to fix a bug, locate the relevant file, construct a plan, write/update the failing test *first*, apply the fix, run the test (using `pytest`), and ensure it passes before finalizing the task.
* **Minimal Edits:** Focus exclusively on the files and lines necessary to complete the user's objective. Do not "clean up" unrelated files during a targeted fix unless specifically asked.
