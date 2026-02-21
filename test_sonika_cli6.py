import sys
import os
import pty
from unittest.mock import patch

def test_interactive():
    master, slave = pty.openpty()
    pid = os.fork()

    if pid == 0:
        # Child process
        os.close(master)
        os.setsid()
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        if slave > 2:
            os.close(slave)

        from dotenv import load_dotenv
        load_dotenv()
        from sonika.interfaces.console.app import ConsoleApp
        app = ConsoleApp()
        # Use a non-thinking model to avoid the thought_signature bug of langgraph+gemini
        app.start_bot("gemini", "gemini-2.5-flash", 2, "test-session")
        app.mode = "ask"
        content, duration = app.run_turn("Modifica un archivo llamado tests_diff.txt que diga 'hello world 2'")
        print(f"!!!SUCCESS!!! {content}")
        sys.exit(0)
    else:
        # Parent process
        os.close(slave)
        import time
        output = b""
        while b"[y/n]" not in output:
            try:
                output += os.read(master, 1024)
            except OSError:
                break
            
        print(output.decode())
        os.write(master, b"y\n")
        
        try:
            while True:
                out = os.read(master, 1024)
                if not out: break
                print(out.decode(), end="")
        except OSError:
            pass
            
        os.waitpid(pid, 0)

if __name__ == "__main__":
    test_interactive()
