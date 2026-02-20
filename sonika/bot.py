import time
import logging
import traceback
from typing import List, Optional, Any, Dict
from datetime import datetime

from .result import ExecutionResult
from .registry import ToolRegistry
from .tools.base import BaseTool
from .tools import TOOL_GROUPS

logger = logging.getLogger(__name__)

class ExecutorBot:
    """
    La capa de ejecución que consume el OrchestratorBot.
    Responsabilidad única: recibir instrucción -> ejecutar -> retornar resultado.
    """
    
    def __init__(
        self,
        tools: Optional[List[Any]] = None,
        timeout: int = 30,
        sandbox: bool = True,
    ):
        self.registry = ToolRegistry()
        self.timeout = timeout
        self.sandbox = sandbox
        
        # Registrar tools iniciales
        if tools:
            for item in tools:
                if isinstance(item, BaseTool):
                    self.registry.register(item)
                elif isinstance(item, str):
                    if item in TOOL_GROUPS:
                        # Cargar grupo por nombre (ej: "bash", "files")
                        for ToolClassOrInstance in TOOL_GROUPS[item]:
                            # Si es una clase, instanciarla. Si es instancia, registrarla directamente.
                            if isinstance(ToolClassOrInstance, type):
                                self.registry.register(ToolClassOrInstance())
                            else:
                                self.registry.register(ToolClassOrInstance)
                    else:
                        logger.warning(f"Unknown tool group: {item}")
                else:
                    logger.warning(f"Invalid tool type: {type(item)}")
                
    def execute(
        self,
        tool_name: str,
        params: Dict[str, Any],
        risk_level: int = 0,
    ) -> ExecutionResult:
        """
        Ejecuta una herramienta por nombre con los parámetros dados.
        Nunca lanza excepciones, siempre retorna ExecutionResult.
        """
        start_time = time.time()
        
        try:
            # 1. Buscar la herramienta
            tool = self.registry.get(tool_name)
            if not tool:
                return self._create_error_result(
                    f"Tool '{tool_name}' not found in registry.",
                    tool_name, params, start_time
                )
            
            # 2. Validar riesgo (opcional, por ahora solo informativo)
            
            # 3. Ejecutar
            try:
                if hasattr(tool, "invoke"):
                    output = tool.invoke(params)
                else:
                    output = tool.run(params)
            except Exception as e:
                # Capturar error de ejecución interna del tool
                return self._create_error_result(
                    f"Tool execution failed: {str(e)}\n{traceback.format_exc()}",
                    tool_name, params, start_time
                )

            # 4. Retornar éxito
            duration = int((time.time() - start_time) * 1000)
            
            output_str = str(output) if output is not None else ""
            
            risk = getattr(tool, "risk_level", getattr(tool, "risk_hint", 0))
            
            return ExecutionResult(
                success=True,
                output=output_str,
                tool_name=tool_name,
                params=params,
                risk_level=risk,
                duration_ms=duration
            )

        except Exception as e:
            # Captura de errores catastróficos fuera del tool execution
            return self._create_error_result(
                f"System error in executor: {str(e)}\n{traceback.format_exc()}",
                tool_name, params, start_time
            )

    def _create_error_result(
        self, 
        error_msg: str, 
        tool_name: str, 
        params: Dict[str, Any], 
        start_time: float
    ) -> ExecutionResult:
        duration = int((time.time() - start_time) * 1000)
        return ExecutionResult(
            success=False,
            output="",
            error=error_msg,
            tool_name=tool_name,
            params=params,
            duration_ms=duration
        )
