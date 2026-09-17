#!/usr/bin/env python3
"""FOMO Leaderboard — scrape top traders from fomo.family web.

No API key needed. Fetches the public leaderboard page and extracts
trader handles, PnL, and wallet addresses. Returns structured JSON
for the LLM to prioritize targets.
"""
import json
import re
import sys
import urllib.request


def fetch_url(url, timeout=15):
    req = urllib.request.Request(url, headers={
        "User-Agent": "pq-fomo-scraper/1.0",
        "Accept": "text/html,application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def scrape_leaderboard_web():
    """Scrape the FOMO leaderboard from the public web page."""
    try:
        html = fetch_url("https://fomo.family/leaderboard")
        # Extract trader data from the HTML/JSON embedded in the page
        # FOMO embeds JSON data in script tags
        json_match = re.search(r'"traders"\s*:\s*(\[.*?\])', html, re.DOTALL)
        if json_match:
            traders = json.loads(json_match.group(1))
            return {"ok": True, "source": "fomo.family/web", "traders": traders[:20]}
        # Fallback: extract handles and PnL from visible text patterns
        handles = re.findall(r'(?<=@)([a-zA-Z0-9_]{3,30})', html)
        return {"ok": True, "source": "fomo.family/web", "traders": handles[:20]}
    except Exception as e:
        return {"ok": False, "error": f"fomo web: {e}", "traders": []}


def lookup_handle(handle):
    """Look up a specific FOMO trader by handle. Returns wallet + PnL."""
    try:
        # Try the fomoapi.io public lookup (no key needed for basic search)
        data = fetch_url(f"https://api.fomoapi.io/v2/search?q={handle}&type=traders")
        result = json.loads(data)
        if result.get("results"):
            return {"ok": True, "results": result["results"][:5]}
        return {"ok": False, "error": "not found", "query": handle}
    except Exception as e:
        return {"ok": False, "error": str(e), "query": handle}


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 fomo_leaderboard.py leaderboard [min_pnl]")
        print("       python3 fomo_leaderboard.py lookup <handle>")
        sys.exit(1)

    action = sys.argv[1]

    if action == "leaderboard":
        min_pnl = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        result = scrape_leaderboard_web()
        print(json.dumps(result, indent=2))

    elif action == "lookup":
        if len(sys.argv) < 3:
            print("Usage: python3 fomo_leaderboard.py lookup <handle>")
            sys.exit(1)
        handle = sys.argv[2]
        result = lookup_handle(handle)
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown action: {action}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
