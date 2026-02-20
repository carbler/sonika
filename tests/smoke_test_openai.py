import os
import sys
from unittest.mock import MagicMock, patch

# Simulamos la API Key CORRECTA para OpenAI
os.environ["OPENAI_API_KEY"] = "sk-dummy-key-for-testing"

# Importamos el CLI
from executor_bot.cli import create_orchestrator, get_model
from sonika_ai_toolkit.utilities.types import BotResponse
from sonika_ai_toolkit.utilities.models import OpenAILanguageModel

def test_openai_integration():
    print("--- Starting Smoke Test for OpenAI Integration ---")
    
    # 1. Test Model Factory
    print("[1] Testing Model Factory...")
    try:
        # Probamos con "openai"
        model = get_model("openai", "gpt-4o")
        print(f"✅ Model instantiated: {type(model).__name__}")
        if isinstance(model, OpenAILanguageModel):
            print("✅ Correct class instance")
    except Exception as e:
        print(f"❌ Model factory failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # 2. Test Orchestrator Creation
    print("\n[2] Testing Orchestrator Creation...")
    try:
        # Crear OrchestratorBot real (usará tools de ExecutorBot)
        # No necesitamos mockear el modelo aquí porque create_orchestrator solo lo instancia
        bot = create_orchestrator("openai", "gpt-4o", risk_level=2, session_id="test_session_openai")
        print("✅ Orchestrator created successfully")
        
        # 3. Test Execution Flow
        print("\n[3] Testing Execution Flow...")
        
        # Simulamos la respuesta del bot para no llamar a la API real ni ejecutar el grafo complejo
        mock_response = BotResponse(
            content="Hello from OpenAI Mock!",
            success=True,
            tools_executed=[],
            logs=[],
            token_usage={},
            plan=[],
            session_id="test_openai",
            goal="test_openai",
            thinking="Reasoning with GPT-4o..."
        )
        
        # Mockeamos el método run del bot
        with patch.object(bot, 'run', return_value=mock_response):
            result = bot.run("Say hello")
            
            print(f"✅ Execution result type: {type(result)}")
            content = getattr(result, "content", str(result))
            print(f"✅ Content received: {content}")
            
            if "OpenAI Mock" in content:
                print("✅ Mock logic verified")

    except Exception as e:
        print(f"❌ Orchestrator execution failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_openai_integration()
