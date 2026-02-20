from dataclasses import dataclass, field
from typing import Optional, Any, Dict
from datetime import datetime

@dataclass
class ExecutionResult:
    """
    Estructura de retorno estandarizada para todas las ejecuciones.
    Nunca lanza excepciones, encapsula el éxito o fallo.
    """
    # Core
    success: bool
    output: str                         # Resultado legible por el LLM
    error: Optional[str] = None         # None si success=True

    # Metadata
    tool_name: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    risk_level: int = 0
    duration_ms: int = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Para síntesis de tools
    is_synthesized: bool = False
    synthesized_code: Optional[str] = None

    def to_llm_context(self) -> str:
        """Serialización optimizada para inyectar en el contexto del orquestador."""
        status = "SUCCESS" if self.success else "FAILURE"
        base = f"[{status}] tool={self.tool_name} ({self.duration_ms}ms)\n"
        if self.success:
            return base + f"Output:\n{self.output}"
        else:
            return base + f"Error:\n{self.error}\nPartial output:\n{self.output}"
