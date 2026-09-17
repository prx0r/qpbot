"""AgentDeck bridge — AgentCom state projection to work-item tiles.

Pure functions: status + queue in, tiles out. Transport (daemon push,
polling) lives outside this module. Tile object is Campaign, ATask, or
HTask — never a bare process.
"""
from __future__ import annotations


def tiles_for_status(status: dict, hqueue=None, spend: dict | None = None,
                     lanes: dict | None = None) -> list[dict]:
    tiles = []
    for prog in status.get("programs", []):
        perf = prog.get("our_performance", {})
        total = max(perf.get("runs", 0), 1)
        state = "verified" if perf.get("score", 0) >= 1.0 else "working"
        tiles.append({"kind": "campaign",
                      "title": prog.get("name", prog.get("program_id", "?")),
                      "state": state,
                      "detail": f"{perf.get('wins', 0)}/{total} flags",
                      "spend": (spend or {}).get("usd_minor", 0)})
    if hqueue is not None:
        for t in hqueue.tasks.values():
            if t.state in ("displayed", "acknowledged"):
                tiles.append({"kind": "htask", "title": t.question[:60],
                              "state": "needs-you",
                              "detail": f"{t.kind} pred={t.prediction}",
                              "task_id": t.task_id})
        pending = hqueue.pending_count()
        if pending:
            tiles.append({"kind": "queue", "title": f"{pending} waiting",
                          "state": "waiting", "detail": ""})
    for name, info in (lanes or {}).items():
        tiles.append({"kind": "lane", "title": name,
                      "state": "working" if info.get("running") else "idle",
                      "detail": str(info.get("note", ""))})
    return tiles


def agentdeck_state(tiles: list[dict]) -> dict:
    """Collapse tiles to working / waiting / idle / approval counts."""
    counts = {"working": 0, "waiting": 0, "idle": 0, "approval": 0}
    for t in tiles:
        s = t.get("state", "")
        if s in ("working",):
            counts["working"] += 1
        elif s in ("waiting",):
            counts["waiting"] += 1
        elif s in ("idle", "verified"):
            counts["idle"] += 1
        elif s in ("needs-you",):
            counts["approval"] += 1
    return counts
