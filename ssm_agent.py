"""
SSM-1.0 — Project Buddy
Local LLaMA agent via Ollama | pb development
"""

import json
import datetime
from typing import Callable

import ollama


# ── Identity ──────────────────────────────────────────────────────────────────

AGENT_NAME = "SSM-1.0"
AGENT_MODEL = "auto"     # "auto" = detect at startup, or set explicitly e.g. "llama3.2"

SYSTEM_PROMPT = """\
You are SSM-1.0, the AI project buddy for pb development — a Flask web application.

YOUR IDENTITY:
- Your name is SSM-1.0. Always introduce yourself as SSM-1.0.
- You are NOT Claude, NOT GPT, NOT any other AI. You are SSM-1.0.
- If someone asks "who are you?" answer: "I'm SSM-1.0, your project buddy for pb development."

YOUR JOB:
- Help the developer write, debug, and improve this Flask codebase
- Answer questions about architecture, routes, models, and services
- Be direct, concise, and technically precise
- Proactively flag issues or improvements you spot

PROJECT CONTEXT:
- Flask 3.1 app using application factory pattern (create_app in app.py)
- PostgreSQL + SQLAlchemy 2.0, Flask-Migrate for migrations
- Real-time: Flask-SocketIO + Redis + eventlet
- Auth: Flask-Login
- File storage: AWS S3 via boto3
- Routes in routes/, models in models.py, config in config.py
- Extensions (db, socketio, login_manager) imported from extensions.py

TOOL USE:
When you need a tool, respond ONLY with this exact JSON — no extra text:
{
  "tool": "<tool_name>",
  "args": { ... }
}
After receiving the tool result, continue your response normally.
If no tool is needed, reply in plain text.

AVAILABLE TOOLS:
- read_file(path)           — read a project file
- write_file(path,content)  — write/update a file
- run_shell(command)        — run shell command (flask, pip, git, etc.)
- get_datetime()            — current date/time
- search_web(query)         — web search (activate in tools.py)

Today's date: """ + datetime.date.today().isoformat()


# ── Tool registry ──────────────────────────────────────────────────────────────

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Callable] = {}

    def register(self, name: str, fn: Callable):
        self._tools[name] = fn

    def call(self, name: str, args: dict) -> str:
        if name not in self._tools:
            return f"[ERROR] Unknown tool: {name}"
        try:
            return str(self._tools[name](**args))
        except Exception as e:
            return f"[ERROR] Tool '{name}' raised: {e}"

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())


# ── Agent ─────────────────────────────────────────────────────────────────────

class SSMAgent:
    """
    SSM-1.0 — ReAct-style agent loop over a local Ollama model.

    Usage:
        agent = SSMAgent()
        print(agent.chat("Who are you?"))
    """

    def __init__(
        self,
        model: str = AGENT_MODEL,
        tools: ToolRegistry | None = None,
        verbose: bool = False,
    ):
        self.model = self._resolve_model(model)
        self.tools = tools or ToolRegistry()
        self.verbose = verbose
        self.history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    @staticmethod
    def _resolve_model(model: str) -> str:
        """If model is 'auto', detect the first available Ollama model."""
        if model != "auto":
            return model
        try:
            models = ollama.list().get("models", [])
            if not models:
                print(f"[{AGENT_NAME}] No models found. Pull one with: ollama pull llama3.2")
                raise SystemExit(1)
            # Prefer llama models, otherwise take the first available
            llama = [m for m in models if "llama" in m.get("name", "").lower()]
            chosen = llama[0]["name"] if llama else models[0]["name"]
            print(f"  [auto-detect] Using model: {chosen}")
            return chosen
        except Exception as e:
            if "SystemExit" in type(e).__name__:
                raise
            print(f"[{AGENT_NAME}] Could not connect to Ollama: {e}")
            print(f"  Make sure Ollama is running: open -a Ollama  or  ollama serve")
            raise SystemExit(1)

    def chat(self, user_message: str) -> str:
        """Send a message and return SSM-1.0's final reply."""
        self.history.append({"role": "user", "content": user_message})

        for _ in range(10):
            reply = self._call_model()
            tool_call = self._parse_tool_call(reply)

            if tool_call is None:
                self.history.append({"role": "assistant", "content": reply})
                return reply

            tool_name = tool_call["tool"]
            tool_args = tool_call.get("args", {})

            if self.verbose:
                print(f"\n  [{AGENT_NAME} tool] {tool_name}({tool_args})")

            tool_result = self.tools.call(tool_name, tool_args)

            if self.verbose:
                preview = tool_result[:300] + ("…" if len(tool_result) > 300 else "")
                print(f"  [result] {preview}")

            self.history.append({"role": "assistant", "content": reply})
            self.history.append({
                "role": "user",
                "content": f"[Tool result for {tool_name}]\n{tool_result}",
            })

        return f"[{AGENT_NAME}] Reached max tool-call rounds without a final answer."

    def reset(self):
        """Clear conversation history, keep system prompt."""
        self.history = [self.history[0]]

    def _call_model(self) -> str:
        response = ollama.chat(
            model=self.model,
            messages=self.history,
            options={"temperature": 0.7},
        )
        return response["message"]["content"].strip()

    @staticmethod
    def _parse_tool_call(text: str) -> dict | None:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        try:
            data = json.loads(text[start:end])
            if "tool" in data:
                return data
        except json.JSONDecodeError:
            pass
        return None


# ── CLI ────────────────────────────────────────────────────────────────────────

def start_cli(agent: SSMAgent):
    from tools import register_default_tools
    register_default_tools(agent.tools)

    print(f"\n{'='*54}")
    print(f"  {AGENT_NAME} — pb development  |  model: {agent.model}")
    print(f"  'reset' = clear history  |  'exit' = quit")
    print(f"{'='*54}\n")
    print(f"  {AGENT_NAME}: Hey! I'm SSM-1.0, your project buddy for pb development.")
    print(f"         Tools ready: {', '.join(agent.tools.list_tools())}\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{AGENT_NAME}: Later!\n")
            break

        if not user_input:
            continue
        if user_input.lower() == "exit":
            print(f"{AGENT_NAME}: Later!")
            break
        if user_input.lower() == "reset":
            agent.reset()
            print("[History cleared]\n")
            continue

        reply = agent.chat(user_input)
        print(f"\n{AGENT_NAME}: {reply}\n")
