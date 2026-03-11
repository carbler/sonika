"""Claude Code-style renderer: Rich output + prompt_toolkit input.

No alternate screen, no mouse capture — native terminal scroll and copy/paste.
"""

from __future__ import annotations

import sys
import time
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window, FormattedTextControl
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.layout.processors import BeforeInput
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sonika.cli.renderers import BaseRenderer

# ── Colours ───────────────────────────────────────────────────────────────────

GREEN = "#a6e3a1"
RED = "#f38ba8"
YELLOW = "#f9e2af"
BLUE = "#89b4fa"
DIM = "dim"

# ANSI equivalents for prompt_toolkit
_GREEN = "ansibrightgreen"
_DIM = "ansibrightblack"
_RED = "ansibrightred"
_YELLOW = "ansibrightyellow"
_BOLD = "bold"

# Mode colours for prompt_toolkit
_MODE_COLORS = {
    "ask": _YELLOW,
    "auto": _GREEN,
    "plan": _RED,
}


# ── Formatting helpers ───────────────────────────────────────────────────────


def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


# ── Interactive picker ────────────────────────────────────────────────────────


async def _run_picker(
    title: str,
    items: list[tuple[str, Any]],
    hint: str = "↑↓ navegar · Enter seleccionar · Esc cancelar",
) -> Any | None:
    """Interactive picker with arrow key navigation."""
    if not items:
        return None

    state = {"index": 0}
    kb = KeyBindings()

    @kb.add("up")
    @kb.add("k")
    def _up(event):
        state["index"] = max(0, state["index"] - 1)

    @kb.add("down")
    @kb.add("j")
    def _down(event):
        state["index"] = min(len(items) - 1, state["index"] + 1)

    @kb.add("enter")
    def _select(event):
        event.app.exit(result=items[state["index"]][1])

    @kb.add("escape")
    @kb.add("q")
    def _cancel(event):
        event.app.exit(result=None)

    def _get_text():
        fragments: list[tuple[str, str]] = []
        fragments.append((_BOLD, f"\n  {title}\n\n"))
        for i, (label, _value) in enumerate(items):
            if i == state["index"]:
                fragments.append((f"bg:ansibrightblack {_GREEN} bold", f"  ❯ {label}\n"))
            else:
                fragments.append(("", f"    {label}\n"))
        fragments.append(("", "\n"))
        fragments.append((_DIM, f"  {hint}\n"))
        return fragments

    control = FormattedTextControl(_get_text)
    layout = Layout(Window(content=control, always_hide_cursor=True))
    app: Application = Application(layout=layout, key_bindings=kb, full_screen=False)
    return await app.run_async()


async def _run_approval(tool_name: str, args_str: str) -> bool:
    """Interactive approval with ← → navigation between Yes/No."""
    state = {"selected": 1}  # 0=Yes, 1=No (default No)
    kb = KeyBindings()

    @kb.add("left")
    @kb.add("h")
    def _left(event):
        state["selected"] = 0

    @kb.add("right")
    @kb.add("l")
    def _right(event):
        state["selected"] = 1

    @kb.add("y")
    def _yes(event):
        event.app.exit(result=True)

    @kb.add("n")
    @kb.add("escape")
    def _no(event):
        event.app.exit(result=False)

    @kb.add("enter")
    def _confirm(event):
        event.app.exit(result=state["selected"] == 0)

    def _get_text():
        fragments: list[tuple[str, str]] = []
        fragments.append((f"{_YELLOW} bold", f"  ⚠ {tool_name}\n"))
        if args_str:
            fragments.append((_DIM, f"    {args_str}\n"))
        fragments.append(("", "\n"))

        # Buttons
        if state["selected"] == 0:
            fragments.append((f"bg:{_GREEN} {_BOLD} ansiblack", "   ✓ Sí   "))
            fragments.append(("", "  "))
            fragments.append((_DIM, "   ✗ No   "))
        else:
            fragments.append((_DIM, "   ✓ Sí   "))
            fragments.append(("", "  "))
            fragments.append((f"bg:{_RED} {_BOLD} ansiblack", "   ✗ No   "))

        fragments.append(("", "\n\n"))
        fragments.append((_DIM, "  ← → navegar · Enter confirmar · y/n directo\n"))
        return fragments

    control = FormattedTextControl(_get_text)
    layout = Layout(Window(content=control, always_hide_cursor=True))
    app: Application = Application(layout=layout, key_bindings=kb, full_screen=False)
    return await app.run_async()


