"""Worker — runs a harness with RSI feedback loop.

Each worker is an isolated harness run that:
1. Reads the memory bank (RSI insights from previous runs)
2. Logs every investigation step via invlog
3. Executes tools via the registry
4. Writes RSI insights back to the memory bank after completion

This closes the RSI loop: run → log → analyze → learn → next run.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pqconfig as cfg
from agentcom.vault.store import Vault
from agentcom.vault.asynclog import UsageLogger
from agentcom.vault.tracker import cost_minor as calc_cost
from agentcom.memory import MemoryBank
from agentcom.invlog import InvestigationLog
from agentcom.rsi import analyze, format_insights
from agentcom.seen import SeenTracker
from scanners.registry import fire as registry_fire


def run_worker(objective: str, tools: list[str] | None = None,
               max_turns: int = 10, model: str = "",
               use_rsi: bool = True, force: bool = False,
               wallet_address: str = "") -> dict:
    """Execute a mission with RSI feedback.

    The RSI loop:
    1. Read memory bank → inject past-run insights into system prompt
    2. Run LLM loop with tools
    3. Log every step via invlog
    4. After completion → analyze all investigation logs
    5. Write fresh RSI insights to memory bank
    6. Next run reads these insights → optimizes behavior
    """
    model = model or "mimo-v2.5"
    start_ts = time.time()

    # ── Resolve vault key ──
    vault = Vault(cfg.vault_path())
    active = vault.find(kind="llm-inference", tier="paid")
    if not active:
        return {"ok": False, "error": "no LLM keys in vault"}

    key = key_name = pick = None
    for cand in active:
        try:
            key = vault.resolve(cand["name"], "dashboard-chat",
                                "chat-session", cand["capability"])
            key_name, pick = cand["name"], cand
            break
        except ValueError:
            continue
    if key is None:
        return {"ok": False, "error": "no usable LLM keys"}

    # ── Dedup: skip if wallet already investigated recently ──
    seen = SeenTracker()
    if wallet_address and not force:
        if seen.is_seen(wallet_address):
            return {"ok": False, "error": "already_investigated",
                    "skip_reason": f"wallet {wallet_address} seen recently",
                    "last_seen": seen._seen.get(wallet_address.lower(), {}).get("ts", 0)}

    # ── RSI Step 1: Read memory bank for past-run insights ──
    bank = MemoryBank(cfg.memory_dir())
    rsi_context = ""
    if use_rsi:
        rsi_context = bank.preamble()

    # ── Build system prompt with RSI context ──
    available_tools = tools or [
        "whale_feed", "eth_check", "sol_check", "wallet_investigate",
        "wallet_github", "clone_scan", "fomo_leaderboard",
        "classify", "drain_classify",
    ]
    tool_desc = "Available tools:\n"
    for t in available_tools:
        tool_desc += f"  TOOL: {t} <args>\n"

    system = f"""You are an autonomous sub-agent on a mission.
Objective: {objective}

{tool_desc}

