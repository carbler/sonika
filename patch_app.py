import re

with open("sonika/interfaces/console/app.py", "r") as f:
    content = f.read()

# Fix final_content extraction
old_code = """                        elif node_name == "agent":
                            if update.get("final_report"):
                                final_content = update.get("final_report")"""

new_code = """                        elif node_name == "agent":
                            if update.get("final_report"):
                                final_content = update.get("final_report")
                            elif update.get("messages"):
                                msgs = update.get("messages")
                                if msgs:
                                    last_msg = msgs[-1]
                                    if hasattr(last_msg, "content") and not getattr(last_msg, "tool_calls", None):
                                        c = last_msg.content
                                        if isinstance(c, list):
                                            c = "\\n".join(str(p.get("text", "")) for p in c if isinstance(p, dict) and p.get("type") != "thinking")
                                        if c:
                                            final_content = c"""

content = content.replace(old_code, new_code)

with open("sonika/interfaces/console/app.py", "w") as f:
    f.write(content)

