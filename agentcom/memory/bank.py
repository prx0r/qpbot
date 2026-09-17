"""MemoryBank — file-backed experience store with freeze snapshots.

Layout: <bank>/ ( *.md memory files, bank.jsonl append-only change log )
Freeze: <bank>/freezes/<ts>/ ( full copy, read-only reference for evals )
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

MAX_INJECT_CHARS = 4000


class MemoryBank:
    def __init__(self, path: str):
        self.root = Path(path)
        self.root.mkdir(parents=True, exist_ok=True)
        self.log_path = self.root / "bank.jsonl"

    def files(self) -> dict[str, str]:
        out = {}
        for p in sorted(self.root.glob("*.md")):
            try:
                out[p.name] = p.read_text()
            except OSError:
                continue
        return out

    def inventory(self) -> str:
        items = self.files()
        if not items:
            return "(memory bank empty)"
        lines = [f"- {name} ({len(text)} chars)"
                 for name, text in items.items()]
        return "Memory files:\n" + "\n".join(lines)

    def preamble(self, max_chars: int = MAX_INJECT_CHARS) -> str:
        """Prompt block: full bank if small, else inventory + read guidance."""
        items = self.files()
        if not items:
            return ("Past-run experience: none yet. Work the targets, and "
                    "your notes will be saved for next run.")
        blob = "\n\n".join(f"## {name}\n{text}"
                            for name, text in items.items())
        if len(blob) <= max_chars:
            return ("Past-run experience (learned by earlier runs, may be "
                    "wrong — verify before trusting):\n" + blob)
        return ("Past-run experience inventory (full text withheld for "
                "space; strongest lessons first):\n" + self.inventory())

    def write(self, name: str, content: str) -> None:
        if "/" in name or name.startswith("."):
            raise ValueError(f"bad memory name: {name}")
        if not name.endswith(".md"):
            name += ".md"
        tmp = self.root / (name + ".tmp")
        tmp.write_text(content)
        os.replace(tmp, self.root / name)
        self._log("write", name=name, chars=len(content))

    def remove(self, name: str) -> None:
        p = self.root / name
        if p.exists() and p.suffix == ".md":
            p.unlink()
            self._log("remove", name=name)

    def freeze(self, dest_root: str = "") -> str:
        """Copy the bank (md files only) to a timestamped read-only snapshot."""
        ts = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        dest = Path(dest_root or (self.root / "freezes")) / ts
        dest.mkdir(parents=True, exist_ok=True)
        for p in self.root.glob("*.md"):
            shutil.copy2(p, dest / p.name)
        manifest = {"ts": ts, "files": sorted(p.name for p in dest.glob("*.md"))}
        (dest / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))
        self._log("freeze", dest=str(dest))
        return str(dest)

    def _log(self, event: str, **fields) -> None:
        with open(self.log_path, "a") as f:
            f.write(json.dumps({"ts": int(time.time()), "event": event,
                                **fields}) + "\n")
