#!/usr/bin/env python3
"""Git History Secret Scanner — find secrets in git history.

Scans git log, diffs, and blobs for private keys, mnemonics, and
credentials. For CTF: find secrets in repo history.
Adapted from stallshark BLUE-TEAM-COMBINED.md + qpbot patterns.
"""
import json
import os
import re
import subprocess
import sys

PATTERNS = {
    "private_key": re.compile(r"(?:0x)?[0-9a-fA-F]{64}"),
    "mnemonic": re.compile(r"(?:mnemonic|seed.?phrase)[\s:=]+[\"']?([a-z]+(\s+[a-z]+){11,23})", re.I),
    "env_key": re.compile(r"(?:PRIVATE_KEY|SECRET_KEY|API_KEY|MNEMONIC)[\s:=]+[\"']?([^\s\"']{20,})", re.I),
    "aws_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "openai_key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "password": re.compile(r"(?:password|passwd)[\s:=]+[\"']?([^\s\"']{8,})", re.I),
}


def git(*args, cwd=None):
    try:
        p = subprocess.run(["git"] + list(args), capture_output=True, text=True,
                           timeout=30, cwd=cwd)
        return p.stdout
    except Exception:
        return ""


def scan_commits(repo_path):
    findings = []
    log = git("log", "--all", "--oneline", "--diff-filter=D", "--name-only", cwd=repo_path)
    # Also scan all diffs
    diff_output = git("log", "--all", "-p", "--diff-filter=A", cwd=repo_path)

    for name, pat in PATTERNS.items():
        for m in pat.finditer(diff_output):
            val = m.group(1) if m.lastindex else m.group(0)
            if len(val) > 10:
                findings.append({
                    "type": name,
                    "redacted": val[:8] + "..." + val[-4:] if len(val) > 16 else val,
                    "source": "git_history",
                })

    # Check deleted files
    deleted = git("log", "--all", "--diff-filter=D", "--name-only", "--pretty=format:", cwd=repo_path)
    for fn in deleted.strip().split("\n"):
        fn = fn.strip()
        if fn and (".env" in fn or "key" in fn.lower() or "secret" in fn.lower()):
            # Try to recover from history
            content = git("log", "--all", "-1", "--format=%H", "--", fn, cwd=repo_path)
            if content.strip():
                blob = git("show", f"{content.strip()}:{fn}", cwd=repo_path)
                for name, pat in PATTERNS.items():
                    for m in pat.finditer(blob):
                        val = m.group(1) if m.lastindex else m.group(0)
                        if len(val) > 10:
                            findings.append({
                                "type": name,
                                "redacted": val[:8] + "..." + val[-4:] if len(val) > 16 else val,
                                "source": f"deleted_file:{fn}",
                            })

    return findings


def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else "."
    findings = scan_commits(repo)
    by_type = {}
    for f in findings:
        by_type.setdefault(f["type"], []).append(f)
    print(json.dumps({
        "repo": repo,
        "total": len(findings),
        "by_type": {k: len(v) for k, v in by_type.items()},
        "findings": findings[:50],
    }, indent=2))


if __name__ == "__main__":
    main()
