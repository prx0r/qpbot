"""RSI Analyzer — find patterns in investigation logs to optimize future runs.

Reads investigation logs and answers:
- Which signals (ENS, Farcaster, FOMO, GitHub) actually find identities?
- Which tools produce the most findings per call?
- What's the success rate of each workflow?
- What's the LLM's decision path through the investigation?
- Which addresses were hardest/easiest to resolve?

Feeds results back to the memory bank so the LLM learns what works.
"""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def analyze(log_path: str = "") -> dict:
    """Analyze all investigation logs. Returns optimization insights."""
    if not log_path:
        log_path = os.path.join(ROOT, "runs", "investigations.jsonl")

    if not os.path.exists(log_path):
        return {"status": "no_data", "message": "no investigation logs found"}

    # Parse all entries
    runs = {}
    all_steps = []
    all_signals = defaultdict(int)
    all_tools = defaultdict(lambda: {"calls": 0, "signals": 0, "handles": 0})
    signal_success = defaultdict(lambda: {"found": 0, "total": 0})
    prize_stats = {"total": 0, "with_github": 0, "with_ens": 0, "by_chain": defaultdict(int)}

    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue

            run_id = entry.get("run_id", "")
            event = entry.get("event", "")

            if event == "start":
                runs[run_id] = {"steps": 0, "signals": 0, "prize": False,
                                "address": entry.get("address", ""),
                                "start_ts": entry.get("ts", 0)}
            elif event == "step":
                if run_id in runs:
                    runs[run_id]["steps"] += 1
                    runs[run_id]["signals"] += entry.get("signals_found", 0)

                tool = entry.get("tool", "")
                all_tools[tool]["calls"] += 1
                all_tools[tool]["signals"] += entry.get("signals_found", 0)
                all_tools[tool]["handles"] += len(entry.get("handles", []))

                for sig in entry.get("signals", []):
                    # Extract signal type from string like "ENS: vitalik.eth"
                    sig_type = sig.split(":")[0].strip() if ":" in sig else "other"
                    all_signals[sig_type] += 1

                for handle in entry.get("handles", []):
                    if handle:
                        signal_success[handle] = signal_success.get(handle, {"found": 0, "total": 0})
                        signal_success[handle]["total"] += 1

            elif event == "prize":
                if run_id in runs:
                    runs[run_id]["prize"] = True
                prize_stats["total"] += 1
                if entry.get("has_github"):
                    prize_stats["with_github"] += 1
                if entry.get("has_ens"):
                    prize_stats["with_ens"] += 1
                chain = entry.get("chain", "unknown")
                prize_stats["by_chain"][chain] += 1

            elif event == "end":
                if run_id in runs:
                    runs[run_id]["status"] = entry.get("status", "")

    # Compute insights
    total_runs = len(runs)
    runs_with_prize = sum(1 for r in runs.values() if r["prize"])
    avg_steps = sum(r["steps"] for r in runs.values()) / max(total_runs, 1)
    avg_signals = sum(r["signals"] for r in runs.values()) / max(total_runs, 1)

    # Signal effectiveness
    signal_ranking = sorted(all_signals.items(), key=lambda x: x[1], reverse=True)

    # Tool effectiveness (signals per call)
    tool_ranking = []
    for tool, stats in sorted(all_tools.items(), key=lambda x: x[1]["signals"], reverse=True):
        calls = stats["calls"]
        tool_ranking.append({
            "tool": tool,
            "calls": calls,
            "total_signals": stats["signals"],
            "total_handles": stats["handles"],
            "signals_per_call": round(stats["signals"] / max(calls, 1), 1),
        })

    # Generate optimization suggestions
    suggestions = []
    if prize_stats["with_github"] < prize_stats["total"] * 0.5:
        suggestions.append("GitHub resolution rate is low — try more ENS text record checks")
    if all_tools.get("wallet_investigate", {}).get("calls", 0) == 0:
        suggestions.append("wallet_investigate not used — add it to workflows")
    if avg_steps < 2:
        suggestions.append("Average steps per investigation is low — workflows may be too short")
    if not signal_ranking:
        suggestions.append("No signals logged — check investigation pipeline")

    return {
        "total_runs": total_runs,
        "runs_with_prize": runs_with_prize,
        "prize_rate": round(runs_with_prize / max(total_runs, 1), 2),
        "avg_steps_per_run": round(avg_steps, 1),
        "avg_signals_per_run": round(avg_signals, 1),
        "signal_ranking": signal_ranking[:10],
        "tool_ranking": tool_ranking[:10],
        "prize_stats": {
            "total": prize_stats["total"],
            "with_github": prize_stats["with_github"],
            "with_ens": prize_stats["with_ens"],
            "by_chain": dict(prize_stats["by_chain"]),
        },
        "suggestions": suggestions,
    }


def format_insights(insights: dict) -> str:
    """Format analysis results as a readable summary for the memory bank."""
    if insights.get("status") == "no_data":
        return "No investigation data yet."

    lines = [
        f"## RSI Analysis ({insights['total_runs']} runs)",
        "",
        f"Prize rate: {insights['prize_rate']*100:.0f}% "
        f"({insights['runs_with_prize']}/{insights['total_runs']})",
        f"Avg steps: {insights['avg_steps_per_run']}",
        f"Avg signals: {insights['avg_signals_per_run']}",
        "",
    ]

    if insights["signal_ranking"]:
        lines.append("Top signals:")
        for sig, count in insights["signal_ranking"][:5]:
            lines.append(f"  {sig}: {count}")
        lines.append("")

    if insights["tool_ranking"]:
        lines.append("Tool effectiveness (signals/call):")
        for t in insights["tool_ranking"][:5]:
            lines.append(f"  {t['tool']}: {t['signals_per_call']} signals/call "
                        f"({t['calls']} calls)")
        lines.append("")

    ps = insights["prize_stats"]
    if ps["total"] > 0:
        lines.append(f"Prizes: {ps['total']} total, "
                    f"{ps['with_github']} with GitHub, "
                    f"{ps['with_ens']} with ENS")
        lines.append(f"By chain: {json.dumps(ps['by_chain'])}")
        lines.append("")

    if insights["suggestions"]:
        lines.append("Optimization suggestions:")
        for s in insights["suggestions"]:
            lines.append(f"  - {s}")

    return "\n".join(lines)


def main():
    """Run analysis and output results."""
    log_path = sys.argv[1] if len(sys.argv) > 1 else ""
    insights = analyze(log_path)
    print(json.dumps(insights, indent=2))
    print()
    print(format_insights(insights))


if __name__ == "__main__":
    import sys
    main()
