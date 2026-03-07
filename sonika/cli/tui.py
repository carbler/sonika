"""Sonika TUI — OpenCode-inspired Textual interface."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Optional

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.css.query import NoMatches
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static
from textual.widget import Widget

from sonika.cli.config import Config, PROVIDERS
from sonika.cli.models_catalog import MODELS, ModelInfo, all_providers, models_for_provider
from sonika.cli.session_manager import Session, SessionManager


# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """
Screen { background: #1e1e2e; color: #cdd6f4; }

#header-bar {
    height: 1;
    background: #181825;
    color: #6c7086;
    padding: 0 1;
}

#chat-scroll {
    height: 1fr;
    padding: 0 1;
}

.turn-label-user { color: #89b4fa; text-style: bold; margin-top: 1; }
.turn-label-ai   { color: #a6e3a1; text-style: bold; margin-top: 1; }

.msg-body     { padding-left: 2; color: #cdd6f4; }
.msg-loading  { padding-left: 2; color: #45475a; }

.thinking-text { padding-left: 2; color: #45475a; }
.tool-pending  { padding-left: 2; color: #f9e2af; }
.tool-ok       { padding-left: 2; color: #a6e3a1; }
.tool-fail     { padding-left: 2; color: #f38ba8; }
.system-text   { padding-left: 2; color: #45475a; }

/* Approval */
.approval-box {
    margin-left: 2;
    margin-top: 0;
    padding: 0 1;
    border-left: solid #f9e2af;
    height: auto;
}
.approval-title { color: #f9e2af; text-style: bold; }
.approval-args  { color: #cdd6f4; }
.approval-hint  { color: #45475a; }
.approval-btns  { layout: horizontal; height: 3; }

Button.btn-deny {
    min-width: 12;
    background: #313244;
    border: tall #585b70;
    color: #cdd6f4;
    margin-right: 1;
}
Button.btn-deny:focus {
    border: tall #f38ba8;
    color: #f38ba8;
}
Button.btn-approve {
    min-width: 14;
    background: #313244;
    border: tall #585b70;
    color: #cdd6f4;
}
Button.btn-approve:focus {
    border: tall #a6e3a1;
    color: #a6e3a1;
}

#input-area {
    height: auto;
    max-height: 10;
    border-top: solid #313244;
    padding: 0 1;
}
#chat-input       { border: round #45475a; }
#chat-input:focus { border: round #89b4fa; }

#footer-hint {
    height: 1;
    background: #181825;
    color: #45475a;
    padding: 0 1;
}

/* Modals */
ModelPickerScreen, SessionPickerScreen, SetupScreen, KeyInputScreen {
    align: center middle;
}
.modal-box {
    background: #1e1e2e;
    border: round #585b70;
    padding: 1 2;
    width: 92;
    max-height: 38;
}
.modal-title { text-style: bold; color: #89b4fa; margin-bottom: 1; }
.modal-hint  { color: #45475a; margin-top: 1; }

ListView { height: 1fr; background: #181825; border: solid #313244; }
ListItem { color: #cdd6f4; padding: 0 1; }
ListItem.--highlight { background: #313244; color: #89b4fa; }

.setup-lbl   { color: #89b4fa; margin-top: 1; }
.setup-input { border: round #45475a; margin-bottom: 1; }
.setup-input:focus { border: round #89b4fa; }
"""


# ── Header ────────────────────────────────────────────────────────────────────

class HeaderBar(Widget):
    def __init__(self, provider: str, model: str, session_id: str):
        super().__init__(id="header-bar")
        self._provider   = provider
        self._model      = model
        self._session_id = session_id
        self._tokens     = 0
        self._cost       = 0.0
        self._busy       = False

    def render(self) -> str:
        busy = "  ⟳ generando…" if self._busy else ""
        return (
            f" SONIKA  {self._provider}/{self._model}"
            f"  {self._tokens:,} tok  ${self._cost:.4f}"
            f"  #{self._session_id}{busy} "
        )

    def set_busy(self, v: bool):
        self._busy = v
        self.refresh()

    def update_stats(self, tokens: int, cost: float):
        self._tokens, self._cost = tokens, cost
        self.refresh()

    def update_model(self, provider: str, model: str, session_id: str):
        self._provider, self._model, self._session_id = provider, model, session_id
        self.refresh()


# ── Inline approval ───────────────────────────────────────────────────────────

class ApprovalWidget(Container):
    """Two-button inline approval, navigable with ← →."""

    class Done(Message):
        def __init__(self, approved: bool):
            super().__init__()
            self.approved = approved

    BINDINGS = [
        Binding("left",   "focus_deny",    show=False),
        Binding("right",  "focus_approve", show=False),
        Binding("escape", "deny",          show=False),
    ]

    def __init__(self, tool_name: str, args_str: str):
        super().__init__(classes="approval-box")
        self._tool = tool_name
        self._args = args_str

    def compose(self) -> ComposeResult:
        yield Static(f"⚠  {self._tool}", markup=False, classes="approval-title")
        if self._args:
            yield Static(f"   {self._args}", markup=False, classes="approval-args")
        yield Static("   ← → navegar  ·  Enter confirmar  ·  Esc=denegar", classes="approval-hint")
        with Horizontal(classes="approval-btns"):
            yield Button("✗  Denegar", id="deny",    classes="btn-deny")
            yield Button("✓  Aprobar", id="approve", classes="btn-approve")

    async def on_mount(self):
        self.query_one("#deny", Button).focus()

    def on_button_pressed(self, event: Button.Pressed):
        self.post_message(ApprovalWidget.Done(event.button.id == "approve"))

    def action_focus_deny(self):    self.query_one("#deny",    Button).focus()
    def action_focus_approve(self): self.query_one("#approve", Button).focus()
    def action_deny(self):          self.post_message(ApprovalWidget.Done(False))


# ── Modals ────────────────────────────────────────────────────────────────────

class KeyInputScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss(None)", "Cancelar")]

    def __init__(self, provider: str, config: Config):
        super().__init__()
        self._provider, self._config = provider, config

    def compose(self) -> ComposeResult:
        hints = {"openai": "sk-...", "google": "AIza...", "deepseek": "sk-..."}
        with Container(classes="modal-box"):
            yield Label(f"API key — {self._provider}", classes="modal-title")
            yield Input(placeholder=hints.get(self._provider, "key..."),
                        id="ki", classes="setup-input", password=True)
            yield Button("Guardar", id="save", variant="primary")
            yield Label("Esc para cancelar", classes="modal-hint")

    async def on_mount(self):
        self.query_one("#ki", Input).focus()

    def on_button_pressed(self, e: Button.Pressed):
        if e.button.id == "save": self._save()

    async def on_input_submitted(self, _):
        self._save()

    def _save(self):
        v = self.query_one("#ki", Input).value.strip()
        if v:
            self._config.set_key(self._provider, v)
            self.dismiss(v)
        else:
            self.dismiss(None)


class ModelPickerScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss(None)", "Cancelar")]

    def __init__(self, config: Config):
        super().__init__()
        self._config = config
        self._idx: list[ModelInfo] = []

    def compose(self) -> ComposeResult:
        with Container(classes="modal-box"):
            yield Label("Seleccionar modelo", classes="modal-title")
            with ListView(id="ml"):
                for prov in all_providers():
                    yield ListItem(Label(f"  {prov.upper()}"))
                    for m in models_for_provider(prov):
                        i = len(self._idx)
                        self._idx.append(m)
                        lock = "" if self._config.has_key(m.provider) else "  [sin key]"
                        yield ListItem(
                            Label(f"    {m.model_id:<36} {m.context_label:<5} {m.price_label}{lock}"),
                            id=f"mi-{i}",
                        )
            yield Label("↑↓ · Enter seleccionar · Esc cancelar", classes="modal-hint")

    def on_list_view_selected(self, e: ListView.Selected):
        iid = e.item.id or ""
        if iid.startswith("mi-"):
            try:
                m = self._idx[int(iid[3:])]
                self.dismiss((m.provider, m.model_id))
            except (ValueError, IndexError):
                pass


class SessionPickerScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss(None)", "Cancelar"),
        Binding("d", "delete_sel", "Borrar"),
    ]

    def __init__(self, manager: SessionManager):
        super().__init__()
        self._mgr = manager
        self._sess: list[dict] = []

    def compose(self) -> ComposeResult:
        self._sess = self._mgr.list_sessions()
        with Container(classes="modal-box"):
            yield Label("Sesiones", classes="modal-title")
            with ListView(id="sl"):
                if not self._sess:
                    yield ListItem(Label("  (sin sesiones)"))
                for s in self._sess:
                    title   = s.get("title", "Sin título")[:48]
                    model   = f"{s.get('provider','?')}/{s.get('model','?')}"
                    cost    = f"${s.get('cost', 0):.4f}"
                    updated = s.get("updated_at", "")[:10]
                    yield ListItem(Label(f"  {title:<50} {model:<26} {cost:<8} {updated}"),
                                   id=f"s-{s['id']}")
            yield Label("↑↓ · Enter abrir · d borrar · Esc cancelar", classes="modal-hint")

    def on_list_view_selected(self, e: ListView.Selected):
        iid = e.item.id or ""
        if iid.startswith("s-"):
            self.dismiss(("open", iid[2:]))

    def action_delete_sel(self):
        try:
            lv = self.query_one("#sl", ListView)
            hi = lv.highlighted_child
            if hi and (hi.id or "").startswith("s-"):
                self._mgr.delete(hi.id[2:])
                self.dismiss(("deleted", hi.id[2:]))
        except NoMatches:
            pass


class SetupScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "Saltar")]

    def __init__(self, config: Config):
        super().__init__()
        self._config = config

    def compose(self) -> ComposeResult:
        with Container(classes="modal-box"):
            yield Label("Bienvenido a Sonika — Configuración", classes="modal-title")
            yield Static("Las API keys se guardan en ~/.sonika/config.json")
            yield Label("OpenAI:", classes="setup-lbl")
            yield Input(placeholder="sk-...",   id="key-openai",   classes="setup-input", password=True)
            yield Label("Google:", classes="setup-lbl")
            yield Input(placeholder="AIza...",  id="key-google",   classes="setup-input", password=True)
            yield Label("DeepSeek:", classes="setup-lbl")
            yield Input(placeholder="sk-...",   id="key-deepseek", classes="setup-input", password=True)
            yield Button("Guardar y continuar", id="save", variant="primary")
            yield Label("Esc para saltar", classes="modal-hint")

    def on_button_pressed(self, e: Button.Pressed):
        if e.button.id == "save":
            for p in PROVIDERS:
                v = self.query_one(f"#key-{p}", Input).value.strip()
                if v:
                    self._config.set_key(p, v)
            self.dismiss()


# ── App ───────────────────────────────────────────────────────────────────────

class SonikaApp(App):
    CSS = CSS
    ALLOW_SELECT = True

    BINDINGS = [
        Binding("ctrl+q", "quit",        "Salir"),
        Binding("ctrl+n", "new_session", "Nueva sesión"),
    ]

    def __init__(self):
        super().__init__()
        self._config  = Config()
        self._mgr     = SessionManager()
        self._session: Optional[Session] = None
        self._bot     = None
        self._hdr:    Optional[HeaderBar] = None
        self._streaming   = False
        self._approval_ev: Optional[asyncio.Event] = None
        self._approval_ok: bool = False

    # ── Layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        prov  = self._config.active_provider or "?"
        model = self._config.active_model    or "?"
        self._hdr = HeaderBar(prov, model, "new")
        yield self._hdr
        with ScrollableContainer(id="chat-scroll"):
            pass
        with Container(id="input-area"):
            yield Input(placeholder="> ", id="chat-input")
        yield Static(
            "  enter: enviar  ·  /model  /session  /new  /key <prov> <key>  /help  ·  ctrl+q: salir",
            id="footer-hint",
        )

    async def on_mount(self):
        if not self._config.is_configured:
            await self.push_screen(SetupScreen(self._config))
            self._auto_model()
        await self._start_session()
        self.query_one("#chat-input", Input).focus()

    def _auto_model(self):
        if self._config.active_provider and self._config.active_model:
            return
        for m in MODELS:
            if self._config.has_key(m.provider):
                self._config.set_active(m.provider, m.model_id)
                return

    # ── Session ───────────────────────────────────────────────────────────────

    async def _start_session(self):
        prov  = self._config.active_provider
        model = self._config.active_model
        if not prov or not model:
            return
        self._session = self._mgr.new_session(prov, model)
        self._rebuild_bot()
        self._refresh_hdr()

    def _rebuild_bot(self):
        if not self._session:
            return
        key = self._config.get_key(self._session.provider)
        if not key:
            return
        env_map = {"openai": "OPENAI_API_KEY", "google": "GOOGLE_API_KEY",
                   "deepseek": "DEEPSEEK_API_KEY"}
        ev = env_map.get(self._session.provider)
        if ev:
            os.environ[ev] = key
        try:
            from sonika.factory import create_orchestrator
            self._bot = create_orchestrator(
                provider=self._session.provider,
                model_name=self._session.model,
                risk_level=2,
                session_id=self._session.id,
            )
        except Exception as exc:
            self._line(f"Error bot: {exc}")
            self._bot = None

    def _refresh_hdr(self):
        if self._hdr and self._session:
            tok = self._session.tokens_in + self._session.tokens_out
            self._hdr.update_model(self._session.provider, self._session.model, self._session.id)
            self._hdr.update_stats(tok, self._session.cost)

    # ── Chat helpers ──────────────────────────────────────────────────────────

    def _sc(self) -> ScrollableContainer:
        return self.query_one("#chat-scroll", ScrollableContainer)

    def _line(self, text: str, cls: str = "system-text") -> Static:
        w = Static(text, markup=False, classes=cls)
        self._sc().mount(w)
        self._sc().scroll_end(animate=False)
        return w

    async def _user_turn(self, text: str):
        sc = self._sc()
        await sc.mount(Static("You", classes="turn-label-user"))
        await sc.mount(Static(text, markup=False, classes="msg-body"))
        sc.scroll_end(animate=False)

    async def _ai_turn(self) -> tuple[Static, Static, Static]:
        sc = self._sc()
        await sc.mount(Static("AI", classes="turn-label-ai"))
        thinking = Static("",              markup=False, classes="thinking-text")
        body     = Static("  ◌ pensando…", markup=False, classes="msg-loading")
        timing   = Static("",              markup=False, classes="system-text")
        await sc.mount(thinking)
        await sc.mount(body)
        await sc.mount(timing)
        sc.scroll_end(animate=False)
        return thinking, body, timing

    # ── Input ─────────────────────────────────────────────────────────────────

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "chat-input":
            return
        if self._approval_ev is not None:
            return  # approval pending — ignore
        text = event.value.strip()
        if not text:
            return
        event.input.clear()
        if text.startswith("/"):
            self._cmd(text)
        else:
            await self._send(text)

    # ── Approval ──────────────────────────────────────────────────────────────

    async def on_approval_widget_done(self, event: ApprovalWidget.Done) -> None:
        self._approval_ok = event.approved
        if self._approval_ev:
            self._approval_ev.set()

    async def _ask_approval(self, tool_name: str, args_str: str) -> bool:
        sc  = self._sc()
        wgt = ApprovalWidget(tool_name, args_str)
        await sc.mount(wgt)
        sc.scroll_end(animate=False)

        self._approval_ev = asyncio.Event()
        self._approval_ok = False
        await self._approval_ev.wait()
        self._approval_ev = None

        icon = "✓" if self._approval_ok else "✗"
        cls  = "tool-ok" if self._approval_ok else "tool-fail"
        result_w = Static(f"  {icon}  {tool_name}",
                          markup=False, classes=cls)
        await wgt.remove()
        await sc.mount(result_w)
        sc.scroll_end(animate=False)

        try:
            self.query_one("#chat-input", Input).focus()
        except NoMatches:
            pass

        return self._approval_ok

    # ── Commands ──────────────────────────────────────────────────────────────

    @work
    async def _cmd(self, text: str) -> None:
        parts = text.split()
        cmd   = parts[0].lower()

        if cmd == "/model":
            res = await self.push_screen_wait(ModelPickerScreen(self._config))
            if res:
                prov, model = res
                if not self._config.has_key(prov):
                    key = await self.push_screen_wait(KeyInputScreen(prov, self._config))
                    if not key:
                        self._line("Sin key — modelo no cambiado.")
                        return
                self._config.set_active(prov, model)
                await self._action_new_session()

        elif cmd == "/session":
            res = await self.push_screen_wait(SessionPickerScreen(self._mgr))
            if res:
                action, sid = res
                if action == "open":
                    await self._load_session(sid)

        elif cmd in ("/new", "/n"):
            await self._action_new_session()

        elif cmd == "/key" and len(parts) >= 3:
            prov, key = parts[1].lower(), parts[2]
            if prov in PROVIDERS:
                self._config.set_key(prov, key)
                self._line(f"Key guardada para {prov}.")
                if self._session and self._session.provider == prov:
                    self._rebuild_bot()
            else:
                self._line(f"Proveedor desconocido: {prov}")

        elif cmd == "/help":
            self._line(
                "/model          — cambiar modelo\n"
                "/session        — sesiones anteriores\n"
                "/new            — nueva sesión\n"
                "/key <prov> <k> — guardar API key\n"
                "ctrl+n          — nueva sesión  ·  ctrl+q — salir"
            )
        else:
            self._line(f"Comando desconocido: {cmd}. Escribe /help.")

    async def _send(self, text: str):
        if self._streaming:
            return
        if not self._session:
            self._line("Sin sesión activa. Configura tu API key con /key.")
            return
        if not self._bot:
            self._line("Bot no listo. Usa /key <proveedor> <apikey>.")
            return
        await self._user_turn(text)
        self._session.add_message("user", text)
        self.run_bot(text)

    # ── Streaming worker ──────────────────────────────────────────────────────

    @work(exclusive=True, thread=False)
    async def run_bot(self, text: str) -> None:
        self._streaming = True
        if self._hdr:
            self._hdr.set_busy(True)
        t_start = time.monotonic()

        thinking_w, body_w, timing_w = await self._ai_turn()

        full_thinking    = ""
        full_response    = ""
        got_first_token  = False
        tool_widgets:    dict[str, Static] = {}   # key → pending Static
        tool_timers:     dict[str, float]  = {}
        tool_call_count: dict[str, int]    = {}

        try:
            from langchain_core.messages import AIMessageChunk

            goal        = text
            thread_id   = self._session.id

            # ── Streaming loop: re-enters after each interrupt ────────────────
            while True:
                interrupted   = False
                interrupt_tool = ""
                interrupt_args = ""

                async for stream_mode, payload in self._bot.astream_events(
                    goal, mode="ask", thread_id=thread_id
                ):
                    sc = self._sc()

                    # ── Token chunks ─────────────────────────────────────────
                    if stream_mode == "messages":
                        chunk, _ = payload
                        if not isinstance(chunk, AIMessageChunk):
                            continue
                        content = chunk.content

                        if isinstance(content, list):
                            for part in content:
                                if isinstance(part, str) and part:
                                    if not got_first_token:
                                        got_first_token = True
                                        body_w.set_class(False, "msg-loading")
                                        body_w.set_class(True,  "msg-body")
                                    full_response += part
                                    body_w.update(full_response)
                                elif isinstance(part, dict):
                                    if part.get("type") == "thinking":
                                        t = part.get("thinking", "")
                                        if t:
                                            full_thinking += t
                                            preview = full_thinking[:300]
                                            if len(full_thinking) > 300:
                                                preview += "…"
                                            thinking_w.update(f"💭 {preview}")
                                    else:
                                        c = part.get("text", "") or part.get("content", "")
                                        if c:
                                            if not got_first_token:
                                                got_first_token = True
                                                body_w.set_class(False, "msg-loading")
                                                body_w.set_class(True,  "msg-body")
                                            full_response += str(c)
                                            body_w.update(full_response)
                        elif isinstance(content, str) and content:
                            if not got_first_token:
                                got_first_token = True
                                body_w.set_class(False, "msg-loading")
                                body_w.set_class(True,  "msg-body")
                            full_response += content
                            body_w.update(full_response)

                        sc.scroll_end(animate=False)

                    # ── Node updates ──────────────────────────────────────────
                    elif stream_mode == "updates":
                        for node_name, update in payload.items():

                            if node_name == "agent":
                                for ev in update.get("status_events", []):
                                    if ev.get("type") == "retrying":
                                        self._line(
                                            f"⟳ Rate limit — reintento {ev['attempt']}, "
                                            f"espera {ev['wait_s']:.1f}s"
                                        )

                                msgs = update.get("messages", [])
                                last = msgs[-1] if msgs else None
                                if last and getattr(last, "tool_calls", None):
                                    for tc in last.tool_calls:
                                        name  = tc.get("name", "unknown")
                                        args  = tc.get("args", {})
                                        pairs = ", ".join(
                                            f"{k}={repr(v)[:40]}" for k, v in args.items()
                                        )[:120]
                                        n   = tool_call_count.get(name, 0)
                                        tool_call_count[name] = n + 1
                                        key = f"{name}#{n}"
                                        tool_timers[key] = time.monotonic()
                                        tw = Static(
                                            f"  ⟳  {name}({pairs})",
                                            markup=False, classes="tool-pending",
                                        )
                                        tool_widgets[key] = tw
                                        await sc.mount(tw)
                                        sc.scroll_end(animate=False)

                                if update.get("final_report"):
                                    if not got_first_token:
                                        got_first_token = True
                                        body_w.set_class(False, "msg-loading")
                                        body_w.set_class(True,  "msg-body")
                                    full_response = update["final_report"]
                                    body_w.update(full_response)

                            elif node_name == "tools":
                                done_count: dict[str, int] = {}
                                for t in update.get("tools_executed", []):
                                    name   = t.get("tool_name", "?")
                                    status = t.get("status", "?")
                                    out    = str(t.get("output", ""))[:100]
                                    n      = done_count.get(name, 0)
                                    done_count[name] = n + 1
                                    key     = f"{name}#{n}"
                                    elapsed = time.monotonic() - tool_timers.pop(key, t_start)
                                    ok      = status == "success"
                                    icon    = "✓" if ok else "✗"
                                    cls     = "tool-ok" if ok else "tool-fail"
                                    line    = f"  {icon}  {name}  {elapsed:.2f}s  →  {out}"
                                    tw = tool_widgets.pop(key, None)
                                    if tw:
                                        tw.set_class(False, "tool-pending")
                                        tw.set_class(True, cls)
                                        tw.update(line)
                                    else:
                                        await sc.mount(Static(line, markup=False, classes=cls))
                                    sc.scroll_end(animate=False)

                            elif node_name == "__interrupt__":
                                # Interrupt detected — collect info, break inner loop
                                iv = update[0].value if update else {}
                                interrupt_tool = iv.get("tool", iv.get("tool_name", "?"))
                                interrupt_args = str(iv.get("params", {}))[:200]
                                interrupted = True

                if not interrupted:
                    break

                # ── Ask approval and resume ───────────────────────────────────
                approved = await self._ask_approval(interrupt_tool, interrupt_args)
                self._bot.set_resume_command({"approved": approved})
                goal = None   # resume pass: same thread_id, no new goal

        except Exception as exc:
            import traceback
            self._line(f"Error: {exc}")
        finally:
            self._streaming = False
            if self._hdr:
                self._hdr.set_busy(False)

        if not full_thinking:
            await thinking_w.remove()

        if not got_first_token:
            await body_w.remove()
        else:
            elapsed = time.monotonic() - t_start
            timing_w.update(f"  ⏱ {elapsed:.2f}s")

        if full_response:
            self._session.add_message("assistant", full_response)
            self._session.save()
            if self._hdr:
                tok = self._session.tokens_in + self._session.tokens_out
                self._hdr.update_stats(tok, self._session.cost)

    # ── Session actions ───────────────────────────────────────────────────────

    async def action_new_session(self):
        await self._action_new_session()

    async def _action_new_session(self):
        prov  = self._config.active_provider
        model = self._config.active_model
        if not prov or not model:
            self._line("Sin modelo configurado. Usa /model.")
            return
        self._session = self._mgr.new_session(prov, model)
        self._rebuild_bot()
        sc = self._sc()
        await sc.remove_children()
        self._refresh_hdr()
        self._line(f"Nueva sesión — {prov}/{model}")

    async def _load_session(self, session_id: str):
        try:
            session = self._mgr.load(session_id)
        except FileNotFoundError:
            self._line(f"Sesión no encontrada: {session_id}")
            return
        self._session = session
        if self._config.has_key(session.provider):
            self._config.set_active(session.provider, session.model)
            self._rebuild_bot()
        sc = self._sc()
        await sc.remove_children()
        for msg in session.messages:
            lbl = "You" if msg["role"] == "user" else "AI"
            cls = "turn-label-user" if msg["role"] == "user" else "turn-label-ai"
            await sc.mount(Static(lbl, classes=cls))
            await sc.mount(Static(msg.get("content", ""), markup=False, classes="msg-body"))
        self._refresh_hdr()
        sc.scroll_end(animate=False)