Call one tool per message. Format: TOOL: <name> <args>
After each tool call you'll get the result. Work toward your objective.
When you have enough findings, summarize them."""

    if rsi_context and "none yet" not in rsi_context:
        system += f"\n\n{rsi_context}"

    messages = [{"role": "system", "content": system}]
    findings = []
    tools_used = []
    run_ti = run_to = 0

    # ── RSI Step 2: Start investigation log ──
    invlog = InvestigationLog()
    run_id = invlog.log_start(objective, workflow="worker")

    logger = UsageLogger(vault=vault,
                         log_path=os.path.join(cfg.runs_dir(), "usage.jsonl"),
                         buffer_size=100, flush_interval_s=1)

    # ── LLM loop ──
    for turn in range(max_turns):
        # Call LLM
        try:
            headers = {"Content-Type": "application/json",
                       "Authorization": f"Bearer {key}",
                       "x-opencode-session": str(uuid.uuid4()),
                       "User-Agent": "pq-worker/1.0"}

            if model.startswith("muse-spark"):
                body = json.dumps({
                    "model": model,
                    "input": [{"role": m["role"], "content": m["content"]}
                              for m in messages[-20:]],
                    "stream": False,
                    "max_output_tokens": 1024,
                }).encode()
                url = cfg.llm_base_url().rstrip("/") + "/responses"
            else:
                body = json.dumps({
                    "model": model,
                    "messages": messages[-20:],
                    "max_tokens": 512,
                }).encode()
                url = cfg.llm_base_url().rstrip("/") + "/chat/completions"

            req = urllib.request.Request(url, data=body, headers=headers,
                                        method="POST")
            with urllib.request.urlopen(req, timeout=60) as r:
                resp = json.loads(r.read())
        except Exception as e:
            invlog.log_end(run_id, "failed", turn, len(findings), False)
            return {"ok": False, "error": f"API error: {e}",
                    "run_id": run_id, "findings": findings,
                    "tokens_in": run_ti, "tokens_out": run_to}

        # Extract text
        if model.startswith("muse-spark"):
            text = ""
            for item in resp.get("output", []):
                for c in item.get("content", []):
                    if c.get("type") == "output_text" and c.get("text"):
                        text += c["text"]
        else:
            text = resp["choices"][0]["message"]["content"] or ""

        usage = resp.get("usage", {})
        ti = usage.get("input_tokens", usage.get("prompt_tokens", 0))
        to = usage.get("output_tokens", usage.get("completion_tokens", 0))
        run_ti += ti
        run_to += to

        logger.log(key_name, model, tokens_in=ti, tokens_out=to,
                   cost_minor=calc_cost(model, ti, to))

        if not text.strip():
            break

        messages.append({"role": "assistant", "content": text})

        # Parse tool call
        m = re.search(r"TOOL:\s*([\w-]+)\s+(.*)", text)
        if m:
            tool_name = m.group(1)
            tool_args = m.group(2).strip().split()
            tools_used.append(tool_name)

            # Execute via registry
            t0 = time.time()
            result = registry_fire(tool_name, tool_args)
            duration_ms = int((time.time() - t0) * 1000)
            result_str = json.dumps(result)

            # ── RSI Step 3: Log investigation step ──
            invlog.log_step(run_id, tool_name, tool_args,
                           result.get("data", result), duration_ms)

            # Track findings
            if result.get("ok") and result.get("data"):
                findings.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "data": result["data"],
                    "turn": turn + 1,
                })

            messages.append({"role": "user", "content": f"Result:\n{result_str[:2000]}"})
        else:
            if "finding" in text.lower() or "summary" in text.lower() or turn == max_turns - 1:
                findings.append({"tool": "summary", "data": {"text": text[:2000]},
                                 "turn": turn + 1})
                break
            messages.append({"role": "user",
                             "content": "Call a tool. Format: TOOL: <name> <args>"})

    logger.shutdown()
    elapsed = time.time() - start_ts

    # ── RSI Step 4: Log investigation end ──
    total_signals = sum(1 for f in findings if f.get("data"))
    invlog.log_end(run_id, "completed", turn + 1 if 'turn' in dir() else 0,
                   total_signals, bool(findings))

    # ── Dedup: mark address as investigated ──
    if wallet_address:
        has_github = any(f.get("tool") == "wallet_github" or
                        f.get("tool") == "wallet_investigate"
                        for f in findings)
        chain = "ethereum" if wallet_address.startswith("0x") else "unknown"
        seen.mark(wallet_address, workflow=objective[:100], run_id=run_id,
                  signals_found=total_signals, prize_stored=bool(findings),
                  github_found=has_github, chain=chain)

    # ── RSI Step 5: Analyze and write insights to memory bank ──
    if use_rsi:
        try:
            insights = analyze()
            if insights.get("total_runs", 0) > 0:
                insight_text = format_insights(insights)
                bank.write("rsi-investigation-insights.md", insight_text)
                bank.freeze()
        except Exception:
            pass  # non-fatal

    return {
        "ok": True,
        "run_id": run_id,
        "objective": objective,
        "turns": turn + 1 if 'turn' in dir() else 0,
        "findings": findings,
        "tools_used": tools_used,
        "tokens_in": run_ti,
        "tokens_out": run_to,
        "duration_s": round(elapsed, 1),
        "model": model,
    }
