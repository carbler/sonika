import asyncio
from dotenv import load_dotenv
load_dotenv()
from sonika.interfaces.console.app import ConsoleApp

def test():
    app = ConsoleApp()
    app.start_bot("gemini", "gemini-3-flash-preview", 2, "test-session")
    content, duration = app.run_turn("Escribe 'hola' en 3 lineas")
    print("\n--- CONTENT ---")
    print(content)
    print(f"\n--- DURATION: {duration:.2f}s ---")

if __name__ == "__main__":
    test()
