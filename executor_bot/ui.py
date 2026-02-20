from typing import List, Dict, Any
from rich.console import Console, Group
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.layout import Layout
from rich.live import Live
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()

class ExecutionDisplay:
    """Gestiona la visualización en tiempo real del razonamiento y los pasos."""
    
    def __init__(self):
        self.thinking_buffer = ""
        self.steps: List[Dict] = []
        self.current_step = None
        self.live = None

    def start(self):
        """Inicia el modo Live."""
        self.live = Live(self._generate_renderable(), console=console, refresh_per_second=10)
        self.live.start()

    def stop(self):
        """Detiene el modo Live."""
        if self.live:
            self.live.stop()

    def update_thinking(self, chunk: str):
        """Añade texto al buffer de pensamiento."""
        self.thinking_buffer += chunk
        # Auto-scroll hack: keep last 1000 chars if too long to save memory in display
        if len(self.thinking_buffer) > 5000:
            self.thinking_buffer = "..." + self.thinking_buffer[-4997:]
        if self.live:
            self.live.update(self._generate_renderable())

    def add_step(self, tool_name: str, params: str):
        """Registra un nuevo paso de herramienta."""
        self.current_step = {
            "name": tool_name,
            "params": params,
            "status": "running",
            "output": ""
        }
        self.steps.append(self.current_step)
        if self.live:
            self.live.update(self._generate_renderable())

    def complete_step(self, output: str, error: bool = False):
        """Marca el paso actual como completado."""
        if self.current_step:
            self.current_step["status"] = "error" if error else "success"
            self.current_step["output"] = output
            self.current_step = None
        if self.live:
            self.live.update(self._generate_renderable())

    def _generate_renderable(self):
        """Genera el layout visual."""
        
        # 1. Tabla de Pasos (Secuencia)
        step_table = Table(box=box.SIMPLE, expand=True, show_header=False)
        step_table.add_column("Status", width=3)
        step_table.add_column("Action")
        
        for step in self.steps:
            if step["status"] == "running":
                icon = "⏳"
                style = "bold yellow"
            elif step["status"] == "success":
                icon = "✅"
                style = "green"
            else:
                icon = "❌"
                style = "red"
                
            action_text = Text(f"{step['name']}", style=style)
            action_text.append(f"({step['params'][:50]}...)", style="dim")
            step_table.add_row(icon, action_text)

        # 2. Panel de Thinking (Markdown streaming)
        think_content = self.thinking_buffer if self.thinking_buffer else "[Waiting for thought process...]"
        think_panel = Panel(
            Markdown(think_content),
            title="🧠 Reasoning",
            border_style="cyan",
            height=15  # Fixed height for thinking
        )

        steps_panel = Panel(
            step_table,
            title="⚡ Execution Sequence",
            border_style="yellow"
        )

        return Group(think_panel, steps_panel)


def print_welcome():
    console.print(Panel.fit(
        "[bold cyan]OpenCode CLI (ExecutorBot)[/bold cyan]\n"
        "Powered by [yellow]Sonika AI[/yellow]\n"
        "Models: OpenAI, DeepSeek | Session Aware | Live Reasoning",
        border_style="blue"
    ))

def print_result(content: str):
    console.print(Panel(Markdown(content), title="🤖 Final Response", border_style="green"))

def ask_secret(prompt: str) -> str:
    return Prompt.ask(f"[bold yellow]{prompt}[/bold yellow]", password=True)

def ask_confirm(prompt: str) -> bool:
    return Prompt.ask(f"[bold cyan]{prompt}[/bold cyan]", choices=["y", "n"], default="y") == "y"
