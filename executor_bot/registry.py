from typing import List, Optional, Dict, Type
from .tools.base import BaseTool
import logging

logger = logging.getLogger(__name__)

class ToolRegistry:
    """
    Catálogo centralizado de herramientas.
    Permite registrar, descubrir y (futuramente) sintetizar tools.
    """
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        
    def register(self, tool: BaseTool) -> None:
        """Registra una herramienta en el catálogo."""
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool: {tool.name}")
        self._tools[tool.name] = tool
        
    def get(self, name: str) -> Optional[BaseTool]:
        """Obtiene una herramienta por su nombre exacto."""
        return self._tools.get(name)
    
    def get_tools(self) -> List[BaseTool]:
        """Retorna la lista de objetos BaseTool registrados."""
        return list(self._tools.values())
        
    def list_all(self) -> List[Dict[str, str]]:
        """Lista todas las herramientas disponibles con su descripción."""
        return [
            {"name": t.name, "description": t.description, "risk_level": str(t.risk_level)}
            for t in self._tools.values()
        ]

    # --- Placeholders para funcionalidades avanzadas ---
    
    def find_alternatives(self, goal: str, failed_tool: str) -> List[BaseTool]:
        """
        [PLACEHOLDER] Busca herramientas alternativas semánticamente similares.
        Requiere implementación de vector search.
        """
        return []

    def synthesize(self, name: str, description: str, example_input: dict) -> BaseTool:
        """
        [PLACEHOLDER] Sintetiza una nueva herramienta usando LLM.
        """
        raise NotImplementedError("Tool synthesis not yet implemented")
