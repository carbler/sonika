import asyncio
from dotenv import load_dotenv
load_dotenv()
from sonika.interfaces.console.app import ConsoleApp

def test():
    app = ConsoleApp()
    app.start_bot("gemini", "gemini-3-flash-preview", 2, "test-session")
    
    # Try using plan mode
    app.mode = "plan"
    content, duration = app.run_turn("Escribe un plan de 2 pasos para limpiar mi computadora")
    print("\n--- CONTENT (PLAN) ---")
    print(content)
    print(f"\n--- DURATION: {duration:.2f}s ---")

if __name__ == "__main__":
    test()
