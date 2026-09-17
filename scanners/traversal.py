"""Traversal scanner — try candidate paths from the wordlist."""
import re
from .common import cli, finding, targets, wordlist

SCANNER = "traversal"
FLAG_RE = re.compile(r"XMCTF\{[^}]+\}")


def scan() -> list[dict]:
    out = []
    paths = wordlist("paths.txt")
    for tid in targets():
        for path in paths:
            r = cli("read-file", tid, path)
            text = str(r)
            if r.get("captured") or FLAG_RE.search(text):
                out.append(finding(SCANNER, tid, "readable-path",
                                   f"{path} -> flag present"))
                break
        else:
            out.append(finding(SCANNER, tid, "no-traversal",
                               f"{len(paths)} paths tried", confidence=0.5))
    return out
