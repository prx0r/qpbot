"""Dashboard — chat left, H-task rail right. Muse-native. Stdlib only.

Token gate: every request needs ?token=<DASH_TOKEN> (env or generated at
boot, printed once to stdout). Binds loopback; the outside world arrives
only through the Cloudflare tunnel.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sys
import threading
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agentcom.audit import log_api_call, log_file_read, log_file_write, log_llm_call

TOKEN = os.environ.get("DASH_TOKEN", secrets.token_urlsafe(24))
RUNS = os.path.join(ROOT, "runs")
HFILE = os.path.join(RUNS, "htasks.json")
PFILE = os.path.join(RUNS, "provider.json")
SYSFILE = os.path.join(RUNS, "system_prompt.txt")
HISTORY: list[dict] = []

DEFAULT_SYSTEM = """You are an autonomous security researcher running in a CTF simulation.

You operate in a simulated arena with 3 targets:
- weak-creds-01: login portal, try default creds
- traversal-01: file server, try path traversal to flag
- sqli-sim-01: user lookup API, try SQL injection

Your mission: capture all 3 flags through server-side verified submission.
Every claim settles through the arena verifier — only CAPTURED verdicts count.

## Your role

You are the MAIN agent. You talk to the human and coordinate work.
You do NOT do long-running tasks yourself. Instead you SPAWN sub-agents.

## Sub-agents (your workers)

When the human asks for work, spawn the right sub-agent:
- TOOL: subagent_run {"message":"<what to do>"} — auto-detects and spawns the right worker

Available sub-agents:
- wallet_hunter — finds funded wallets, checks balances, investigates identity
- repo_auditor — clones repos, scans for secrets, audits security
- chain_scanner — scans whale feed, checks top wallets, finds opportunities
- ctf_runner — runs the CTF arena autonomously, captures flags
- maintenance — checks vault health, usage stats, system status

Sub-agents run in background (nohup). You stay responsive to the human.
When they finish, results appear in runs/subagents/. You can read and discuss.

## Arena tools (for quick tasks)

- probe <target_id> — recon one target
- try-creds <target_id> <user> <pw> — test credentials
- read-file <target_id> <path> — read a file
- sqli <target_id> <payload> — SQL injection
- submit <target_id> <flag> — submit a flag

## On-chain tools (for quick checks)

- whale_feed [min_usd] — large transactions
- eth_check <address> — ETH + ERC-20 balance
- sol_check <address> — SOL + SPL balance
- wallet_investigate <address> — full OSINT chain
- classify <secret> — detect key type

## Rules

