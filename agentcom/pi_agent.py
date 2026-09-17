"""Pi agent — wraps Pi CLI as the main agent harness.

Replaces the simple LLM loop with Pi's multi-turn agent:
- Session persistence via --session flag
- Tool calling with validation (read, bash, edit, write + custom)
- Streaming via JSON mode
- Multi-turn conversation
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PI_BIN = os.path.join(ROOT, "pi", "packages", "coding-agent", "dist", "cli.js")
SESSION_DIR = os.path.join(ROOT, "runs", "sessions")

# Track session IDs per conversation
_sessions: dict[str, str] = {}


def _get_key() -> str:
    """Resolve API key from vault."""
    sys.path.insert(0, ROOT)
    from agentcom.vault.store import Vault
    v = Vault(os.path.expanduser("~/.qpbot/vault.json"))
    usable = v.find(kind="llm-inference", tier="paid")
    for c in usable:
        try:
            key = v.resolve(c["name"], "dashboard-chat", "chat-session",
                            c["capability"])
            return key
        except ValueError:
            continue
    return ""


def _get_session_id(conversation_id: str) -> str:
    """Get or create Pi session ID for a conversation."""
    if conversation_id not in _sessions:
        os.makedirs(SESSION_DIR, exist_ok=True)
        _sessions[conversation_id] = str(uuid.uuid4())[:8]
    return _sessions[conversation_id]


def chat(message: str, conversation_id: str = "default",
         system_prompt: str = "", model: str = "mimo-v2.5") -> dict:
    """Send a message through Pi agent, get response.

    Returns: {"reply": str, "tools_called": list, "session_id": str}
    """
    key = _get_key()
    if not key:
        return {"reply": "No API key in vault.", "tools_called": [], "session_id": ""}

    session_id = _get_session_id(conversation_id)
    os.makedirs(SESSION_DIR, exist_ok=True)

    # Build Pi command
    cmd = [
        "node", PI_BIN,
        "--provider", "opencode-go",
        "--model", model,
        "--mode", "json",
        "--session", os.path.join(SESSION_DIR, f"{session_id}.jsonl"),
    ]

    # Add system prompt via --system-prompt if provided
    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt[:2000]])

    # The message to process
    cmd.extend(["-p", message[:4000]])

    env = os.environ.copy()
    env["OPENCODE_API_KEY"] = key
    env["PI_SESSION_DIR"] = SESSION_DIR

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=ROOT,
            env=env, timeout=120
        )
        output = result.stdout.strip()
    except subprocess.TimeoutExpired:
        return {"reply": "Pi agent timed out (120s).", "tools_called": [], "session_id": session_id}
    except Exception as e:
        return {"reply": f"Pi agent error: {e}", "tools_called": [], "session_id": session_id}

    # Parse JSON output — extract text and tool calls
    reply_parts = []
    tools_called = []
    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("type") == "message_update":
            msg_evt = event.get("assistantMessageEvent", {})
            if msg_evt.get("type") == "text_delta":
                reply_parts.append(msg_evt.get("delta", ""))
            elif msg_evt.get("type") == "text_end":
                pass  # content already accumulated

        elif event.get("type") == "tool_execution_start":
            tool_name = event.get("toolName", "")
            tools_called.append(tool_name)

    reply = "".join(reply_parts).strip()
    if not reply:
        # Fallback: try to extract from final message
        for line in output.split("\n"):
            try:
                event = json.loads(line.strip())
                if event.get("type") == "agent_end":
                    msgs = event.get("messages", [])
                    for m in msgs:
                        if m.get("role") == "assistant":
                            for c in m.get("content", []):
                                if c.get("type") == "text":
                                    reply = c.get("text", "")
            except (json.JSONDecodeError, ValueError):
                pass

    return {
        "reply": reply or "(no response)",
        "tools_called": tools_called,
        "session_id": session_id,
    }


def chat_stream(message: str, conversation_id: str = "default",
                system_prompt: str = "", model: str = "mimo-v2.5"):
    """Stream Pi agent events as they happen. Yields dicts."""
    key = _get_key()
    if not key:
        yield {"type": "error", "message": "No API key in vault."}
        return

    session_id = _get_session_id(conversation_id)
    os.makedirs(SESSION_DIR, exist_ok=True)

    cmd = [
        "node", PI_BIN,
        "--provider", "opencode-go",
        "--model", model,
        "--mode", "json",
        "--session", os.path.join(SESSION_DIR, f"{session_id}.jsonl"),
    ]
    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt[:2000]])
    cmd.extend(["-p", message[:4000]])

    env = os.environ.copy()
    env["OPENCODE_API_KEY"] = key
    env["PI_SESSION_DIR"] = SESSION_DIR

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, cwd=ROOT, env=env
    )

    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        yield event

    proc.wait()
