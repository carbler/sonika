import re

with open("sonika/interfaces/console/app.py", "r") as f:
    content = f.read()

# Fix final_content extraction
old_code = """                                            c = "\\n".join(str(p.get("text", "")) for p in c if isinstance(p, dict) and p.get("type") != "thinking")"""

new_code = """                                            parts = []
                                            for p in c:
                                                if isinstance(p, str):
                                                    parts.append(p)
                                                elif isinstance(p, dict) and p.get("type") != "thinking":
                                                    parts.append(str(p.get("text", "") or p.get("content", "")))
                                            c = "\\n".join(parts)"""

content = content.replace(old_code, new_code)

with open("sonika/interfaces/console/app.py", "w") as f:
    f.write(content)

