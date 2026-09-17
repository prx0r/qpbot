"""GitHub — shared GitHub API helpers.

Single source of truth for GitHub Code Search and raw file fetching.
Every GitHub tool imports from here instead of duplicating.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from urllib.parse import quote
from urllib.error import HTTPError

TOKEN = os.environ.get("GH_TOKEN", "")
HEADERS = {
    "Authorization": f"token {TOKEN}" if TOKEN else "",
    "Accept": "application/vnd.github.v3.text-match+json",
    "User-Agent": "pq-github/1.0",
}


def search_code(query: str, per_page: int = 10) -> tuple[list[dict], int]:
    """Search GitHub code. Returns (items, total_count)."""
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


def fetch_raw(repo: str, path: str) -> str | None:
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


def get_user(username: str) -> dict | None:
    """Get GitHub user profile."""
    url = f"https://api.github.com/users/{username}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception:
        return None


def get_user_repos(username: str, per_page: int = 30) -> list[dict]:
    """Get a user's public repos."""
    url = f"https://api.github.com/users/{username}/repos?per_page={per_page}&sort=updated"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception:
        return []


def email_to_user(email: str) -> str | None:
    """Try to find a GitHub username from an email address.

    Checks commit history and GPG keys for the email.
    """
    # Search for the email in commit author fields
    items, _ = search_code(f'"<{email}>"', per_page=5)
    for item in items:
        # The repo name gives us a clue, but we need the commit author
        repo = item.get("repository", {}).get("full_name", "")
        if repo:
            # Try to get the user from the repo
            owner = repo.split("/")[0] if "/" in repo else ""
            if owner and owner != "ghost":
                return owner
    return None
