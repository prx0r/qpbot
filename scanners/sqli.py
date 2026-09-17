"""SQLi scanner — try payload wordlist, detect admin-row evidence."""
from .common import cli, finding, targets, wordlist

SCANNER = "sqli"


def scan() -> list[dict]:
    out = []
    payloads = wordlist("payloads.txt")
    for tid in targets():
        for payload in payloads:
            r = cli("sqli", tid, payload)
            if r.get("captured") or "admin" in str(r.get("evidence", "")):
                out.append(finding(SCANNER, tid, "injectable",
                                   f"{payload!r} -> admin row"))
                break
        else:
            out.append(finding(SCANNER, tid, "no-injection",
                               f"{len(payloads)} payloads tried",
                               confidence=0.5))
    return out
