import typer
import sys
import os
import time
import asyncio as _asyncio
from typing import Optional, Dict
from dotenv import load_dotenv, set_key

# Fix: reuse a persistent event loop across bot.run() calls to avoid gRPC
# channel incompatibility. asyncio.run() closes the loop after each call,
# but ChatGoogleGenerativeAI's gRPC channel is bound to the first loop and
# fails when a new loop is created on subsequent turns.
_persistent_loop = _asyncio.new_event_loop()
_asyncio.set_event_loop(_persistent_loop)

def _persistent_asyncio_run(coro, *, debug=None):
    global _persistent_loop
    if _persistent_loop.is_closed():
        _persistent_loop = _asyncio.new_event_loop()
        _asyncio.set_event_loop(_persistent_loop)
    return _persistent_loop.run_until_complete(coro)

_asyncio.run = _persistent_asyncio_run

from .bot import ExecutorBot
from .ui import (
    console,
    ExecutionDisplay,
    print_welcome,
    print_result,
    print_model_info,
    ask_secret,
    ask_confirm,
)

# Importaciones de Sonika
from sonika_ai_toolkit.agents.orchestrator.graph import OrchestratorBot
from sonika_ai_toolkit.agents.orchestrator.prompts import OrchestratorPrompts
from sonika_ai_toolkit.utilities.models import (
    OpenAILanguageModel,
    DeepSeekLanguageModel,
    GeminiLanguageModel,
)
from sonika_ai_toolkit.utilities.types import ILanguageModel

app = typer.Typer()
load_dotenv()

# ── Callbacks de display ────────────────────────────────────────────────────
display: Optional[ExecutionDisplay] = None

def _on_thinking(chunk: str):
    if display:
        display.update_thinking(chunk)

def _on_message(text: str):
    """Muestra mensajes directos del bot (ej: explicaciones del manager)."""
    console.print(f"\n[bold cyan]Sonika:[/bold cyan] {text}")

def _on_step_start(step: Dict):
    if display:
        display.add_step(step.get("tool_name", "unknown"), str(step.get("params", "")))

def _on_step_end(step: Dict, output: str):
    if display:
        error = output.startswith("ERROR:") or "Error:" in output[:20]
        display.complete_step(output, error=error)


# ── Cargar prompts desde archivos ────────────────────────────────────────────

def load_prompts(prompts_dir: str = None) -> OrchestratorPrompts:
    """Carga prompts personalizados desde archivos en prompts_dir."""
    if prompts_dir is None:
        prompts_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")
    
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


# ── Factory de modelos ──────────────────────────────────────────────────────

def get_model(provider: str, model_name: str) -> ILanguageModel:
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
    prompts_dir: str = None,
) -> OrchestratorBot:
    model = get_model(provider, model_name)

    executor = ExecutorBot(tools=["bash", "files", "http", "integrations", "core"], sandbox=True)
    tools = executor.registry.get_tools()

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
        prompts=prompts,
        on_thinking=_on_thinking,
        on_message=_on_message,
        on_step_start=_on_step_start,
        on_step_end=_on_step_end,
    )


# ── CLI ─────────────────────────────────────────────────────────────────────

