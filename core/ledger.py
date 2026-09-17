"""Ledger — append-only hash-chained event store (stdlib only).

Shape mirrors qp Store: canonical JSON + sha256, verify_chain, replay.
"""
from __future__ import annotations

import hashlib
import json
import os
import time


def canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def obj_hash(obj: dict) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


class Ledger:
    def __init__(self, path: str):
        self.path = path
        self.cursor = 0
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.cursor += 1

    def append(self, etype: str, payload: dict) -> dict:
        prev = self._last_hash()
        event = {
            "seq": self.cursor + 1,
            "ts": int(time.time()),
            "type": etype,
            "payload": payload,
            "prev": prev,
        }
        event["hash"] = obj_hash({k: v for k, v in event.items() if k != "hash"})
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(event, sort_keys=True) + "\n")
        self.cursor += 1
        return event

    def _last_hash(self) -> str:
        if self.cursor == 0 or not os.path.exists(self.path):
            return "genesis"
        last = None
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    last = json.loads(line)
        return last["hash"] if last else "genesis"

    def read_all(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def verify_chain(self) -> bool:
        events = self.read_all()
        prev = "genesis"
        for e in events:
            if e.get("prev") != prev:
                return False
            h = e.get("hash")
            recomputed = obj_hash({k: v for k, v in e.items() if k != "hash"})
            if h != recomputed:
                return False
            prev = h
        return True


def settle_capture(target_id: str, agent_id: str, flag_sha256: str,
                   evidence_hashes: list[str], ledger_cursor: int) -> dict:
    body = {
        "target_id": target_id,
        "agent_id": agent_id,
        "verdict": "CAPTURED",
        "flag_sha256": flag_sha256,
        "evidence_hashes": evidence_hashes,
        "ledger_cursor": ledger_cursor,
    }
    rid = obj_hash(body)
    return {"id": rid, **body}
