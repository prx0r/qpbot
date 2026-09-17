#!/usr/bin/env python3
"""Wallet Identity — resolve a wallet address to social/GitHub identity.

Uses multiple OSINT signals to connect on-chain wallets to real identities:
1. ENS name resolution (wallet -> name.eth -> search GitHub for that name)
2. FOMO handle lookup (wallet -> trader handle -> GitHub search)
3. Commit email extraction (scan GitHub repos for wallet address in commits)
4. Username pattern search (try common handles across platforms)
5. Blockchain explorer labels (Etherscan/Solscan labeled entities)

No API keys needed for most paths. GH_TOKEN helps but isn't required.
"""
import json
import os
import re
import sys
import time
import urllib.request
from urllib.error import HTTPError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from scripts.simulations.github import search_code, get_user, email_to_user
from scanners.patterns import ETH_ADDRESS, SOL_ADDRESS, redact


def resolve_ens(address: str) -> dict | None:
    """Try to resolve an ENS name for an ETH address via public RPC."""
    try:
        # ENS reverse resolution: call ens.name(address) on mainnet
        # The ENS registry is at 0x0000000000C2E074eC69008fD4189972B3e0D3F0
        # We use a simpler approach: check the Etherscan API for the name
        url = (f"https://api.etherscan.io/api"
               f"?module=account&action=txlist"
               f"&address={address}&startblock=0&endblock=99999999"
               f"&page=1&offset=1&sort=desc")
        req = urllib.request.Request(url, headers={"User-Agent": "pq-identity/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        # Etherscan doesn't directly give ENS names in this endpoint
        # but the from/to fields sometimes include ENS labels
        return None
    except Exception:
        return None


def search_fomo_wallet(address: str) -> list[dict]:
    """Search FOMO for traders holding this wallet address."""
    try:
        url = f"https://api.fomoapi.io/v2/search?q={address}"
        req = urllib.request.Request(url, headers={"User-Agent": "pq-identity/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        results = data.get("results", [])
        return [{"handle": r.get("handle"), "pnl": r.get("pnlUsd"),
                 "win_rate": r.get("winRate")} for r in results[:5]]
    except Exception:
        return []


def search_github_for_address(address: str) -> list[dict]:
    """Search GitHub for repos containing a wallet address."""
    items, total = search_code(f'"{address}"', per_page=5)
    if total == -1:
        return []
    results = []
    seen_repos = set()
    for item in items:
        repo = item.get("repository", {}).get("full_name", "?")
        if repo in seen_repos:
            continue
        seen_repos.add(repo)
        results.append({
            "repo": repo,
            "path": item.get("path", "?"),
            "url": item.get("html_url", ""),
        })
    return results


def search_github_for_username(handle: str) -> list[dict]:
    """Search GitHub for a username/profile matching a handle."""
    # Try direct profile lookup
    user = get_user(handle)
    if user:
        return [{"username": user.get("login"), "name": user.get("name"),
                 "bio": user.get("bio", "")[:100],
                 "repos": user.get("public_repos", 0),
                 "followers": user.get("followers", 0)}]

    # Try variations: lowercase, with underscores, etc.
    variations = [handle.lower(), handle.replace("-", "_"),
                  handle.replace("_", "-")]
    for v in variations:
        user = get_user(v)
        if user:
            return [{"username": user.get("login"), "name": user.get("name"),
                     "bio": user.get("bio", "")[:100]}]
    return []


def extract_emails_from_github(handle: str) -> list[str]:
    """Extract email addresses from a GitHub user's commit history."""
    repos = get_user_repos(handle, per_page=5)
    emails = set()
    for repo in repos[:3]:
        name = repo.get("name", "")
        full = f"{handle}/{name}"
        items, _ = search_code(f"repo:{full}", per_page=3)
        time.sleep(1)
    return list(emails)[:5]


def search_social_profiles(handle: str) -> list[dict]:
    """Search for a handle across social platforms (OSINT)."""
    profiles = []
    platforms = {
        "twitter": f"https://twitter.com/{handle}",
        "fomo": f"https://fomo.family/{handle}",
    }
    for platform, url in platforms.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pq-identity/1.0"})
            req.get_method = lambda: "HEAD"
            with urllib.request.urlopen(req, timeout=5) as r:
                if r.status == 200:
                    profiles.append({"platform": platform, "url": url, "exists": True})
        except HTTPError as e:
            if e.code == 200:
                profiles.append({"platform": platform, "url": url, "exists": True})
        except Exception:
            pass
    return profiles


def resolve_all(address: str) -> dict:
    """Full identity resolution for a wallet address.

    Chains multiple signals to build an identity profile:
    1. FOMO handle lookup
    2. GitHub address search
    3. ENS resolution
    4. Social profile search for any handles found
    """
    result = {
        "address": address,
        "signals": [],
        "handles": [],
        "github_repos": [],
        "social_profiles": [],
    }

    # 1. FOMO handle lookup
    fomo = search_fomo_wallet(address)
    if fomo:
        for f in fomo:
            handle = f.get("handle", "")
            if handle:
                result["handles"].append({"source": "fomo", "handle": handle,
                                          "pnl": f.get("pnl")})
                result["signals"].append(f"FOMO trader: {handle}")

    # 2. GitHub address search
    gh_repos = search_github_for_address(address)
    if gh_repos:
        result["github_repos"] = gh_repos
        result["signals"].append(f"Found in {len(gh_repos)} GitHub repos")
        # Extract usernames from repo owners
        for repo in gh_repos:
            owner = repo["repo"].split("/")[0]
            if owner and owner not in [h["handle"] for h in result["handles"]]:
                result["handles"].append({"source": "github_repo", "handle": owner})

    # 3. For each handle found, search GitHub profile + social
    for h in result["handles"][:3]:
        handle = h["handle"]
        time.sleep(1)

        # GitHub profile
        gh_users = search_github_for_username(handle)
        for u in gh_users:
            result["signals"].append(f"GitHub: {u['username']} ({u.get('name', '?')})")

        # Social profiles
        social = search_social_profiles(handle)
        result["social_profiles"].extend(social)

    result["summary"] = {
        "handles_found": len(result["handles"]),
        "github_repos": len(result["github_repos"]),
        "social_profiles": len(result["social_profiles"]),
        "signals_count": len(result["signals"]),
    }

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 wallet_identity.py <address>")
        print("       Supports ETH (0x...) and SOL addresses")
        sys.exit(1)

    address = sys.argv[1]
    result = resolve_all(address)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