@app.command()
def start(
    prompt:  Optional[str] = typer.Argument(None, help="Prompt inicial"),
    model:   str = typer.Option(
        "gemini:gemini-3-flash-preview",
        help="Modelo a usar (provider:nombre)  ej: gemini:gemini-3-flash-preview",
    ),
    risk:    int = typer.Option(2, help="Umbral de riesgo (0=Seguro, 1=Efectos, 2=Destructivo)"),
    session: str = typer.Option("default", help="ID de sesión para persistir contexto"),
    prompts: Optional[str] = typer.Option(None, help="Directorio con prompts personalizados"),
):
    """Inicia la sesión interactiva con el agente."""
    global display

    # Parsear modelo
    if ":" in model:
        provider, model_name = model.split(":", 1)
    else:
        provider, model_name = model, "default"

    print_welcome(f"{provider}:{model_name}")

    try:
        console.print(f"[dim]Inicializando {provider}/{model_name} (sesión: {session})…[/dim]")
        bot = create_orchestrator(provider, model_name, risk, session, prompts)
    except Exception as e:
        console.print(f"[bold red]Error de inicialización:[/bold red] {e}")
        return

    chat_context = ""

    # ── ejecución de un turno ──────────────────────────────────────────────
    def run_turn(user_msg: str):
        nonlocal chat_context
        global display
        t0 = time.time()

        display = ExecutionDisplay()
        display.start()
        try:
            full_goal = f"Context:\n{chat_context}\n\nCurrent Task:\n{user_msg}"
            result    = bot.run(full_goal)
            content   = getattr(result, "content", "")
            chat_context += f"\nUser: {user_msg}\nAssistant: {content}\n"
            return content, time.time() - t0
        except Exception as e:
            return f"Error: {e}", time.time() - t0
        finally:
            if display:
                display.stop()
                display = None

    # ── prompt inicial opcional ────────────────────────────────────────────
    if prompt:
        content, duration = run_turn(prompt)
        print_result(content)
        console.print(f"[dim]⏱ {duration:.2f}s[/dim]")

    # ── bucle interactivo ──────────────────────────────────────────────────
    from rich.prompt import Prompt as RichPrompt

    while True:
        try:
            user_input = RichPrompt.ask(
                f"\n[bold cyan]Sonika:[/bold cyan] [dim]{provider}:{model_name}[/dim]"
            )

            # ── salir ──────────────────────────────────────────────────────
            if user_input.lower() in ("/exit", "exit", "quit", "q"):
                console.print("[yellow]Hasta luego.[/yellow]")
                break

            if not user_input.strip():
                continue

            # ── /help ──────────────────────────────────────────────────────
            if user_input.strip() == "/help":
                console.print(
                    "\n[bold cyan]Comandos disponibles:[/bold cyan]\n"
                    "  [bold]/model [provider:nombre][/bold]  — ver o cambiar modelo\n"
                    "  [bold]/modelos[/bold]                  — listar modelos recomendados\n"
                    "  [bold]/sesion[/bold]                   — ver sesión activa\n"
                    "  [bold]/exit[/bold]  o  [bold]exit[/bold]             — salir\n"
                )
                continue

            # ── /sesion ────────────────────────────────────────────────────
            if user_input.strip() == "/sesion":
                console.print(
                    f"\n  [cyan]Sesión:[/cyan] [bold]{session}[/bold]  "
                    f"[dim](~/.sonika/memory/{session}/)[/dim]"
                )
                continue

            # ── /modelos ───────────────────────────────────────────────────
            if user_input.strip() == "/modelos":
                console.print(
                    "\n[bold cyan]Modelos Gemini disponibles:[/bold cyan]\n"
                    "  [green]gemini:gemini-3-flash-preview[/green]    [dim]más nuevo · rápido · razonamiento[/dim]\n"
                    "  [green]gemini:gemini-3.1-pro-preview[/green]    [dim]más potente · razonamiento avanzado[/dim]\n"
                    "  [green]gemini:gemini-2.5-flash[/green]          [dim]rápido · razonamiento visible[/dim]\n"
                    "  [green]gemini:gemini-2.5-pro[/green]            [dim]potente · razonamiento visible[/dim]\n"
                    "\n[bold cyan]Otros proveedores:[/bold cyan]\n"
                    "  openai:gpt-4o  ·  openai:gpt-4o-mini\n"
                    "  deepseek:deepseek-reasoner  ·  deepseek:deepseek-chat\n"
                )
                continue

            # ── /model [nuevo] ─────────────────────────────────────────────
            if user_input.strip().startswith("/model"):
                parts = user_input.strip().split(maxsplit=1)

                if len(parts) == 1:
                    # Sin argumento → mostrar modelo actual
                    print_model_info(provider, model_name)
                    continue

                new_str = parts[1].strip()
                if ":" not in new_str:
                    console.print(
                        "[red]Formato inválido.[/red] Usa: [bold]/model provider:nombre[/bold]\n"
                        "[dim]Ej: /model gemini:gemini-3-flash-preview[/dim]"
                    )
                    continue

                new_provider, new_model_name = new_str.split(":", 1)
                try:
                    console.print(
                        f"[dim]Cargando {new_provider}/{new_model_name}…[/dim]"
                    )
                    bot        = create_orchestrator(new_provider, new_model_name, risk, session, prompts)
                    provider   = new_provider
                    model_name = new_model_name
                    console.print(
                        f"[green]✓[/green] Modelo cambiado a "
                        f"[bold]{provider}:{model_name}[/bold]"
                    )
                except Exception as e:
                    console.print(f"[red]Error al cambiar modelo:[/red] {e}")
                continue

            # ── mensaje normal ─────────────────────────────────────────────
            content, duration = run_turn(user_input)
            print_result(content)
            console.print(f"[dim]⏱ {duration:.2f}s[/dim]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrumpido. Escribe /exit para salir.[/yellow]")
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            import traceback
            console.print(traceback.format_exc())


if __name__ == "__main__":
    app()
