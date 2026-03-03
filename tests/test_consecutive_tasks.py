"""
Test de integración: Sonika recibe UNA sola instrucción y ejecuta 3 herramientas consecutivas.

Instrucción enviada al orquestador:
  "Crea el archivo /tmp/sonika_test.txt con el texto 'hello from sonika',
   luego léelo para verificar su contenido,
   y finalmente cuenta cuántas palabras tiene con bash."

El orquestador debe planificar y ejecutar: write_file → read_file → run_bash
"""
import os
import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture(scope="module")
def orchestrator():
    from sonika.factory import create_orchestrator
    return create_orchestrator(
        provider="gemini",
        model_name="gemini-2.0-flash",
        risk_level=2,
        session_id="test-consecutive",
    )


def test_instruccion_unica_tres_herramientas(orchestrator, tmp_path):
    target = str(tmp_path / "sonika_test.txt")

    result = orchestrator.run(
        goal=(
            f"Haz estas 3 cosas en orden: "
            f"1) Crea el archivo {target} con el texto 'hello from sonika'. "
            f"2) Lee ese archivo para confirmar su contenido. "
            f"3) Ejecuta bash para contar las palabras del archivo con: wc -w < {target}"
        )
    )

    # El orquestador debe haber tenido éxito general
    assert result.success, f"El orquestador reportó fallo.\nContent: {result.content}"

    # Deben haberse ejecutado al menos 3 herramientas
    tools = result.tools_executed
    assert len(tools) >= 3, (
        f"Se esperaban al menos 3 herramientas ejecutadas, se obtuvieron {len(tools)}.\n"
        f"Tools: {[t.get('tool_name') or t.get('name') for t in tools]}"
    )

    # Todas las ejecuciones deben haber sido exitosas
    failed = [t for t in tools if t.get("status") == "error"]
    assert not failed, f"Herramientas con error: {failed}"

    # El archivo debe existir en disco como efecto colateral
    assert os.path.exists(target), f"El archivo {target} no fue creado en disco"

    tool_names = [t.get("tool_name") or t.get("name") for t in tools]
    print(f"\nHerramientas ejecutadas: {tool_names}")
    print(f"Respuesta final: {result.content[:200]}")
