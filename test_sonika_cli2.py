import asyncio
from dotenv import load_dotenv
load_dotenv()
from sonika.interfaces.console.app import ConsoleApp

def test():
    app = ConsoleApp()
    app.start_bot("gemini", "gemini-3-flash-preview", 2, "test-session")
    
    # Probando herramienta
    content, duration = app.run_turn("Por favor crea un archivo test_sonika.txt con la palabra hola")
    print("\n--- CONTENT ---")
    print(content)
    print(f"\n--- DURATION: {duration:.2f}s ---")
    
    # Check si interrupt es detectado correctamente (debería lanzar a consola)

if __name__ == "__main__":
    test()
