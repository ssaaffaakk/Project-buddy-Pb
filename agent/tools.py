"""
Built-in tools for SSM-1.0 (pb development).
Add custom tools by calling agent.tools.register(name, fn).
"""

import datetime
import os
import subprocess


def read_file(path: str) -> str:
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        return f"[ERROR] File not found: {path}"
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def write_file(path: str, content: str) -> str:
    path = os.path.expanduser(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Written {len(content)} characters to {path}"


def run_shell(command: str) -> str:
    """Run a shell command and return stdout + stderr."""
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    out = result.stdout.strip()
    err = result.stderr.strip()
    parts = []
    if out:
        parts.append(f"stdout:\n{out}")
    if err:
        parts.append(f"stderr:\n{err}")
    return "\n".join(parts) if parts else "(no output)"


def get_datetime() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def search_web(query: str) -> str:
    """
    Web search stub.
    To activate: pip install duckduckgo-search  then replace this with:

        from duckduckgo_search import DDGS
        results = DDGS().text(query, max_results=5)
        return "\\n".join(f"{r['title']}: {r['href']}\\n{r['body']}" for r in results)
    """
    return (
        f"[search_web] Stub — query='{query}'. "
        "Run: pip install duckduckgo-search and update this function."
    )


def register_default_tools(registry):
    """Register all built-in tools into a ToolRegistry."""
    registry.register("read_file", read_file)
    registry.register("write_file", write_file)
    registry.register("run_shell", run_shell)
    registry.register("get_datetime", get_datetime)
    registry.register("search_web", search_web)
