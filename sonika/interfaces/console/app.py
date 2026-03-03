import time
import sys
import asyncio
from typing import Optional, Dict, Any

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML

from langchain_core.messages import AIMessageChunk

from .ui import (
    console,
    ConsoleInterface,
    print_welcome,
    print_result,
    print_model_info,
)

class ConsoleApp:
    def __init__(self):
        self.provider = "gemini"
        self.model_name = "gemini-3-flash-preview"
        self.session = "default"
        self.bot = None
        self.ui = ConsoleInterface()
        self.modes = ["plan", "ask", "auto"]
        self.mode = "ask"

    def cycle_mode(self):
        idx = self.modes.index(self.mode)
        self.mode = self.modes[(idx + 1) % len(self.modes)]

    def get_mode_name(self) -> str:
        return self.mode.upper()

    def start_bot(self, provider: str, model_name: str, risk: int, session: str, prompts: Optional[str] = None):
        from sonika.factory import create_orchestrator
        
        self.provider = provider
        self.model_name = model_name
        self.session = session
        
        console.print(f"[dim]Inicializando motor LangGraph {provider}/{model_name} (sesión: {session})…[/dim]")
        
        # Eliminamos callbacks ya que la interfaz maneja el stream
        self.bot = create_orchestrator(
            provider, 
            model_name, 
            risk, 
            session, 
            prompts,
        )
        
        # Pre-warm connection asíncrono
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.bot.a_prewarm())
            else:
                loop.run_until_complete(self.bot.a_prewarm())
        except Exception:
            # Fallback for cli contexts
            pass

    async def _process_stream(self, stream_gen):
        """Consume el generador de astream_events y actualiza la UI."""
        interrupt_data = None
        final_content = None
        last_text_buffer = ""

        try:
            async for stream_mode, payload in stream_gen:
                if stream_mode == "messages":
                    chunk, metadata = payload
                    if isinstance(chunk, AIMessageChunk):
                        # Extract thinking and accumulate plain text as fallback
                        if isinstance(chunk.content, list):
                            for part in chunk.content:
                                if isinstance(part, dict):
                                    if part.get("type") == "thinking":
                                        self.ui.on_thought(part.get("thinking", ""))
                                    else:
                                        last_text_buffer += str(part.get("text", "") or part.get("content", ""))
                        elif isinstance(chunk.content, str):
                            last_text_buffer += chunk.content

                elif stream_mode == "updates":
                    # Mapeo de eventos
                    for node_name, update in payload.items():
                        if node_name == "tools":
                            tools_executed = update.get("tools_executed", [])
                            for t in tools_executed:
                                if t.get("status") == "success":
                                    self.ui.on_tool_end(t.get("tool_name"), t.get("output"))
                                elif t.get("status") == "error":
                                    self.ui.on_error(t.get("tool_name"), t.get("output"))

                        elif node_name == "agent":
                            msgs = update.get("messages", [])
                            last_msg = msgs[-1] if msgs else None

                            # Detect tool calls first so we never capture a stale
                            # final_report when the agent is still mid-execution.
                            has_tool_calls = bool(last_msg and getattr(last_msg, "tool_calls", None))

                            if has_tool_calls:
                                for tcall in last_msg.tool_calls:
                                    self.ui.on_tool_start(tcall.get("name", "unknown"), tcall.get("args", {}))
                                # Reset buffer — agent is still working
                                last_text_buffer = ""
                            else:
                                # Only accept final_report when no tools are being called.
                                if update.get("final_report"):
                                    final_content = update.get("final_report")
                                elif last_msg and hasattr(last_msg, "content"):
                                    c = last_msg.content
                                    if isinstance(c, list):
                                        parts = []
                                        for p in c:
                                            if isinstance(p, str):
                                                parts.append(p)
                                            elif isinstance(p, dict) and p.get("type") != "thinking":
                                                parts.append(str(p.get("text", "") or p.get("content", "")))
                                        c = "\n".join(parts)
                                    if c:
                                        final_content = c


                # Detectar interrupción usando el método de LangGraph state o catching payload
                if stream_mode == "updates" and '__interrupt__' in payload:
                    # LangGraph >= 0.2 __interrupt__ channel
                    interrupts = payload['__interrupt__']
                    if interrupts:
                        interrupt_data = interrupts[0].value

        except Exception as e:
            # We don't crash stream errors aggressively in terminal
            pass

        # Fallback: use accumulated messages-stream text when updates stream
        # didn't produce a final_report (e.g. simple conversational turns).
        if final_content is None and last_text_buffer.strip():
            final_content = last_text_buffer.strip()

        return final_content, interrupt_data

    def run_turn(self, user_msg: str) -> tuple[str, float]:
        t0 = time.time()
        self.ui.start_turn()
        
        async def run_async():
            final_content = None
            
            # Start initial generation stream
            stream_gen = self.bot.astream_events(user_msg, mode=self.mode, thread_id=self.session)
            content, interrupt_data = await self._process_stream(stream_gen)
            
            if content:
                final_content = content
                
            # Handle Interrupt loop
            while True:
                config = {"configurable": {"thread_id": self.session}}
                state = self.bot.graph.get_state(config)
                
                # Check if graph halted on a task interrupt
                if state.tasks and state.tasks[0].interrupts:
                    interrupt_data = state.tasks[0].interrupts[0].value
                    
                    approved = self.ui.on_interrupt(interrupt_data)
                    self.bot.set_resume_command({"approved": approved})
                    
                    # Consume resume stream
                    resume_gen = self.bot.astream_events(None, mode=self.mode, thread_id=self.session)
                    content, _ = await self._process_stream(resume_gen)
                    if content:
                        final_content = content
                else:
                    break
                    
            return final_content, time.time() - t0

        import nest_asyncio
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        content, duration = loop.run_until_complete(run_async())
        
        self.ui.end_turn()
        return content, duration

    def run_interactive_loop(self):
        print_welcome(f"{self.provider}:{self.model_name}")
        
        session = PromptSession()
        bindings = KeyBindings()

        @bindings.add('tab')
        def _(event):
            self.cycle_mode()
            event.app.invalidate()

        def get_rprompt():
            mode = self.get_mode_name()
            color = "green" if mode == "AUTO" else "yellow" if mode == "ASK" else "red"
            return HTML(f"<style fg='{color}'>[{mode}]</style> <dim>{self.model_name}</dim>")

        while True:
            try:
                # Prompt estilo minimalista
                prompt_text = HTML("<b><cyan>sonika ❯</cyan></b> ")
                user_input = session.prompt(
                    prompt_text, 
                    key_bindings=bindings, 
                    rprompt=get_rprompt
                )

                if user_input.lower() in ("/exit", "exit", "quit", "q"):
                    console.print("[dim]Goodbye.[/dim]")
                    break

                if not user_input.strip():
                    continue

                if user_input.strip() == "/help":
                    console.print(
                        "\n[bold green]Ayuda de Sonika[/bold green]\n"
                        "  [cyan]TAB[/cyan]     : Cambia entre modo PLAN, ASK, AUTO.\n"
                        "  [cyan]/model[/cyan]  : Muestra modelo actual.\n"
                        "  [cyan]/model p:n[/cyan]: Cambia de modelo.\n"
                        "  [cyan]/exit[/cyan]   : Salir.\n"
                    )
                    continue

                if user_input.strip().startswith("/model"):
                    parts = user_input.strip().split(maxsplit=1)
                    if len(parts) == 1:
                        print_model_info(self.provider, self.model_name)
                        continue
                    new_str = parts[1].strip()
                    if ":" not in new_str:
                         console.print("[red]Formato inválido. Use provider:name[/red]")
                         continue
                    new_provider, new_model_name = new_str.split(":", 1)
                    try:
                        self.start_bot(new_provider, new_model_name, 2, self.session)
                        console.print(f"[green]✓[/green] Modelo cambiado a {self.provider}:{self.model_name}")
                    except Exception as e:
                        console.print(f"[red]Error:[/red] {e}")
                    continue

                # Normal turn
                content, duration = self.run_turn(user_input)
                
                # Render result outside live box
                print_result(content)
                console.print(f"[dim]⏱ {duration:.2f}s[/dim]")

            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Goodbye.[/dim]")
                break
            except Exception as e:
                console.print(f"[red]Error in loop:[/red] {e}")
                import traceback
                console.print(traceback.format_exc())
