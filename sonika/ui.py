import sys
from typing import List, Dict
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt

console = Console()

# ── ANSI sequences (bypass Rich for inline streaming) ──────────────────────
_GRAY     = "\033[38;5;244m"   # gris medio — texto de pensamiento
_DIM_CYAN = "\033[2;36m"       # cyan tenue — borde │
_DIM      = "\033[2m"
_BOLD     = "\033[1m"
_YELLOW   = "\033[33m"
_GREEN    = "\033[32m"
_RED      = "\033[31m"
_RESET    = "\033[0m"
_BOX_W    = 48                  # ancho de los bordes del bloque thinking


class ExecutionDisplay:
    """
    Display sin Live/panel fijo.

    • Thinking → streameado directo al terminal con ANSI tenue.
      El terminal hace scroll natural; el texto más nuevo siempre queda
      abajo (donde está el cursor). El usuario puede subir para ver más.
    • Steps   → líneas de estado simples (⏳ / ✅ / ❌).
    """

    def __init__(self):
        self.thinking_buffer  = ""
        self.thinking_started = False
        self._at_line_start   = True   # si el cursor está al inicio de línea
        self.steps: List[Dict] = []
        self.current_step = None

    # ── lifecycle ──────────────────────────────────────────────────────────

    def start(self):
        pass  # sin Live

    def stop(self):
        """Cierra cualquier bloque de thinking abierto."""
        if self.thinking_started:
            if not self._at_line_start:
                sys.stdout.write(_RESET + "\n")
            sys.stdout.write(f"{_DIM_CYAN}╰{'─' * _BOX_W}{_RESET}\n")
            sys.stdout.flush()
            self.thinking_started = False
            self._at_line_start = True

    # ── thinking ───────────────────────────────────────────────────────────

    def update_thinking(self, chunk: str):
        """
        Imprime el chunk de razonamiento en color tenue.
        """
        if not chunk:
            return
        
        # Ignorar si es solo un espacio o newline al inicio extremo (limpieza)
        if not self.thinking_started and chunk.strip() == "":
            return

        self.thinking_buffer += chunk

        if not self.thinking_started:
            label = " 💭 Razonamiento "
            dashes = _BOX_W - len(label)
            sys.stdout.write(
                f"\n{_DIM_CYAN}╭{label}{'─' * dashes}╮{_RESET}\n"
            )
            sys.stdout.flush()
            self.thinking_started = True
            self._at_line_start = True

        # Procesar líneas
        lines = chunk.split("\n")
        for i, line in enumerate(lines):
            if i > 0:
                sys.stdout.write(_RESET + "\n")
                self._at_line_start = True
            
            if self._at_line_start:
                sys.stdout.write(f"{_DIM_CYAN}│{_RESET} {_GRAY}")
                self._at_line_start = False
            
            if line:
                sys.stdout.write(line)
        
        sys.stdout.flush()

    # ── steps ──────────────────────────────────────────────────────────────

    def add_step(self, tool_name: str, params: str):
        """Muestra el inicio de la ejecución de una herramienta."""
        # Cierra el bloque thinking si estaba abierto
        if self.thinking_started:
            if not self._at_line_start:
                sys.stdout.write(_RESET + "\n")
                self._at_line_start = True
            sys.stdout.write(f"{_DIM_CYAN}╰{'─' * _BOX_W}{_RESET}\n")
            sys.stdout.flush()
            self.thinking_started = False

        params_short = (params[:72] + "…") if len(params) > 72 else (params or "{}")
        self.current_step = {
            "name": tool_name,
            "params": params_short,
            "status": "running",
        }
        self.steps.append(self.current_step)

        sys.stdout.write(
            f"\n  {_YELLOW}⏳{_RESET} {_BOLD}{tool_name}{_RESET}  {_DIM}{params_short}{_RESET}\n"
        )
        sys.stdout.flush()

    def complete_step(self, output: str, error: bool = False):
        """Marca el paso actual como completado."""
        if not self.current_step:
            return
        icon  = f"{_RED}❌{_RESET}" if error else f"{_GREEN}✅{_RESET}"
        name  = self.current_step["name"]
        brief = output.replace("\n", " ")[:90]
        sys.stdout.write(
            f"  {icon} {_BOLD}{name}{_RESET}  {_DIM}→ {brief}{_RESET}\n"
        )
        sys.stdout.flush()
        self.current_step["status"] = "error" if error else "success"
        self.current_step = None


# ── helpers de consola ─────────────────────────────────────────────────────

def print_welcome(model_str: str = ""):
    model_hint = f"\n[dim]Modelo: [bold]{model_str}[/bold][/dim]" if model_str else ""
    console.print(Panel.fit(
        "[bold cyan]Sonika CLI — ExecutorBot Edition[/bold cyan]\n"
        "Powered by [yellow]Sonika AI[/yellow]  ·  "
        "OpenAI · DeepSeek · Gemini · Session Aware"
        + model_hint +
        "\n[dim]/model <provider:nombre>  /modelos  /help  /exit[/dim]",
        border_style="blue",
    ))


def print_result(content: str):
    console.print()
    console.print(Panel(
        Markdown(content),
        title="🤖 Respuesta",
        border_style="green",
    ))


def print_model_info(provider: str, model_name: str):
    console.print(
        f"\n  [cyan]Modelo actual:[/cyan] [bold]{provider}:{model_name}[/bold]\n"
        "  [dim]Uso: /model gemini:gemini-2.5-flash[/dim]"
    )


def ask_secret(prompt: str) -> str:
    return Prompt.ask(f"[bold yellow]{prompt}[/bold yellow]", password=True)


def ask_confirm(prompt: str) -> bool:
    return Prompt.ask(
        f"[bold cyan]{prompt}[/bold cyan]", choices=["y", "n"], default="y"
    ) == "y"
