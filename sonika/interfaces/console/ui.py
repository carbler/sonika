import time
from typing import Any, Dict, Optional
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.prompt import Confirm
from rich.markdown import Markdown

from sonika_ai_toolkit.interfaces.base import BaseInterface

console = Console()

class ExecutionDisplay:
    """Legacy UI class. Being replaced by ConsoleInterface, kept here if used by other modules."""
    def __init__(self):
        self.active = False
    def start(self):
        pass
    def stop(self):
        pass
    def show_waiting(self):
        pass
    def clear_waiting(self):
        pass
    def update_thinking(self, chunk):
        pass
    def add_step(self, tool, params):
        pass
    def complete_step(self, out, error=False):
        pass

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
        console.print("\n[bold green]Sonika:[/bold green]")
        console.print(Markdown(content))

def print_model_info(provider: str, model: str):
    console.print(f"[bold]Current model:[/bold] {provider}:{model}")

def ask_confirm(prompt: str = "Continue?") -> bool:
    return Confirm.ask(f"[bold yellow]{prompt}[/bold yellow]")

def ask_secret(prompt: str) -> str:
    return console.input(f"[bold yellow]{prompt}[/bold yellow]: ", password=True)


class ConsoleInterface(BaseInterface):
    """
    Implementación del BaseInterface para la terminal usando Rich.
    """
    def __init__(self):
        self.start_times: Dict[str, float] = {}
        self.thought_buffer = ""
        self._is_thinking = False

    def _flush_thoughts(self):
        if self.thought_buffer:
            console.print(Panel(
                Markdown(self.thought_buffer),
                title="🧠 Pensamiento",
                border_style="dim",
                padding=(0, 2)
            ))
            self.thought_buffer = ""
            self._is_thinking = False

    def on_thought(self, chunk: str) -> None:
        """Render a chunk of thinking/reasoning."""
        if chunk:
            if not self._is_thinking:
                console.print("\n[dim]🧠 Pensando...[/dim]", end="\r")
                self._is_thinking = True
            self.thought_buffer += chunk

    def on_tool_start(self, tool_name: str, params: Dict[str, Any]) -> None:
        """Render the start of a tool execution."""
        self._flush_thoughts()
        self.start_times[tool_name] = time.time()
        console.print(f"[bold cyan]⚙️  Ejecutando:[/bold cyan] {tool_name} [dim]{params}[/dim]")

    def on_tool_end(self, tool_name: str, result: str) -> None:
        """Render the successful completion of a tool."""
        self._flush_thoughts()
        duration = time.time() - self.start_times.get(tool_name, time.time())
        console.print(f"[bold green]✅ {tool_name}[/bold green] [dim]({duration:.2f}s)[/dim]")

    def on_error(self, tool_name: str, error: str) -> None:
        """Render an error that occurred during tool execution."""
        self._flush_thoughts()
        duration = time.time() - self.start_times.get(tool_name, time.time())
        console.print(f"[bold red]❌ {tool_name} falló:[/bold red] {error} [dim]({duration:.2f}s)[/dim]")

    def on_interrupt(self, data: Dict[str, Any]) -> bool:
        """
        Handle a LangGraph interrupt (e.g. permission required).
        """
        self._flush_thoughts()
        console.print("\n[bold yellow]⚠️  Permiso Requerido[/bold yellow]")
        tool_name = data.get("tool", "unknown")
        
        if "diff" in data and data["diff"]:
            diff_text = data["diff"]
            syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
            console.print(Panel(syntax, title=f"Preview: {tool_name}", border_style="yellow"))
        else:
            params = data.get("params", {})
            console.print(f"Tool: [cyan]{tool_name}[/cyan]\nParams: {params}")

        return Confirm.ask("¿Permitir ejecución de esta acción?")

    def on_result(self, result: str) -> None:
        """Render the final result/report from the LLM."""
        self._flush_thoughts()
        if result:
            console.print("\n[bold green]Sonika:[/bold green]")
            console.print(Markdown(result))
