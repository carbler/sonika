import typer
import sys
import asyncio as _asyncio
from typing import Optional
from dotenv import load_dotenv

from .interfaces.console.app import ConsoleApp

# Fix: reuse a persistent event loop across calls.
_persistent_loop = _asyncio.new_event_loop()
_asyncio.set_event_loop(_persistent_loop)

def _persistent_asyncio_run(coro, *, debug=None):
    global _persistent_loop
    if _persistent_loop.is_closed():
        _persistent_loop = _asyncio.new_event_loop()
        _asyncio.set_event_loop(_persistent_loop)
    return _persistent_loop.run_until_complete(coro)

_asyncio.run = _persistent_asyncio_run

app = typer.Typer()
load_dotenv()

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
    
    # Parsear modelo
    if ":" in model:
        provider, model_name = model.split(":", 1)
    else:
        provider, model_name = model, "default"

    console_app = ConsoleApp()
    
    try:
        console_app.start_bot(provider, model_name, risk, session, prompts)
    except Exception as e:
        print(f"Error initializing bot: {e}")
        return

    # Prompt inicial
    if prompt:
        content, duration = console_app.run_turn(prompt)
        console_app.ui.on_result(content)
        from .interfaces.console.ui import console
        console.print(f"[dim]⏱ {duration:.2f}s[/dim]")

    # Run loop
    console_app.run_interactive_loop()

if __name__ == "__main__":
    app()
