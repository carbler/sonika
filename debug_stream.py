import asyncio
from dotenv import load_dotenv
load_dotenv()
from sonika.interfaces.console.app import ConsoleApp

async def test():
    app = ConsoleApp()
    app.start_bot("gemini", "gemini-3-flash-preview", 2, "test-session")
    
    stream_gen = app.bot.astream_events("Dime hola", mode="plan", thread_id="test-session")
    async for stream_mode, payload in stream_gen:
        if stream_mode == "updates":
            print(f"UPDATES: {payload}")

if __name__ == "__main__":
    asyncio.run(test())
