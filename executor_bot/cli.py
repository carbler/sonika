import typer
import sys
import os
import time
from typing import Optional, List, Dict
from dotenv import load_dotenv, set_key
from rich.console import Console
from rich.live import Live

from .bot import ExecutorBot
from .ui import (
    console,
    ExecutionDisplay,
    print_welcome,
    print_result,
    ask_secret,
    ask_confirm
)

# Importaciones de Sonika
from sonika_ai_toolkit.agents.orchestrator.graph import OrchestratorBot
from sonika_ai_toolkit.utilities.models import OpenAILanguageModel, DeepSeekLanguageModel, GeminiLanguageModel
from sonika_ai_toolkit.utilities.types import BotResponse, ILanguageModel

app = typer.Typer()
load_dotenv()

# --- Callbacks para Live Rendering ---
display: Optional[ExecutionDisplay] = None

def _on_thinking(chunk: str):
    """Callback para mostrar razonamiento en tiempo real."""
    if display:
        display.update_thinking(chunk)

def _on_step_start(step: Dict):
    """Callback para mostrar cuando una herramienta se invoca."""
    if display:
        tool_name = step.get("tool_name", "unknown")
        params = str(step.get("params", ""))
        display.add_step(tool_name, params)

def _on_step_end(step: Dict, output: str):
    """Callback para mostrar cuando una herramienta termina."""
    if display:
        status = step.get("status", "unknown")
        # En Sonika, 'status' se actualiza a 'success'/'error' antes de llamar al callback
        error = output.startswith("ERROR:") or "Error:" in output[:20]
        display.complete_step(output, error=error)


# --- Factory de Modelos ---

def get_model(provider: str, model_name: str) -> ILanguageModel:
    """Instancia el modelo según el proveedor y gestiona API Keys."""
    env_key = f"{provider.upper()}_API_KEY"
    
    # Estandarizar Gemini/Google -> GOOGLE_API_KEY
    if provider in ("gemini", "google"):
        env_key = "GOOGLE_API_KEY"
    
    api_key = os.getenv(env_key)

    if not api_key:
        # Check interactivity
        if not sys.stdin.isatty():
             # Non-interactive mode fallback
             console.print(f"[bold red]❌ {env_key} not found in environment![/bold red]")
             sys.exit(1)
             
        console.print(f"[bold red]❌ {env_key} not found![/bold red]")
        if ask_confirm(f"Do you want to enter your {provider} API Key now?"):
            api_key = ask_secret(f"Enter {provider} API Key")
            if api_key:
                # Guardar en .env para el futuro
                env_path = os.path.join(os.getcwd(), ".env")
                if not os.path.exists(env_path):
                    open(env_path, 'a').close()
                set_key(env_path, env_key, api_key)
                os.environ[env_key] = api_key # Update runtime env
                console.print(f"[green]Saved to {env_path}[/green]")
            else:
                console.print("[red]API Key is required.[/red]")
                sys.exit(1)
        else:
            sys.exit(1)

    if provider == "openai":
        return OpenAILanguageModel(api_key, model_name=model_name)
    elif provider == "deepseek":
        return DeepSeekLanguageModel(api_key) 
    elif provider in ("gemini", "google"):
        # Intentamos pasar model_name, si falla capturamos
        try:
            return GeminiLanguageModel(api_key, model_name=model_name)
        except TypeError:
            # Fallback si el constructor no acepta model_name
            return GeminiLanguageModel(api_key)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def create_orchestrator(
    provider: str, 
    model_name: str, 
    risk_level: int,
    session_id: str
) -> OrchestratorBot:
    """Initialize Sonika Orchestrator with ExecutorBot's safe tools."""
    
    # 1. Configurar Modelo
    model = get_model(provider, model_name)
    
    # 2. Inicializar ExecutorBot (Capa de herramientas)
    executor = ExecutorBot(
        tools=["bash", "files", "http"],
        sandbox=True,  
    )
    tools = executor.registry.get_tools()
    
    # 3. Prompt de Sistema
    instructions = (
        "You are OpenCode (ExecutorBot Edition). "
        "Use provided tools to execute precise coding and system tasks. "
        "Always reason before acting. If you modify files, verify changes."
    )

    # 4. Inicializar Orquestador
    memory_base = os.path.expanduser("~/.executor_bot/memory")
    session_path = os.path.join(memory_base, session_id)
    os.makedirs(session_path, exist_ok=True)

    bot = OrchestratorBot(
        strong_model=model,
        fast_model=model,
        instructions=instructions,
        tools=tools,
        risk_threshold=risk_level,
        memory_path=session_path,
        on_thinking=_on_thinking,
        on_step_start=_on_step_start,
        on_step_end=_on_step_end,
    )
    
    return bot


@app.command()
def start(
    prompt: Optional[str] = typer.Argument(None, help="Initial prompt"),
    model: str = typer.Option("openai:gpt-4o", help="Model to use (provider:model_name) e.g., gemini:gemini-pro"),
    risk: int = typer.Option(2, help="Risk threshold (0=Safe, 1=SideEffects, 2=Destructive)"),
    session: str = typer.Option("default", help="Session ID to persist context"),
):
    """Start the interactive AI session."""
    global display
    
    print_welcome()
    
    # Parsear modelo
    if ":" in model:
        provider, model_name = model.split(":", 1)
    else:
        provider, model_name = model, "default"
        
    try:
        console.print(f"[dim]Initializing {provider}/{model_name} (Session: {session})...[/dim]")
        bot = create_orchestrator(provider, model_name, risk, session)
    except Exception as e:
        console.print(f"[bold red]Initialization failed:[/bold red] {e}")
        return

    # Historial de chat en memoria
    chat_context = ""

    # Función interna para ejecutar una interacción
    def run_turn(user_msg: str):
        nonlocal chat_context
        start_time = time.time()
        
        # Iniciar UI Live
        global display
        display = ExecutionDisplay()
        display.start() 
        
        try:
            # Construir prompt con contexto previo
            full_goal = f"Context:\n{chat_context}\n\nCurrent Task:\n{user_msg}"
            
            # Ejecutar
            result = bot.run(full_goal)
            
            # Procesar resultado
            content = getattr(result, "content", "")
            success = getattr(result, "success", False)
            
            # Actualizar historial
            chat_context += f"\nUser: {user_msg}\nAssistant: {content}\n"
            
            duration = time.time() - start_time
            return content, success, duration

        except Exception as e:
            duration = time.time() - start_time
            return f"Error: {str(e)}", False, duration
        finally:
            if display:
                display.stop()
                display = None

    # Si hay prompt inicial
    if prompt:
        content, success, duration = run_turn(prompt)
        print_result(content)
        console.print(f"[dim italic]⏱️ Executed in {duration:.2f}s[/dim italic]")

    # Bucle interactivo
    while True:
        try:
            from rich.prompt import Prompt as RichPrompt
            user_input = RichPrompt.ask("\n[bold cyan]>>>[/bold cyan]")
            
            if user_input.lower() in ("/exit", "exit", "quit"):
                console.print("[yellow]Goodbye![/yellow]")
                break
            
            if not user_input.strip():
                continue

            content, success, duration = run_turn(user_input)
            print_result(content)
            console.print(f"[dim italic]⏱️ Executed in {duration:.2f}s[/dim italic]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Type /exit to quit.[/yellow]")
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            import traceback
            console.print(traceback.format_exc())

if __name__ == "__main__":
    app()
