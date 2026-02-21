import os
import sys
from typing import Optional, TYPE_CHECKING, Callable
from dotenv import set_key

if TYPE_CHECKING:
    from sonika_ai_toolkit.agents.orchestrator.graph import OrchestratorBot
    from sonika_ai_toolkit.agents.orchestrator.prompts import OrchestratorPrompts
    from sonika_ai_toolkit.utilities.types import ILanguageModel

from .bot import ExecutorBot
from .interfaces.console.ui import console, ask_secret, ask_confirm

def load_prompts(prompts_dir: Optional[str] = None) -> "OrchestratorPrompts":
    from sonika_ai_toolkit.agents.orchestrator.prompts import OrchestratorPrompts
    if prompts_dir is None:
        prompts_dir = os.path.join(os.path.dirname(__file__), "prompts")
    prompts_dir = os.path.abspath(prompts_dir)
    
    prompt_files = {
        "core": "core.txt",
        "manager": "manager.txt",
        "planner": "planner.txt",
        "evaluator": "evaluator.txt",
        "retry": "retry.txt",
        "reporter": "reporter.txt",
        "save_memory": "save_memory.txt",
    }
    
    loaded = {}
    for key, filename in prompt_files.items():
        filepath = os.path.join(prompts_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                loaded[key] = f.read()
    return OrchestratorPrompts(**loaded)

def get_model(provider: str, model_name: str) -> "ILanguageModel":
    from sonika_ai_toolkit.utilities.models import (
        OpenAILanguageModel,
        DeepSeekLanguageModel,
        GeminiLanguageModel,
    )
    env_key = f"{provider.upper()}_API_KEY"
    if provider in ("gemini", "google"):
        env_key = "GOOGLE_API_KEY"

    api_key = os.getenv(env_key)

    if not api_key:
        if not sys.stdin.isatty():
            console.print(f"[bold red]❌ {env_key} no encontrada en el entorno.[/bold red]")
            sys.exit(1)
        console.print(f"[bold red]❌ {env_key} no encontrada.[/bold red]")
        if ask_confirm(f"¿Ingresar tu API Key de {provider} ahora?"):
            api_key = ask_secret(f"API Key de {provider}")
            if api_key:
                env_path = os.path.join(os.getcwd(), ".env")
                if not os.path.exists(env_path):
                    open(env_path, "a").close()
                set_key(env_path, env_key, api_key)
                os.environ[env_key] = api_key
                console.print(f"[green]Guardada en {env_path}[/green]")
            else:
                console.print("[red]API Key requerida.[/red]")
                sys.exit(1)
        else:
            sys.exit(1)

    if provider == "openai":
        return OpenAILanguageModel(api_key, model_name=model_name)
    elif provider == "deepseek":
        return DeepSeekLanguageModel(api_key)
    elif provider in ("gemini", "google"):
        try:
            return GeminiLanguageModel(api_key, model_name=model_name)
        except TypeError:
            return GeminiLanguageModel(api_key)
    else:
        raise ValueError(f"Proveedor desconocido: {provider}")


def create_orchestrator(
    provider: str,
    model_name: str,
    risk_level: int,
    session_id: str,
    prompts_dir: Optional[str] = None,
) -> "OrchestratorBot":
    from sonika_ai_toolkit.agents.orchestrator.graph import OrchestratorBot

    model = get_model(provider, model_name)

    # Use sonika's own tools plus the toolkit core groups
    executor = ExecutorBot(tools=["bash", "files", "http", "integrations", "core"], sandbox=True)
    raw_tools = executor.registry.get_tools()

    # The new LangGraph Orchestrator natively supports Interrupts and risk levels,
    # so we no longer need PermissionAwareTool wrappers.
    tools = raw_tools

    instructions = (
        "You are Sonika CLI (ExecutorBot Edition). "
        "Use provided tools to execute precise coding and system tasks. "
        "Always reason before acting. If you modify files, verify changes."
    )

    memory_base = os.path.expanduser("~/.sonika/memory")
    session_path = os.path.join(memory_base, session_id)
    os.makedirs(session_path, exist_ok=True)

    prompts = load_prompts(prompts_dir)

    return OrchestratorBot(
        strong_model=model,
        fast_model=model,
        instructions=instructions,
        tools=tools,
        risk_threshold=risk_level,
        memory_path=session_path,
        prompts=prompts
    )
