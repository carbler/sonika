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
        
        try:
            async for stream_mode, payload in stream_gen:
                if stream_mode == "messages":
                    chunk, metadata = payload
                    if isinstance(chunk, AIMessageChunk):
                        # Extract thinking
                        if isinstance(chunk.content, list):
                            for part in chunk.content:
                                if isinstance(part, dict) and part.get("type") == "thinking":
                                    self.ui.on_thought(part.get("thinking", ""))
                        
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
                            if update.get("final_report"):
                                final_content = update.get("final_report")
                            elif update.get("messages"):
                                msgs = update.get("messages")
                                if msgs:
                                    last_msg = msgs[-1]
                                    if hasattr(last_msg, "content") and not getattr(last_msg, "tool_calls", None):
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
            console.print(f"[bold red]Stream Error:[/bold red] {str(e)}")
            
        return final_content, interrupt_data

    def run_turn(self, user_msg: str) -> tuple[str, float]:
        t0 = time.time()
        
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
        return content, duration

    def run_interactive_loop(self):
        print_welcome(f"{self.provider}:{self.model_name}")
        
        session = PromptSession()
        bindings = KeyBindings()

        @bindings.add('tab')
        def _(event):
            self.cycle_mode()
            event.app.invalidate()

        def get_bottom_toolbar():
            mode = self.get_mode_name()
            color = "green" if mode == "AUTO" else "yellow" if mode == "ASK" else "red"
            return HTML(f'Mode: <style bg="{color}" fg="black"> {mode} </style> (TAB to switch) | /help /exit')

        while True:
            try:
                prompt_text = HTML(f'\n<b><cyan>Sonika</cyan></b> <dim>{self.provider}:{self.model_name}</dim>\n> ')
                user_input = session.prompt(prompt_text, key_bindings=bindings, bottom_toolbar=get_bottom_toolbar)

                if user_input.lower() in ("/exit", "exit", "quit", "q"):
                    console.print("[yellow]Hasta luego.[/yellow]")
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
                self.ui.on_result(content)
                console.print(f"[dim]⏱ {duration:.2f}s[/dim]")

            except KeyboardInterrupt:
                console.print("\n[yellow]Interrumpido. Escribe /exit para salir.[/yellow]")
            except Exception as e:
                console.print(f"[red]Error in loop:[/red] {e}")
                import traceback
                console.print(traceback.format_exc())
