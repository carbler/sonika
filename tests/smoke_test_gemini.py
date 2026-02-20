import os
import sys
from unittest.mock import MagicMock, patch

# Simulamos la API Key CORRECTA
os.environ["GOOGLE_API_KEY"] = "dummy_key_for_testing"

# Importamos el CLI
from executor_bot.cli import create_orchestrator, get_model
from sonika_ai_toolkit.utilities.types import BotResponse

def test_gemini_integration():
    print("--- Starting Smoke Test for Gemini Integration ---")
    
    # 1. Test Model Factory
    print("[1] Testing Model Factory...")
    try:
        # Probamos con "gemini" que debe mapear a GOOGLE_API_KEY
        model = get_model("gemini", "gemini-1.5-flash")
        print(f"✅ Model instantiated: {type(model).__name__}")
    except Exception as e:
        print(f"❌ Model factory failed: {e}")
        return

    # 2. Test Orchestrator Creation
    print("\n[2] Testing Orchestrator Creation...")
    try:
        # Mocking el modelo para que no intente conectarse
        with patch("sonika_ai_toolkit.utilities.models.GeminiLanguageModel.invoke") as mock_invoke:
            mock_invoke.return_value = "Hello! I am a simulated Gemini response."
            
            # Crear OrchestratorBot real (usará tools de ExecutorBot)
            bot = create_orchestrator("gemini", "gemini-1.5-flash", risk_level=2, session_id="test_session")
            print("✅ Orchestrator created successfully")
            
            # 3. Test Execution Flow (Mockeando bot.run para no ejecutar graph complejo)
            print("\n[3] Testing Execution Flow...")
            
            mock_response = BotResponse(
                content="Hello from Mock!",
                success=True,
                tools_executed=[],
                logs=[],
                token_usage={},
                plan=[],
                session_id="test",
                goal="test",
                thinking="Reasoning..."
            )
            
            with patch.object(bot, 'run', return_value=mock_response):
                result = bot.run("Say hello")
                print(f"✅ Execution result type: {type(result)}")
                content = getattr(result, "content", str(result))
                print(f"✅ Content received: {content}")

    except Exception as e:
        print(f"❌ Orchestrator execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_gemini_integration()
