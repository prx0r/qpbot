"""Run every scanner, emit one findings doc. Recon only, never submits."""
from __future__ import annotations

import json
import os
import time

from . import banner, creds, traversal, sqli

SCANNERS = (banner, creds, traversal, sqli)


def run_all() -> dict:
    ts = int(time.time())
    findings: list[dict] = []
    for mod in SCANNERS:
        try:
            findings.extend(mod.scan())
        except Exception as e:
            findings.append({"ts": ts, "scanner": mod.SCANNER,
                             "target_id": "", "kind": "scanner-error",
                             "detail": f"{type(e).__name__}: {e}",
                             "confidence": 0.0})
    hits = [f for f in findings if f["kind"] in
            ("valid-creds", "readable-path", "injectable")]
    return {"ts": ts, "findings": findings,
            "summary": {"targets_hit": sorted({f["target_id"] for f in hits}),
                        "hits": len(hits), "total": len(findings)}}


def main() -> None:
    doc = run_all()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runs = os.path.join(root, "runs")
    os.makedirs(runs, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    path = os.path.join(runs, f"scanner-{stamp}.json")
    with open(path, "w") as f:
        json.dump(doc, f, indent=1)
    print(json.dumps(doc["summary"], indent=1))
    print("wrote", path)


if __name__ == "__main__":
    main()
