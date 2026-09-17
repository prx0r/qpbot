"""Credential scanner — spray default logins from the wordlist."""
from .common import cli, finding, targets, wordlist

SCANNER = "creds"


def scan() -> list[dict]:
    out = []
    pairs = [ln.split(":", 1) for ln in wordlist("creds.txt")]
    pairs = [(u, p) for u, p in pairs if u and p is not None]
    for tid in targets():
        for user, pw in pairs:
            r = cli("try-creds", tid, user, pw)
            if r.get("captured"):
                out.append(finding(SCANNER, tid, "valid-creds",
                                   f"{user}:{pw} -> flag present"))
                break
        else:
            out.append(finding(SCANNER, tid, "no-default-creds",
                               f"{len(pairs)} pairs tried", confidence=0.5))
    return out
