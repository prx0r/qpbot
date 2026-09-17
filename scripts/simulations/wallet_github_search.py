#!/usr/bin/env python3
"""Wallet GitHub Search — find repos containing a wallet address or key.

Searches GitHub Code Search for a specific wallet address, private key,
or related terms. Useful for cross-referencing on-chain wallets with
leaked code. Needs GH_TOKEN for higher rate limits.
"""
import json
import os
import re
import sys
import time
import urllib.request
from urllib.parse import quote
from urllib.error import HTTPError

TOKEN = os.environ.get("GH_TOKEN", "")
HEADERS = {
    "Authorization": f"token {TOKEN}" if TOKEN else "",
    "Accept": "application/vnd.github.v3.text-match+json",
    "User-Agent": "pq-wallet-search/1.0",
}


def github_search(query, per_page=10):
    """Search GitHub code. Returns list of matches."""
    q = quote(query)
    url = f"https://api.github.com/search/code?q={q}&per_page={per_page}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            return data.get("items", []), data.get("total_count", 0)
    except HTTPError as e:
        if e.code == 403:
            return [], -1  # rate limited
        return [], 0
    except Exception:
        return [], 0


def fetch_raw(repo, path):
    """Fetch raw file content from GitHub."""
    url = f"https://raw.githubusercontent.com/{repo}/HEAD/{path}"
    req = urllib.request.Request(url, headers={
        **HEADERS,
        "Accept": "application/vnd.github.v3.raw",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def extract_matching_lines(content, query_terms):
    """Find lines in content that match any of the query terms."""
    matches = []
    for i, line in enumerate(content.splitlines(), 1):
        for term in query_terms:
            if term.lower() in line.lower():
                matches.append({"line": i, "text": line.strip()[:200], "match": term})
                break
    return matches[:10]


def search_for_address(address):
    """Search GitHub for repos containing a specific wallet address."""
    results = []

    # Search strategies
    searches = [
        (f'"{address}"', f"exact address match"),
        (f'"{address}" filename:.env', f"address in .env file"),
        (f'"{address}" filename:config', f"address in config file"),
        (f'"{address}" filename:key', f"address in key file"),
    ]

    for query, label in searches:
        items, total = github_search(query, per_page=5)
        if total == -1:
            break  # rate limited
        for item in items:
            repo = item.get("repository", {}).get("full_name", "?")
            path = item.get("path", "?")
            results.append({
                "repo": repo,
                "path": path,
                "url": item.get("html_url", ""),
                "search": label,
            })
        time.sleep(2)

    return results


def search_for_key_type(key_type="private_key"):
    """Search GitHub for common key patterns."""
    patterns = {
        "private_key": '"PRIVATE_KEY" filename:.env',
        "mnemonic": '"MNEMONIC" filename:.env',
        "aws_key": '"AWS_SECRET_ACCESS_KEY"',
        "openai_key": '"OPENAI_API_KEY"',
        "gh_token": '"ghp_" filename:.env',
    }
    query = patterns.get(key_type, f'"{key_type}"')
    items, total = github_search(query, per_page=5)
    results = []
    for item in items:
        repo = item.get("repository", {}).get("full_name", "?")
        results.append({
            "repo": repo,
            "path": item.get("path", "?"),
            "url": item.get("html_url", ""),
        })
    return results


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 wallet_github_search.py address <wallet_addr>")
        print("       python3 wallet_github_search.py keys <key_type>")
        sys.exit(1)

    action = sys.argv[1]

    if action == "address":
        if len(sys.argv) < 3:
            print("Usage: python3 wallet_github_search.py address <wallet_addr>")
            sys.exit(1)
        address = sys.argv[2]
        results = search_for_address(address)
        print(json.dumps({
            "ok": True,
            "query": address,
            "results_count": len(results),
            "results": results,
        }, indent=2))

    elif action == "keys":
        key_type = sys.argv[2] if len(sys.argv) > 2 else "private_key"
        results = search_for_key_type(key_type)
        print(json.dumps({
            "ok": True,
            "key_type": key_type,
            "results_count": len(results),
            "results": results,
        }, indent=2))

    else:
        print(f"Unknown action: {action}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
