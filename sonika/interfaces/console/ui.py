import time
from typing import Any, Dict, Optional
from rich.console import Console, Group
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich.live import Live
from rich.spinner import Spinner
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.box import MINIMAL

from sonika_ai_toolkit.interfaces.base import BaseInterface

console = Console()

class ExecutionDisplay:
    """Legacy UI class."""
    def __init__(self):
        self.active = False
    def start(self): pass
    def stop(self): pass
    def show_waiting(self): pass
    def clear_waiting(self): pass
    def update_thinking(self, chunk): pass
    def add_step(self, tool, params): pass
    def complete_step(self, out, error=False): pass

def print_welcome(model_info: str):
    console.print(Panel(
        f"[bold cyan]Sonika CLI[/bold cyan] — Autonomous Agent\n"
        f"🤖 [dim]Model:[/dim] [green]{model_info}[/green]\n\n"
        f"[bold]Commands:[/bold]\n"
        f"  [cyan]TAB[/cyan]     : Change Mode (plan / ask / auto)\n"
        f"  [cyan]/model[/cyan]  : Change model provider:name\n"
        f"  [cyan]/exit[/cyan]   : Quit session",
        title="[bold yellow]✨ Welcome to Sonika[/bold yellow]",
        border_style="cyan",
        padding=(1, 2)
    ))

def print_result(content: str):
    if content:
        console.print("\n[bold cyan]sonika ❯[/bold cyan]")
        console.print(Markdown(content))

def print_model_info(provider: str, model: str):
    console.print(f"[bold]Current model:[/bold] {provider}:{model}")

def ask_confirm(prompt: str = "Continue?") -> bool:
    return Confirm.ask(f"[bold yellow]{prompt}[/bold yellow]")

def ask_secret(prompt: str) -> str:
    return console.input(f"[bold yellow]{prompt}[/bold yellow]: ", password=True)


class ConsoleInterface(BaseInterface):
    """
    Implementación del BaseInterface para la terminal usando Rich con motor Live 
    (estilo Claude Code).
    """
    def __init__(self):
        self.start_times: Dict[str, float] = {}
        self.turn_start_time = 0.0
        
        # State for Live render
        self.events = []
        self.current_thought_chunk = ""
        self._is_thinking = False
        self.active_tool = None
        self.live: Optional[Live] = None

    def start_turn(self):
        """Inicia el layout dinámico de un nuevo turno."""
        self.turn_start_time = time.time()
        self.events = []
        self.current_thought_chunk = ""
        self._is_thinking = True
        self.active_tool = None
        self.start_times = {}
        
        self.live = Live(
            get_renderable=self.render_layout,
            refresh_per_second=10,
            console=console,
            transient=False  # Keep the final output visible
        )
        self.live.start()

    def end_turn(self):
        """Finaliza el layout dinámico."""
        self._flush_thought_chunk()
        self._is_thinking = False
        if self.live:
            self.live.update(self.render_layout(final=True))
            self.live.stop()
            self.live = None

    def _flush_thought_chunk(self):
        """Mueve el texto actual de pensamiento al historial de eventos."""
        if self.current_thought_chunk.strip():
            self.events.append({"type": "thought", "content": self.current_thought_chunk})
            self.current_thought_chunk = ""

    def render_layout(self, final=False):
        """Genera el árbol de componentes a renderizar en este frame."""
        elapsed = time.time() - self.turn_start_time
        elements = []
        
        def render_thought(content):
            return Panel(
                Markdown(content),
                box=MINIMAL,
                border_style="dim cyan",
                padding=(0, 2),
                style="dim"
            )

        # 1. Renderizar el historial de este turno
        for event in self.events:
            if event["type"] == "thought":
                elements.append(render_thought(event["content"]))
            elif event["type"] == "tool":
                name = event["name"]
                duration = event["duration"]
                if event["status"] == "success":
                    elements.append(Text.from_markup(f"[bold green]✓[/bold green] [dim]{name} ({duration:.1f}s)[/dim]"))
                else:
                    err = event["error"]
                    # Limit error length in inline view
                    if len(err) > 60: err = err[:57] + "..."
                    elements.append(Text.from_markup(f"[bold red]✗[/bold red] [dim]{name} ({duration:.1f}s): {err}[/dim]"))

        # 2. Renderizar el bloque de pensamiento activo (stream)
        if self.current_thought_chunk.strip():
            elements.append(render_thought(self.current_thought_chunk))

        # 3. Renderizar la herramienta activa
        if self.active_tool and not final:
            t_name, t_params = self.active_tool
            # Try to format params safely
            param_str = str(t_params)
            if len(param_str) > 50:
                param_str = param_str[:47] + "..."
            elements.append(Spinner("dots", text=f"[bold cyan]Ejecutando {t_name}...[/bold cyan] [dim]{param_str}[/dim]"))

        # 4. Renderizar el estado global de pensamiento
        if self._is_thinking and not self.active_tool and not final:
            elements.append(Spinner("dots", text=f"[dim]Pensando... ({elapsed:.1f}s)[/dim]", style="dim"))

        # 5. Timer final al terminar
        if final and len(elements) > 0:
            elements.append(Text.from_markup(f"")) # Empty line separator

        if not elements:
            return Text("")
            
        return Group(*elements)

    # BaseInterface methods
    
    def on_thought(self, chunk: str) -> None:
        if chunk:
            self._is_thinking = True
            self.current_thought_chunk += chunk

    def on_tool_start(self, tool_name: str, params: Dict[str, Any]) -> None:
        self._flush_thought_chunk()
        self.start_times[tool_name] = time.time()
        self.active_tool = (tool_name, params)
        self._is_thinking = False

    def on_tool_end(self, tool_name: str, result: str) -> None:
        self._flush_thought_chunk()
        duration = time.time() - self.start_times.get(tool_name, time.time())
        self.events.append({
            "type": "tool",
            "name": tool_name,
            "status": "success",
            "duration": duration
        })
        self.active_tool = None
        self._is_thinking = True

    def on_error(self, tool_name: str, error: str) -> None:
        self._flush_thought_chunk()
        duration = time.time() - self.start_times.get(tool_name, time.time())
        self.events.append({
            "type": "tool",
            "name": tool_name,
            "status": "error",
            "duration": duration,
            "error": error
        })
        self.active_tool = None
        self._is_thinking = True

    def on_interrupt(self, data: Dict[str, Any]) -> bool:
        """
        Pausa el layout en vivo para pedir confirmación interactiva.
        """
        # Temporalmente detenemos la animación para mostrar el prompt de confirmación limpio
        if self.live:
            self.live.stop()
            
        self._flush_thought_chunk()
        console.print("\n[bold yellow]⚠️  Permiso Requerido[/bold yellow]")
        tool_name = data.get("tool", "unknown")
        
        if "diff" in data and data["diff"]:
            diff_text = data["diff"]
            syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
            console.print(Panel(syntax, title=f"Preview: {tool_name}", border_style="yellow"))
        else:
            params = data.get("params", {})
            console.print(f"Tool: [cyan]{tool_name}[/cyan]\nParams: {params}")

        approved = Confirm.ask("¿Permitir ejecución de esta acción?")
        
        # Reiniciamos la animación
        if self.live:
            self.live.start()
            
        return approved

    def on_result(self, result: str) -> None:
        # Finaliza el bloque asíncrono si está activo
        pass 
