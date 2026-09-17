#!/usr/bin/env python3
"""Wallet Investigate — full OSINT chain from wallet address to identity.

Chains every available signal to connect on-chain wallets to real identities:
1. ENS reverse resolution (name.eth)
2. ENS com.github text record (name.eth → GitHub username)
3. Farcaster profile lookup
4. Lens Protocol profile lookup
5. FOMO trader handle
6. GitHub code search for wallet address
7. Etherscan/Solscan name tags (scrape)
8. Arkham entity labels
9. OpenSea profile (if NFT holder)
10. Cross-platform username correlation
11. Donation address in repo READMEs
12. Gitcoin Passport linked accounts

Each method is a signal. The tool chains them, deduplicates handles,
and returns a unified identity profile.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.request
from urllib.error import HTTPError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from scripts.simulations.github import search_code, get_user, get_user_repos
from scripts.simulations.rpc import eth_rpc
from scanners.patterns import ETH_ADDRESS, redact

USER_AGENT = "pq-investigate/1.0"


# ── Signal 1: ENS reverse resolution ──────────────────────────────────

def ens_reverse_resolve(address: str) -> dict | None:
    """Resolve ENS name for an ETH address. Returns name.eth or None."""
    try:
        # ENS Registry: 0x0000000000C2E074eC69008fD4189972B3e0D3F0
        # ReverseRegistrar: 0xa269e756E8e73Be9115f51b3e7D4D0e0b2c5D8F3
        # Use public ENS subgraph or the Etherscan label approach
        # For now, check if the address has an ENS name via the resolution API
        url = f"https://api.ensideas.com/ens/resolve/{address}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        if data.get("displayName") and data["displayName"] != address:
            return {"name": data["displayName"], "source": "ens"}
    except Exception:
        pass
    return None


def ens_github_record(address: str) -> str | None:
    """Check ENS com.github text record for a GitHub username."""
    try:
        # Use the ensideas API which includes text records
        url = f"https://api.ensideas.com/ens/resolve/{address}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        github = data.get("github")
        if github:
            return github
    except Exception:
        pass
    return None


# ── Signal 2: Farcaster profile ───────────────────────────────────────

def farcaster_lookup(address: str) -> dict | None:
    """Look up Farcaster profile by custody address."""
    try:
        url = f"https://api.neynar.com/v2/farcaster/user/by-custody-address?custody_address={address}"
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "api_key": os.environ.get("NEYNAR_API_KEY", ""),
        })
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        user = data.get("result", {}).get("user")
        if user:
            return {
                "username": user.get("username", ""),
                "display_name": user.get("display_name", ""),
                "bio": user.get("bio", "")[:200],
                "source": "farcaster",
            }
    except Exception:
        pass
    return None


# ── Signal 3: Lens Protocol profile ───────────────────────────────────

def lens_lookup(address: str) -> dict | None:
    """Look up Lens Protocol profile by wallet address."""
    try:
        url = "https://api.lens.xyz"
        query = json.dumps({
            "query": """{ profiles(request: {ownedBy: ["%s"]}) { items { handle bio } } }""" % address
        }).encode()
        req = urllib.request.Request(url, data=query, headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        })
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        items = data.get("data", {}).get("profiles", {}).get("items", [])
        if items:
            p = items[0]
            return {
                "username": p.get("handle", ""),
                "bio": p.get("bio", "")[:200],
                "source": "lens",
            }
    except Exception:
        pass
    return None


# ── Signal 4: FOMO handle ─────────────────────────────────────────────

def fomo_lookup(address: str) -> dict | None:
    """Look up FOMO trader handle by wallet address."""
    try:
        url = f"https://api.fomoapi.io/v2/search?q={address}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        results = data.get("results", [])
        if results:
            r = results[0]
            return {
                "username": r.get("handle", ""),
                "pnl": r.get("pnlUsd", 0),
                "win_rate": r.get("winRate", 0),
                "source": "fomo",
            }
    except Exception:
        pass
    return None


# ── Signal 5: GitHub code search ──────────────────────────────────────

def github_address_search(address: str) -> list[dict]:
    """Search GitHub for repos containing the wallet address."""
    items, total = search_code(f'"{address}"', per_page=10)
    if total == -1:
        return []
    results = []
    seen_repos = set()
    for item in items:
        repo = item.get("repository", {}).get("full_name", "?")
        if repo in seen_repos:
            continue
        seen_repos.add(repo)
        path = item.get("path", "")
        # Check if it's a donation address (README) — higher confidence
        is_donation = "readme" in path.lower() or "donate" in path.lower()
        results.append({
            "repo": repo,
            "path": path,
            "url": item.get("html_url", ""),
            "is_donation_address": is_donation,
            "owner": repo.split("/")[0] if "/" in repo else "",
        })
    return results


# ── Signal 6: Etherscan name tag (scrape) ─────────────────────────────

def etherscan_name_tag(address: str) -> str | None:
    """Try to get the Etherscan name tag for an address."""
    try:
        url = f"https://api.etherscan.io/api?module=contract&action=getsourcecode&address={address}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        result = data.get("result", [{}])
        if isinstance(result, list) and result:
            contract_name = result[0].get("ContractName", "")
            if contract_name:
                return contract_name
    except Exception:
        pass
    return None


# ── Signal 7: OpenSea profile ─────────────────────────────────────────

def opensea_profile(address: str) -> dict | None:
    """Check OpenSea for a profile on this address."""
    try:
        url = f"https://api.opensea.io/api/v2/accounts/{address}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
        username = data.get("username", "")
        if username:
            return {"username": username, "source": "opensea"}
    except Exception:
        pass
    return None


# ── Signal 8: Username cross-platform search ──────────────────────────

def check_username_platforms(username: str) -> list[dict]:
    """Check if a username exists on various platforms."""
    platforms = {
        "github": f"https://api.github.com/users/{username}",
        "twitter": f"https://twitter.com/{username}",
        "fomo": f"https://fomo.family/{username}",
    }
    found = []
    for platform, url in platforms.items():
        try:
            if platform == "github":
                user = get_user(username)
                if user:
                    found.append({
                        "platform": "github",
                        "username": user.get("login", username),
                        "name": user.get("name", ""),
                        "bio": user.get("bio", "")[:100],
                        "repos": user.get("public_repos", 0),
                    })
            else:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                req.get_method = lambda: "HEAD"
                with urllib.request.urlopen(req, timeout=3) as r:
                    if r.status == 200:
                        found.append({"platform": platform, "username": username, "exists": True})
        except HTTPError as e:
            if e.code == 200:
                found.append({"platform": platform, "username": username, "exists": True})
        except Exception:
            pass
    return found


# ── Main investigation pipeline ────────────────────────────────────────

def investigate(address: str) -> dict:
    """Full OSINT investigation of a wallet address.

    Chains all signals and returns a unified identity profile.
    """
    result = {
        "address": address,
        "chain": "ethereum" if address.startswith("0x") else "unknown",
        "signals": [],
        "handles": [],
        "github_repos": [],
        "social_profiles": [],
        "github_username": "",
        "ens_name": "",
        "confidence": "low",
    }

    handles_found = set()

    # ── Phase 1: Direct on-chain resolution (fast, free) ──

    # ENS reverse resolution
    ens = ens_reverse_resolve(address)
    if ens:
        result["ens_name"] = ens["name"]
        result["signals"].append(f"ENS: {ens['name']}")
        # Extract username from ENS (vitalik.eth → vitalik)
        base = ens["name"].split(".")[0]
        if base and base not in handles_found:
            handles_found.add(base)
            result["handles"].append({"handle": base, "source": "ens", "confidence": "high"})

    # ENS GitHub text record
    github_from_ens = ens_github_record(address)
    if github_from_ens:
        result["github_username"] = github_from_ens
        result["signals"].append(f"ENS GitHub: {github_from_ens}")
        if github_from_ens not in handles_found:
            handles_found.add(github_from_ens)
            result["handles"].append({"handle": github_from_ens, "source": "ens_github", "confidence": "very_high"})

    # Farcaster
    fc = farcaster_lookup(address)
    if fc:
        result["signals"].append(f"Farcaster: @{fc['username']}")
        if fc["username"] not in handles_found:
            handles_found.add(fc["username"])
            result["handles"].append({"handle": fc["username"], "source": "farcaster", "confidence": "high"})

    # Lens
    lens = lens_lookup(address)
    if lens:
        result["signals"].append(f"Lens: @{lens['username']}")
        if lens["username"] not in handles_found:
            handles_found.add(lens["username"])
            result["handles"].append({"handle": lens["username"], "source": "lens", "confidence": "high"})

    # FOMO
    fomo = fomo_lookup(address)
    if fomo:
        result["signals"].append(f"FOMO: @{fomo['username']} (PnL: ${fomo.get('pnl', 0):,.0f})")
        if fomo["username"] not in handles_found:
            handles_found.add(fomo["username"])
            result["handles"].append({"handle": fomo["username"], "source": "fomo", "confidence": "high"})

    # Etherscan name tag
    etherscan_name = etherscan_name_tag(address)
    if etherscan_name:
        result["signals"].append(f"Etherscan: {etherscan_name}")

    # OpenSea
    opensea = opensea_profile(address)
    if opensea:
        result["signals"].append(f"OpenSea: @{opensea['username']}")
        if opensea["username"] not in handles_found:
            handles_found.add(opensea["username"])
            result["handles"].append({"handle": opensea["username"], "source": "opensea", "confidence": "medium"})

    # ── Phase 2: GitHub search (slower, network) ──

    gh_repos = github_address_search(address)
    if gh_repos:
        result["github_repos"] = gh_repos
        result["signals"].append(f"GitHub: found in {len(gh_repos)} repos")
        for repo in gh_repos:
            owner = repo.get("owner", "")
            if owner and owner not in handles_found and owner != "ghost":
                handles_found.add(owner)
                conf = "very_high" if repo.get("is_donation_address") else "medium"
                result["handles"].append({"handle": owner, "source": "github_repo", "confidence": conf})

    # ── Phase 3: Cross-platform correlation ──

    for h in list(handles_found)[:5]:
        time.sleep(0.5)
        platforms = check_username_platforms(h["handle"] if isinstance(h, dict) else h)
        result["social_profiles"].extend(platforms)

    # ── Phase 4: Confidence scoring ──

    high_conf = sum(1 for h in result["handles"] if h.get("confidence") in ("high", "very_high"))
    if high_conf >= 2:
        result["confidence"] = "high"
    elif high_conf >= 1:
        result["confidence"] = "medium"
    elif result["handles"]:
        result["confidence"] = "low"

    result["summary"] = {
        "handles_found": len(result["handles"]),
        "github_repos": len(result["github_repos"]),
        "social_profiles": len(result["social_profiles"]),
        "signals_count": len(result["signals"]),
        "confidence": result["confidence"],
        "github_username": result["github_username"],
        "ens_name": result["ens_name"],
    }

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 wallet_investigate.py <address>")
        print("       Full OSINT chain: wallet → identity → GitHub")
        sys.exit(1)

    address = sys.argv[1]
    result = investigate(address)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
