#!/usr/bin/env python3
"""GitHub Secret Scanner — find leaked keys in public repos.

Adapted from stallshark BLUE-TEAM-COMBINED.md for CTF context.
Searches GitHub code for exposed private keys, mnemonics, and API tokens.
Requires GH_TOKEN env var.
"""
import json
import os
import re
import sys
import time
from urllib.request import Request, urlopen
from urllib.parse import quote
from urllib.error import HTTPError

TOKEN = os.environ.get("GH_TOKEN", "")
HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3.text-match+json",
    "User-Agent": "pq-ctf-scanner/1.0",
}

# Search patterns — ranked by severity for CTF relevance
QUERIES = [
    ("PRIVATE_KEY 0x filename:.env", "EVM private key in .env"),
    ("MNEMONIC filename:.env", "Seed phrase in .env"),
    ("SECRET_KEY filename:.env", "Secret key in .env"),
    ("id.json solana keypair", "Solana keypair JSON file"),
    ("ethers.Wallet.fromSecretKey", "EVM private key usage"),
    ("Keypair.fromSecretKey solana", "Solana keypair usage"),
    ("AWS_SECRET_ACCESS_KEY", "AWS secret key"),
    ("OPENAI_API_KEY", "OpenAI API key"),
    ("DATABASE_URL postgres", "Database URL with credentials"),
    ("password= filename:.env", "Password in .env"),
]

# Extraction patterns
PATTERNS = {
    "eth_hex": re.compile(r"(?:0x)?[0-9a-fA-F]{64}"),
    "mnemonic": re.compile(
        r"(?:mnemonic|seed.?phrase)[\s:=]+[\"']?([a-z]+(\s+[a-z]+){11,23})",
        re.I,
    ),
    "env_val": re.compile(
        r"(?:PRIVATE_KEY|SECRET_KEY|API_KEY|MNEMONIC|PASSWORD)[\s:=]+[\"']?([^\s\"']{20,})",
        re.I,
    ),
    "base64_key": re.compile(
        r"(?:PRIVATE_KEY|SIGNING_KEY|SECRET_KEY)[\s:=]+[\"']?([A-Za-z0-9+/]{40,88}={0,2})"
    ),
    "aws_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "openai_key": re.compile(r"sk-[A-Za-z0-9]{20,}"),
}


def search_github(query, page=1, per_page=5):
    q = quote(query)
    url = f"https://api.github.com/search/code?q={q}&per_page={per_page}&page={page}"
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data.get("items", []), data.get("total_count", 0)
    except HTTPError as e:
        if e.code == 403:
            print("  [RATE LIMITED] waiting 60s...", file=sys.stderr)
            time.sleep(60)
            return search_github(query, page, per_page)
        return [], 0
    except Exception:
        return [], 0


def fetch_raw(repo, path):
    url = f"https://raw.githubusercontent.com/{repo}/HEAD/{path}"
    req = Request(url, headers={**HEADERS, "Accept": "application/vnd.github.v3.raw"})
    try:
        with urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def extract_secrets(content):
    found = []
    for name, pat in PATTERNS.items():
        for m in pat.finditer(content):
            val = m.group(1) if m.lastindex else m.group(0)
            if val not in found and len(val) > 8:
                found.append(val[:12] + "..." + val[-4:] if len(val) > 20 else val)
    return found[:10]


def main():
    if not TOKEN:
        print("ERROR: Set GH_TOKEN env var", file=sys.stderr)
        sys.exit(1)

    results = []
    repos_hit = set()

    for query, label in QUERIES:
        print(f"Searching: {label}", file=sys.stderr)
        items, total = search_github(query)
        print(f"  Found: {total} results", file=sys.stderr)

        for item in items[:3]:
            repo = item.get("repository", {}).get("full_name", "?")
            path = item.get("path", "?")
            repos_hit.add(repo)
            raw_url = f"https://raw.githubusercontent.com/{repo}/HEAD/{path}"
            content = fetch_raw(repo, path)
            secrets = extract_secrets(content) if content else []

            results.append({
                "query": label,
                "repo": repo,
                "path": path,
                "url": item.get("html_url", "?"),
                "secrets_found": len(secrets),
                "redacted": secrets[:3],
            })
        time.sleep(10)

    print(json.dumps(results, indent=2))
    print(
        f"\n{len(results)} files across {len(repos_hit)} repos",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