- Be concise. Talk to the human normally.
- Spawn sub-agents for long work. Stay available.
- Every tool call runs in background and results are logged.
- Use TOOL: <name> <args> format for tool calls.
- Never guess flags. Only submit verified captures.
- You have vault-held API keys — resolve through vault only.
- Spend is real. Spawn wisely. No wasted runs."""


def _load_sys() -> str:
    if os.path.exists(SYSFILE):
        try:
            return open(SYSFILE).read().strip()
        except Exception:
            pass
    return DEFAULT_SYSTEM


def _save_sys(text: str):
    os.makedirs(os.path.dirname(SYSFILE) or ".", exist_ok=True)
    with open(SYSFILE, "w") as f:
        f.write(text)


def _load_tasks() -> list[dict]:
    if os.path.exists(HFILE):
        return json.load(open(HFILE))
    seed = [
        {"task_id": "demo-digit-1", "kind": "digit",
         "question": "Demo pack finished 3/3. Which lane should lead next?",
         "prediction": "7", "confidence": 0.72, "state": "displayed",
         "context_hash": "seed", "campaign": "demo", "lane": "creds-first",
         "deadline": 4102444800, "answer": None},
        {"task_id": "demo-approval-1", "kind": "confirm",
         "question": "Approve running the live Pi red-team lane? (no spend yet)",
         "prediction": "", "confidence": 0.0, "state": "emitted",
         "context_hash": "seed", "campaign": "demo", "lane": "pi",
         "deadline": 4102444800, "answer": None},
    ]
    os.makedirs(RUNS, exist_ok=True)
    json.dump(seed, open(HFILE, "w"), indent=1)
    return seed


def _save_tasks(tasks: list[dict]):
    os.makedirs(RUNS, exist_ok=True)
    json.dump(tasks, open(HFILE, "w"), indent=1)


def _provider() -> dict:
    if os.path.exists(PFILE):
        return json.load(open(PFILE))
    return {"base_url": "https://opencode.ai/zen/go/v1", "model": "mimo-v2.5"}


def _resp_text(resp: dict) -> str:
    """Extract text from Muse responses API or OpenAI chat completions."""
    parts = []
    for item in resp.get("output", []):
        for c in item.get("content", []):
            if c.get("type") == "output_text" and c.get("text"):
                parts.append(c["text"])
    if parts:
        return "".join(parts)
    return resp.get("output_text", "")


def _chat_via_provider(message: str) -> dict:
    """Route chat through Pi agent harness. Returns dict with reply + tools."""
    from agentcom.pi_agent import chat
    sys_prompt = _load_sys()
    result = chat(message, system_prompt=sys_prompt)
    text = result.get("reply", "(no response)")
    tools = result.get("tools_called", [])
    HISTORY.append({"role": "user", "content": message})
    HISTORY.append({"role": "assistant", "content": text})
    _dispatch_tools(text)
    return {"reply": text, "tools_called": tools}


def _dispatch_tools(text: str):
    """Parse TOOL: calls from LLM output, run workers in background."""
    from agentcom.missions import MissionControl
    from scanners.registry import fire as registry_fire, tool_names
    import subprocess
    # Match both "TOOL: name args" and XML-style "<tool_call>...<name>...</name><args>...</args>..."
    matches = re.findall(r"TOOL:\s*([\w-]+)\s+(.*)", text)
    if not matches:
        xml_calls = re.findall(
            r"<name>([\w-]+)</name>\s*<args>(.*?)</args>", text, re.DOTALL)
        matches = [(n, a.strip()) for n, a in xml_calls]
    if not matches:
        return
    mc = MissionControl()
    arena_tools = {"probe", "try-creds", "try_creds", "read-file", "read_file",
                   "submit", "submit_flag", "sqli"}
    worker_tools = {"whale_feed", "eth_check", "sol_check", "wallet_investigate",
                    "wallet_identity", "wallet_github", "fomo_leaderboard",
                    "clone_scan", "env_scan", "git_history", "classify",
                    "drain_classify", "batch_check", "mnemonic_derive",
                    "gh_search"}
    spawn_tools = {"subagent_run", "spawn_subagent"}
    for tool, args_str in matches[:3]:
        # Try to parse JSON args
        try:
            parsed = json.loads(args_str)
            args = list(parsed.values()) if isinstance(parsed, dict) else [str(parsed)]
        except (json.JSONDecodeError, ValueError):
            args = args_str.strip().split()
        objective = f"{tool} {' '.join(args)}"
        m = mc.dispatch(objective, tools=[tool])

        def _run(mid=m.id, tn=tool, ta=args):
            mc.start(mid)
            try:
                if tn in arena_tools:
                    alias = {"try_creds": "try-creds", "read_file": "read-file",
                             "submit_flag": "submit"}.get(tn, tn)
                    cmd = [sys.executable, "-m", "core.cli", alias] + ta
                    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
                    result = {"ok": p.returncode == 0,
                              "data": {"stdout": p.stdout.strip()[:2000],
                                       "stderr": p.stderr.strip()[:500]},
                              "tool": tn}
                    mc.complete(mid, result, findings=[{"tool": tn, "args": ta, "data": result}])
                elif tn in worker_tools:
                    from agentcom.worker import run_worker
                    r = run_worker(objective, tools=[tn], max_turns=5, force=True)
                    mc.complete(mid, r, findings=r.get("findings", []),
                                tokens_in=r.get("tokens_in", 0),
                                tokens_out=r.get("tokens_out", 0))
                elif tn in spawn_tools:
                    from agentcom.subagent import spawn, SUBAGENTS
                    # Parse the JSON args to get the message
                    try:
                        parsed = json.loads(args_str)
                        msg = parsed.get("message", objective)
                    except (json.JSONDecodeError, ValueError):
                        msg = objective
                    msg_lower = msg.lower()
                    # Auto-detect sub-agent
                    if "whale" in msg_lower or "wallet" in msg_lower or "chain" in msg_lower:
                        sa = "wallet_hunter" if "investigate" in msg_lower else "chain_scanner"
                    elif "repo" in msg_lower or "clone" in msg_lower or "audit" in msg_lower:
                        sa = "repo_auditor"
                    elif "ctf" in msg_lower or "capture" in msg_lower or "flag" in msg_lower or "attack" in msg_lower:
                        sa = "ctf_runner"
                    elif "maintain" in msg_lower or "health" in msg_lower or "status" in msg_lower:
                        sa = "maintenance"
                    else:
                        sa = "wallet_hunter"
                    result = spawn(sa, extra_context=msg)
                    mc.complete(mid, result, findings=[{"subagent": sa, "pid": result.get("pid")}])
                elif tn in tool_names():
                    result = registry_fire(tn, ta)
                    mc.complete(mid, result, findings=[{"tool": tn, "args": ta, "data": result}])
                else:
                    mc.fail(mid, f"unknown tool: {tn}")
            except Exception as e:
                mc.fail(mid, str(e))

        threading.Thread(target=_run, daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    server_version = "qpbot-dash/0.2"

    def _gate(self) -> bool:
        q = parse_qs(urlparse(self.path).query)
        if q.get("token", [""])[0] != TOKEN:
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"bad token")
            return False
        return True

    def _json(self, obj, code: int = 200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length", 0))
        except ValueError:
            n = 0
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n))
        except (ValueError, json.JSONDecodeError):
            return {}

    def do_GET(self):
        if not self._gate():
            return
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            page = open(os.path.join(ROOT, "dashboard", "static",
                                     "index.html"), "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
        elif path == "/api/tasks":
            self._json(_load_tasks())
        elif path == "/api/status":
            from core import module_adapter
            self._json({"status": module_adapter.status("demo"),
                        "provider": _provider()})
        elif path == "/api/system-prompt":
            self._json({"prompt": _load_sys()})
        elif path == "/api/missions":
            from agentcom.missions import MissionControl
            mc = MissionControl()
            self._json({"missions": mc.list_missions(), "summary": mc.summary()})
        elif path == "/api/prizes":
            from agentcom.prizes import PrizeStore
            ps = PrizeStore()
            self._json({"prizes": ps.list_prizes(), "summary": ps.summary()})
        elif path == "/api/seen":
            from agentcom.seen import SeenTracker
            st = SeenTracker()
            self._json({"stats": st.stats()})
        elif path == "/api/rsi":
            from agentcom.rsi import analyze, format_insights
            i = analyze()
            self._json({"text": format_insights(i)})
        elif path == "/api/history":
            self._json(HISTORY[-30:])
        elif path == "/api/audit":
            from agentcom.audit import recent
            self._json({"events": recent(int(parse_qs(urlparse(self.path).query).get("n", ["20"])[0]))})
        elif path == "/api/subagent/statuses":
            from agentcom.monitor import list_statuses, summary
            self._json({"statuses": list_statuses(), "summary": summary()})
        elif path == "/api/workflows":
            from agentcom.workflows import WORKFLOWS
            self._json({"workflows": {name: {"goal": wf["goal"],
                                              "steps": [s.tool for s in wf["steps"]]}
                                       for name, wf in WORKFLOWS.items()}})
        elif path == "/api/memory":
            from agentcom.memory import MemoryBank
            import pqconfig as cfg
            bank = MemoryBank(cfg.memory_dir())
            self._json({"inventory": bank.inventory(), "preamble": bank.preamble()})
        elif path == "/api/subagents":
            from agentcom.subagent import list_subagents
            self._json(list_subagents())
        elif path == "/api/subagent/runs":
            from agentcom.subagent import list_runs
            self._json({"runs": list_runs()})
        elif path == "/api/subagent/log":
            run_id = parse_qs(urlparse(self.path).query).get("run_id", [""])[0]
            if not run_id:
                self._json({"error": "missing run_id"}, 400)
                return
            from agentcom.subagent import get_log
            log_content = get_log(run_id)
            self._json({"log": log_content, "lines": log_content.count("\n")})
        elif path == "/api/subagent/status":
            run_id = parse_qs(urlparse(self.path).query).get("run_id", [""])[0]
            if not run_id:
                self._json({"error": "missing run_id"}, 400)
                return
            from agentcom.subagent import get_status
            status = get_status(run_id)
            if status:
                self._json(status)
            else:
                self._json({"error": "not found"}, 404)
        elif path == "/api/files":
            files = []
            for d in ["core", "agentcom", "dashboard", "scanners", "scripts"]:
                dp = os.path.join(ROOT, d)
                if os.path.isdir(dp):
                    for f in sorted(os.listdir(dp)):
                        if f.endswith((".py", ".md", ".json", ".sh")):
                            files.append(f"{d}/{f}")
            self._json(files)
        elif path == "/api/vault":
            from agentcom.vault.store import Vault
            v = Vault(os.path.expanduser("~/.qpbot/vault.json"))
            self._json({"keys": v.find(active_only=False)})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if not self._gate():
            return
        path = urlparse(self.path).path
        body = self._body()
        if path == "/api/chat":
            msg_preview = str(body.get("message", ""))[:100]
            log_api_call("/api/chat", actor="user")
            result = _chat_via_provider(str(body.get("message", ""))[:4000])
            self._json(result)
        elif path == "/api/system-prompt":
            _save_sys(str(body.get("prompt", ""))[:10000])
            self._json({"ok": True})
        elif path == "/api/answer":
            from agentcom.htasks.queue import HQueue, HTask
            q = HQueue()
            for raw in _load_tasks():
                t = HTask(raw["task_id"], raw["kind"], raw["question"],
                          prediction=raw.get("prediction", ""),
                          confidence=raw.get("confidence", 0.0))
                t.state = raw.get("state", "emitted")
                t.context_hash = raw.get("context_hash", "")
                q.emit(t)
            t = q.tasks.get(body.get("task_id", ""))
            if not t:
                self._json({"ok": False, "error": "unknown task"}, 404)
                return
            try:
                if t.state == "emitted":
                    t.display()
                if t.state == "displayed":
                    t.acknowledge()
                t.answer_task(str(body.get("value", "")),
                              str(body.get("prediction", "")))
                _save_tasks([x.view() | {"answer": x.answer}
                             for x in q.tasks.values()])
                self._json({"ok": True, "state": t.state})
            except ValueError as e:
                self._json({"ok": False, "error": str(e)}, 400)
        elif path == "/api/vault-store":
            from agentcom.vault.store import Vault
            v = Vault(os.path.expanduser("~/.qpbot/vault.json"))
            value = str(body.get("value", ""))
            if not value:
                self._json({"ok": False, "error": "empty"}, 400)
                return
            out = v.store(str(body.get("name", "LLM_KEY")), value,
                          ["dashboard-chat", "pi-redteam"],
                          ["chat-session", "lane-1"],
                          scope=str(body.get("scope", "")),
                          ttl_s=int(body.get("ttl_s", 86400)),
                          max_uses=int(body.get("max_uses", 0)))
            self._json({"ok": True, **out})
        elif path == "/api/provider":
            os.makedirs(RUNS, exist_ok=True)
            json.dump({"base_url": str(body.get("base_url", ""))[:200],
                       "model": str(body.get("model", ""))[:200]},
                      open(PFILE, "w"))
            self._json({"ok": True})
        elif path == "/api/missions/dispatch":
            from agentcom.missions import MissionControl
            mc = MissionControl()
            obj = str(body.get("objective", ""))[:2000]
            if not obj:
                self._json({"ok": False, "error": "no objective"}, 400)
                return
            m = mc.dispatch(obj, tools=body.get("tools", []))

            def _run():
                mc.start(m.id)
                try:
                    import subprocess
                    tool_args = obj.split()
                    cmd = [sys.executable, "-m", "core.cli"] + tool_args
                    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
                    result = {"ok": p.returncode == 0,
                              "stdout": p.stdout.strip()[:2000],
                              "stderr": p.stderr.strip()[:500]}
                    mc.complete(m.id, result, findings=[{"data": result}])
                except Exception as e:
                    mc.fail(m.id, str(e))

            threading.Thread(target=_run, daemon=True).start()
            self._json({"ok": True, "mission_id": m.id})
        elif path == "/api/workflow/run":
            from agentcom.workflows import WORKFLOWS, WorkflowRunner
            from scanners.registry import fire as registry_fire, tool_names
            import subprocess
            wf_name = str(body.get("workflow", ""))
            if wf_name not in WORKFLOWS:
                self._json({"ok": False, "error": f"unknown workflow: {wf_name}. Available: {list(WORKFLOWS.keys())}"}, 400)
                return
            wf = WORKFLOWS[wf_name]
            arena_tools = {"probe", "try-creds", "read-file", "submit", "sqli"}
            def _tool_exec(tool_name, args):
                if tool_name in arena_tools:
                    cmd = [sys.executable, "-m", "core.cli", tool_name] + args
                    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
                    return {"ok": p.returncode == 0, "data": json.loads(p.stdout) if p.stdout.strip() else {}}
                elif tool_name in tool_names():
                    return registry_fire(tool_name, args)
                return {"ok": False, "error": f"unknown tool: {tool_name}"}
            runner = WorkflowRunner(tool_executor=_tool_exec)
            wallet_address = str(body.get("wallet_address", ""))

            def _run_wf():
                result = runner.run(wf_name, initial_context={"wallet_address": wallet_address} if wallet_address else None)
                # Store findings as mission
                from agentcom.missions import MissionControl
                mc = MissionControl()
                m = mc.dispatch(f"workflow:{wf_name}", tools=[s.tool for s in wf["steps"]])
                mc.start(m.id)
                if result.status == "completed":
                    mc.complete(m.id, {"workflow": wf_name, "status": result.status,
                                       "steps": len(result.steps)},
                                findings=[{"tool": s.tool, "data": s.output} for s in result.steps if s.output])
                else:
                    mc.fail(m.id, f"workflow {result.status}: {result.steps[-1].evidence if result.steps else 'no steps'}")

            threading.Thread(target=_run_wf, daemon=True).start()
            self._json({"ok": True, "workflow": wf_name})
        elif path == "/api/subagent/spawn":
            from agentcom.subagent import spawn
            sa_name = str(body.get("subagent", ""))
            result = spawn(
                sa_name,
                extra_context=str(body.get("context", "")),
                wallet_address=str(body.get("wallet_address", "")),
                repo_url=str(body.get("repo_url", "")),
            )
            self._json(result)
        elif path == "/api/subagent/run":
            # Convenience: main agent sends one message, spawns appropriate sub-agent
            from agentcom.subagent import spawn, SUBAGENTS
            msg = str(body.get("message", "")).lower()
            # Auto-detect which sub-agent to spawn
            if "whale" in msg or "wallet" in msg or "chain" in msg:
                sa = "wallet_hunter" if "investigate" in msg or "osint" in msg else "chain_scanner"
            elif "repo" in msg or "clone" in msg or "audit" in msg:
                sa = "repo_auditor"
            elif "ctf" in msg or "capture" in msg or "flag" in msg or "attack" in msg:
                sa = "ctf_runner"
            elif "maintain" in msg or "health" in msg or "status" in msg:
                sa = "maintenance"
            else:
                sa = "wallet_hunter"  # default
            result = spawn(sa, extra_context=str(body.get("message", "")))
            self._json({"spawned": sa, **result})
        elif path == "/api/file/read":
            fpath = str(body.get("path", ""))
            full = os.path.join(ROOT, fpath)
            if not os.path.exists(full) or not full.startswith(ROOT):
                self._json({"error": "not found"}, 404)
            else:
                log_file_read(fpath)
                try:
                    content = open(full).read()
                    self._json({"path": fpath, "content": content})
                except Exception as e:
                    self._json({"error": str(e)}, 500)
        elif path == "/api/file/write":
            fpath = str(body.get("path", ""))
            content = str(body.get("content", ""))
            full = os.path.join(ROOT, fpath)
            if not full.startswith(ROOT):
                self._json({"error": "invalid path"}, 400)
            else:
                log_file_write(fpath)
                try:
                    os.makedirs(os.path.dirname(full), exist_ok=True)
                    with open(full, "w") as f:
                        f.write(content)
                    self._json({"ok": True, "path": fpath})
                except Exception as e:
                    self._json({"error": str(e)}, 500)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("DASH_PORT", "8791"))
    print(f"dashboard token: {TOKEN}", flush=True)
    print(f"http://localhost:{port}/?token={TOKEN}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
