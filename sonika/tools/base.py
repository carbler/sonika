from typing import Type, Any, Optional
from pydantic import BaseModel
from langchain_core.tools import BaseTool as LCBaseTool

class BaseTool(LCBaseTool):
    """
    Clase base para todas las herramientas del ExecutorBot.
    Extiende LangChain BaseTool pero añade atributos de riesgo.
    """
    risk_level: int = 0  # 0: Safe, 1: Side effects, 2: Destructive
    
    # Forzar implementación en subclases si es necesario, 
    # aunque LangChain ya maneja esto.
    
    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """
        Método síncrono que debe ser implementado por cada tool.
        """
        raise NotImplementedError("Tool must implement _run")
        
    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        """
        Método asíncrono opcional.
        """
        raise NotImplementedError("Tool does not support async")