# ── Renderer ──────────────────────────────────────────────────────────────────


class ClaudeStyleRenderer(BaseRenderer):
    """Rich (stdout) + prompt_toolkit renderer inspired by Claude Code."""

    def __init__(self) -> None:
        self._console = Console(highlight=False)
        self._raw_tokens: list[str] = []
        self._raw_lines_printed: int = 0
        self._is_pre_tool: bool = True
        self._has_content: bool = False
        # Live status tracking
        self._t_start: float = 0.0
        self._token_count: int = 0
        self._phase: str = ""  # current activity label
        self._provider: str = ""
        self._model: str = ""
        self._status_visible: bool = False  # whether status line is on screen
        self._tools_count: int = 0
        # Stats for toolbar
        self._last_stats: dict | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def init(
        self,
        provider: str,
        model: str,
        session_id: str,
        app_title: str = "SONIKA",
        recent_sessions: list[dict] | None = None,
    ) -> None:
        import os
        import getpass

        # ── ASCII art mascot ──
        mascot = Text.assemble(
            ("      ╭──────╮\n", GREEN),
            ("      │ ◠  ◠ │\n", GREEN),
            ("      │  ──  │\n", GREEN),
            ("      ╰──┬┬──╯\n", GREEN),
            ("     ╭───┘└───╮\n", GREEN),
            ("     │ SONIKA │\n", f"bold {GREEN}"),
            ("     ╰────────╯\n", GREEN),
        )

        # ── Left column: welcome + mascot + model ──
        try:
            username = getpass.getuser().capitalize()
        except Exception:
            username = "Usuario"

        left = Text()
        left.append(f"\n  Hola {username}!\n\n", style=f"bold {GREEN}")
        left.append_text(mascot)
        left.append(f"\n  {provider}/{model}\n", style=DIM)
        cwd = os.getcwd()
        home = os.path.expanduser("~")
        if cwd.startswith(home):
            cwd = "~" + cwd[len(home):]
        left.append(f"  {cwd}\n", style=DIM)

        # ── Right column: tips + recent activity ──
        right = Text()
        right.append("\n  Tips\n", style=f"bold {YELLOW}")
        tips = [
            "Tab          cambiar modo",
            "/model       cambiar modelo",
            "/ui          cambiar interfaz",
            "/help        ver todos los comandos",
        ]
        for tip in tips:
            right.append(f"  {tip}\n", style=DIM)

        right.append(f"\n  Actividad reciente\n", style=f"bold {BLUE}")
        if recent_sessions:
            for s in recent_sessions[:3]:
                title = s.get("title", "Sin titulo")[:40]
                right.append(f"  {title}\n", style=DIM)
        else:
            right.append("  Sin actividad reciente\n", style=DIM)

        # ── Compose panel ──
        table = Table.grid(padding=(0, 3))
        table.add_column(min_width=30)
        table.add_column()
        table.add_row(left, right)

        self._console.print()
        self._console.print(
            Panel(
                table,
                border_style=GREEN,
                padding=(0, 1),
            )
        )
        self._console.print()

    async def get_input(
        self,
        mode: str,
        provider: str,
        model: str,
        on_tab=None,
    ) -> str:
        """Prompt input using PromptSession — clean scrollback, no artifacts."""
        state = {"mode": mode}

        kb = KeyBindings()

        @kb.add("tab")
        def _tab(event):
            if on_tab:
                state["mode"] = on_tab()
            event.app.invalidate()

        @kb.add("escape")
        def _escape(event):
            buf = event.app.current_buffer
            if buf.text:
                buf.reset()

        def _toolbar():
            parts: list[tuple[str, str]] = []
            parts.append((_DIM, f" {model}"))
            if self._last_stats:
                s = self._last_stats
                parts.append((_DIM, f" · {s['elapsed']:.1f}s"))
                if s.get("tokens"):
                    parts.append((_DIM, f" · {_fmt_tokens(s['tokens'])} tk"))
                if s.get("cost") and s["cost"] > 0:
                    parts.append((_DIM, f" · ${s['cost']:.4f}"))
                if s.get("tools"):
                    t = s["tools"]
                    parts.append((_DIM, f" · {t} tool{'s' if t > 1 else ''}"))
            parts.append((_DIM, "  │  Tab: modo"))
            return FormattedText(parts)

        def _prompt():
            m = state["mode"].upper()
            mc = _MODE_COLORS.get(state["mode"], _DIM)
            return FormattedText([
                (f"{mc} bold", f" {m} "),
                ("", " "),
                (_GREEN, "❯ "),
            ])

        if not hasattr(self, "_prompt_session"):
            self._prompt_session = PromptSession()

        result = await self._prompt_session.prompt_async(
            _prompt,
            bottom_toolbar=_toolbar,
            key_bindings=kb,
        )

        text = result.strip() if result else ""
        if not text:
            return ""
        return text

    async def shutdown(self) -> None:
        self._console.print(Text("\n  Bye!\n", style=DIM))

    # ── Chat display ──────────────────────────────────────────────────────────

    def show_user_message(self, text: str) -> None:
        self._console.print()

    def show_ai_start(self, provider: str = "", model: str = "") -> None:
        self._raw_tokens = []
        self._raw_lines_printed = 0
        self._is_pre_tool = True
        self._has_content = False
        self._t_start = time.monotonic()
        self._token_count = 0
        self._phase = "Pensando"
        self._provider = provider
        self._model = model
        self._status_visible = False
        self._tools_count = 0
        self._update_status()

    def show_thinking(self, text: str, line_count: int) -> None:
        # Just update status line with a preview — no in-place erase (fragile)
        first_line = ""
        for ln in text.splitlines():
            s = ln.strip().lstrip("#*- ").strip()
            if s:
                first_line = s[:50]
                break
        self._phase = f"Thinking: {first_line}" if first_line else "Thinking..."
        if self._status_visible:
            # Overwrite existing status line
            elapsed = time.monotonic() - self._t_start
            parts = [self._phase, f"{elapsed:.1f}s"]
            if self._provider and self._model:
                parts.append(f"{self._provider}/{self._model}")
            line = " · ".join(parts)
            sys.stdout.write(f"\r\033[2K\033[2m  ⏺ {line}\033[0m")
            sys.stdout.flush()
        else:
            self._update_status()

    def show_thinking_end(self, full_text: str) -> None:
        self._clear_status()
        if not full_text:
            return
        # Truncate to max visible lines with summary
        max_lines = 8
        all_lines = full_text.splitlines()
        total = len(all_lines)
        if total <= max_lines:
            display_text = full_text
        else:
            head = all_lines[:3]
            tail = all_lines[-3:]
            omitted = total - 6
            display_text = "\n".join(
                head + [f"  ... {omitted} lineas mas ..."] + tail
            )
        self._console.print(
            Panel(
                Text(display_text, style=DIM),
                title=f"Thinking ({total} lines)",
                title_align="left",
                border_style=YELLOW,
                padding=(0, 1),
            )
        )

    def show_token(self, token: str, is_pre_tool: bool) -> None:
        self._clear_status()
        self._has_content = True
        self._is_pre_tool = is_pre_tool
        self._raw_tokens.append(token)
        self._token_count += max(1, len(token) // 4)
        self._phase = "Generando"

        if is_pre_tool:
            sys.stdout.write(f"\033[2m{token}\033[0m")
        else:
            sys.stdout.write(token)
        sys.stdout.flush()
        self._raw_lines_printed += token.count("\n")

    def show_final_response(self, markdown_text: str) -> None:
        """Replace streamed raw tokens with Rich Markdown."""
        self._clear_status()
        self._erase_raw_tokens()
        self._raw_tokens = []
        self._raw_lines_printed = 0
        self._console.print(Text(f"  ● ", style=f"bold {GREEN}"), end="")
        self._console.print(Markdown(markdown_text), end="")
        self._console.print()

    def show_ai_end(
        self,
        elapsed: float,
        provider: str,
        model: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost: float = 0.0,
    ) -> None:
        self._clear_status()
        if not self._has_content:
            return

        tokens = 0
        if tokens_in or tokens_out:
            tokens = tokens_in + tokens_out
        elif self._token_count:
            tokens = self._token_count

        self._last_stats = {
            "elapsed": elapsed,
            "provider": provider,
            "model": model,
            "tokens": tokens,
            "cost": cost,
            "tools": self._tools_count,
        }
        self._console.print()

    # ── Tools ─────────────────────────────────────────────────────────────────

    def show_tool_start(self, name: str, args_str: str) -> None:
        self._clear_status()
        if self._is_pre_tool and self._raw_tokens:
            self._erase_raw_tokens()
            full = "".join(self._raw_tokens)
            if full.strip():
                self._console.print(Text(f"  ● {full.strip()}", style=DIM))
                self._console.print()
            self._raw_tokens = []
            self._raw_lines_printed = 0
            self._is_pre_tool = False

        self._tools_count += 1
        self._phase = f"▸ {name}"
        self._console.print(
            Text(f"    ▸ {name}({args_str})", style=DIM)
        )
        self._update_status()

    def show_tool_result(
        self,
        name: str,
        status: str,
        output: str,
        args_str: str,
        elapsed: float,
    ) -> None:
        self._clear_status()
        ok = status == "success"
        icon = "✓" if ok else "✗"
        color = GREEN if ok else RED
        line = f"    {icon} {name} ({elapsed:.1f}s)"
        if not ok and output:
            line += f": {output[:80]}"
        self._console.print(Text(line, style=f"bold {color}"))
        self._phase = "Generando"
        self._update_status()

    # ── Approval ──────────────────────────────────────────────────────────────

    async def show_approval(self, tool_name: str, args_str: str) -> bool:
        self._clear_status()
        self._console.print()
        return await _run_approval(tool_name, args_str)

    # ── System ────────────────────────────────────────────────────────────────

    def show_partial_response(self, text: str) -> None:
        """Show intermediate agent progress as a dim bullet."""
        self._clear_status()
        self._console.print(Text(f"  ● {text}", style=DIM))
        self._update_status()

    def show_retry(self, attempt: int, wait_s: float) -> None:
        self._clear_status()
        self._console.print(
            Text(
                f"  ↻ Rate limit — reintento {attempt}, espera {wait_s:.1f}s",
                style=DIM,
            )
        )

    def show_system(self, text: str) -> None:
        self._console.print(Text(f"  {text}", style=DIM))

    def show_error(self, text: str) -> None:
        msg = _extract_error_message(text)
        self._console.print(Text(f"  ✗ {msg}", style=f"bold {RED}"))

    # ── Pickers ───────────────────────────────────────────────────────────────

    def show_setup_prompt(self) -> dict[str, str]:
        self._console.print(
            Text("\n  Bienvenido a Sonika — Configuracion", style=f"bold {GREEN}")
        )
        self._console.print(
            Text("  Las API keys se guardan en ~/.sonika/config.json\n", style=DIM)
        )

        keys: dict[str, str] = {}
        providers = [
            ("openai", "sk-..."),
            ("google", "AIza..."),
            ("deepseek", "sk-..."),
        ]
        for prov, hint in providers:
            try:
                val = input(f"  {prov} API key ({hint}): ").strip()
                if val:
                    keys[prov] = val
            except (EOFError, KeyboardInterrupt):
                break
        self._console.print()
        return keys

    async def show_model_picker(
        self,
        models: list[Any],
        configured_providers: list[str],
    ) -> tuple[str, str] | None:
        items: list[tuple[str, Any]] = []
        for m in models:
            lock = "  🔒" if m.provider not in configured_providers else ""
            label = f"{m.provider:<9} {m.model_id:<36} {m.context_label:<5} {m.price_label}{lock}"
            items.append((label, (m.provider, m.model_id)))
        return await _run_picker("Seleccionar modelo", items)

    async def show_session_picker(
        self, sessions: list[dict]
    ) -> tuple[str, str] | None:
        if not sessions:
            self._console.print(Text("\n  (sin sesiones)\n", style=DIM))
            return None

        items: list[tuple[str, Any]] = []
        for s in sessions:
            title = s.get("title", "Sin titulo")[:44]
            model = f"{s.get('provider', '?')}/{s.get('model', '?')}"
            cost = f"${s.get('cost', 0):.4f}"
            updated = s.get("updated_at", "")[:10]
            label = f"{title:<46} {model:<26} {cost:<8} {updated}"
            items.append((label, ("open", s["id"])))

        return await _run_picker(
            "Sesiones",
            items,
            hint="↑↓ navegar · Enter abrir · Esc cancelar",
        )

    def show_key_input(self, provider: str) -> str | None:
        hints = {"openai": "sk-...", "google": "AIza...", "deepseek": "sk-..."}
        try:
            val = input(
                f"  API key para {provider} ({hints.get(provider, 'key...')}): "
            ).strip()
            return val if val else None
        except (EOFError, KeyboardInterrupt):
            return None

    def show_help(self) -> None:
        self._console.print()
        help_items = [
            ("/model", "cambiar modelo"),
            ("/session", "sesiones anteriores"),
            ("/new", "nueva sesion"),
            ("/key <prov> <k>", "guardar API key"),
            ("/mode", "cambiar modo (ask/auto/plan)"),
            ("/exit", "salir"),
            ("Tab", "cambiar modo"),
        ]
        for cmd, desc in help_items:
            self._console.print(
                Text(f"  {cmd:<20}", style=f"bold {GREEN}"),
                Text(desc, style=DIM),
            )
        self._console.print()

    # ── Internal: status line ─────────────────────────────────────────────────

    def _update_status(self) -> None:
        """Write/overwrite a single status line below current output."""
        elapsed = time.monotonic() - self._t_start
        parts = [self._phase]
        parts.append(f"{elapsed:.1f}s")
        if self._token_count:
            parts.append(f"~{_fmt_tokens(self._token_count)} tokens")
        if self._provider and self._model:
            parts.append(f"{self._provider}/{self._model}")

        line = " · ".join(parts)
        if self._status_visible:
            sys.stdout.write(f"\r\033[2K\033[2m  ⏺ {line}\033[0m")
        else:
            sys.stdout.write(f"\n\033[2m  ⏺ {line}\033[0m")
            self._status_visible = True
        sys.stdout.flush()

    def _clear_status(self) -> None:
        """Remove the status line if visible."""
        if self._status_visible:
            sys.stdout.write("\r\033[2K")
            sys.stdout.write("\033[A\033[2K")
            sys.stdout.write("\r")
            sys.stdout.flush()
            self._status_visible = False

    def _erase_raw_tokens(self) -> None:
        """Erase previously streamed raw tokens from terminal."""
        if not self._raw_tokens:
            return
        lines = self._raw_lines_printed + 1
        for _ in range(lines):
            sys.stdout.write("\033[2K\033[A")
        sys.stdout.write("\033[2K\r")
        sys.stdout.flush()



# ── Utilities ─────────────────────────────────────────────────────────────────


def _extract_error_message(text: str) -> str:
    """Extract a short, readable error from verbose API error strings."""
    import json
    import re

    json_match = re.search(r'\{.*"message".*\}', text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            error = data.get("error", data)
            if isinstance(error, dict):
                msg = error.get("message", "")
                if msg:
                    return msg.split("\n")[0].strip() if "\n" in msg else msg[:120]
            return str(error)[:120]
        except (json.JSONDecodeError, AttributeError):
            pass

    reason_match = re.search(r'"reason":\s*"([^"]+)"', text)
    if reason_match:
        return reason_match.group(1)

    return text[:120]
