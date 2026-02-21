import asyncio
from dotenv import load_dotenv
load_dotenv()
from sonika.interfaces.console.app import ConsoleApp

def test():
    app = ConsoleApp()
    app.start_bot("gemini", "gemini-3-flash-preview", 2, "test-session")
    
    # Try using ask mode to get a diff preview
    app.mode = "ask"
    
    # Simulate testing interrupt directly
    # We will just write a file
    print("\n--- CONTENT (ASK) ---")
    content, duration = app.run_turn("Modifica un archivo llamado tests_diff.txt que diga 'hello world 2'")
    print(content)
    print(f"\n--- DURATION: {duration:.2f}s ---")

if __name__ == "__main__":
    test()
