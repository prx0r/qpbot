#!/usr/bin/env python3
"""Extract Secrets from .env files.

Scans a directory tree for .env files and extracts private keys,
mnemonics, API keys, and passwords. For CTF flag discovery.
Adapted from stallshark BLUE-TEAM-COMBINED.md.
"""
import json
import os
import re
import sys

PATTERNS = {
    "private_key": re.compile(
        r"(?:PRIVATE_KEY|SECRET_KEY|SIGNING_KEY|PRIVATE)[\s:=]+[\"']?([^\s\"']{20,})",
        re.I,
    ),
    "mnemonic": re.compile(
        r"(?:MNEMONIC|SEED_PHRASE|SEED)[\s:=]+[\"']?([a-z]+(\s+[a-z]+){11,23})",
        re.I,
    ),
    "api_key": re.compile(
        r"(?:API_KEY|APISECRET|API_SECRET)[\s:=]+[\"']?([^\s\"']{20,})",
        re.I,
    ),
    "password": re.compile(
        r"(?:PASSWORD|PASSWD|DB_PASS|DATABASE_PASSWORD)[\s:=]+[\"']?([^\s\"']{8,})",
        re.I,
    ),
    "aws_key": re.compile(r"(AKIA[0-9A-Z]{16})"),
    "openai_key": re.compile(r"(sk-[A-Za-z0-9]{20,})"),
    "eth_address": re.compile(r"(0x[0-9a-fA-F]{40})"),
    "sol_address": re.compile(r"([1-9A-HJ-NP-Za-km-z]{32,44})"),
    "connection_string": re.compile(
        r"(?:postgres|mysql|mongodb|redis)://[^\s]+",
        re.I,
    ),
}


def scan_file(path):
    findings = []
    try:
        with open(path) as f:
            content = f.read()
    except Exception:
        return findings

    for name, pat in PATTERNS.items():
        for m in pat.finditer(content):
            val = m.group(1) if m.lastindex else m.group(0)
            findings.append({
                "file": path,
                "type": name,
                "redacted": val[:8] + "..." + val[-4:] if len(val) > 16 else val,
                "length": len(val),
            })
    return findings


def scan_tree(root):
    all_findings = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.startswith(".env") or fn.endswith(".env") or "config" in fn.lower():
                path = os.path.join(dirpath, fn)
                findings = scan_file(path)
                all_findings.extend(findings)
    return all_findings


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    findings = scan_tree(root)

    # Group by type
    by_type = {}
    for f in findings:
        by_type.setdefault(f["type"], []).append(f)

    print(json.dumps({
        "total": len(findings),
        "by_type": {k: len(v) for k, v in by_type.items()},
        "findings": findings[:50],
    }, indent=2))


if __name__ == "__main__":
    main()
