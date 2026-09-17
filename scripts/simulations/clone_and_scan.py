#!/usr/bin/env python3
"""Clone and Scan — clone a git repo and scan for secrets.

Runs git_history + env_extract on a cloned repo. Returns all findings.
The repo is cloned to a temp directory, scanned, then cleaned up.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCANNERS_DIR = os.path.join(ROOT, "scanners")
SIM_DIR = os.path.join(ROOT, "scripts", "simulations")


def git_clone(repo_url, dest_dir, timeout=60):
    """Clone a git repository. Returns (success, path_or_error)."""
    try:
        p = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, dest_dir],
            capture_output=True, text=True, timeout=timeout
        )
        if p.returncode != 0:
            return False, f"git clone failed: {p.stderr.strip()}"
        return True, dest_dir
    except subprocess.TimeoutExpired:
        return False, "clone timeout"
    except Exception as e:
        return False, f"clone error: {e}"


def run_scanner(script, args, timeout=30):
    """Run a scanner script and return parsed output."""
    script_path = os.path.join(SIM_DIR, script)
    if not os.path.exists(script_path):
        script_path = os.path.join(SCANNERS_DIR, script)
    if not os.path.exists(script_path):
        return {"ok": False, "error": f"script not found: {script}"}

    cmd = [sys.executable, script_path] + args
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        raw = p.stdout.strip()
        try:
            return {"ok": True, "data": json.loads(raw)}
        except json.JSONDecodeError:
            return {"ok": True, "data": {"raw": raw}}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "scanner timeout"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def scan_repo(repo_path):
    """Run all local scanners on a cloned repo."""
    findings = {
        "git_history": [],
        "env_files": [],
    }

    # Git history scan
    hist = run_scanner("git_history_scan.py", [repo_path])
    if hist.get("ok") and hist.get("data"):
        findings["git_history"] = hist["data"] if isinstance(hist["data"], list) else [hist["data"]]

    # Env file scan
    env = run_scanner("env_extract.py", [repo_path])
    if env.get("ok") and env.get("data"):
        findings["env_files"] = env["data"] if isinstance(env["data"], list) else [env["data"]]

    return findings


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 clone_and_scan.py <repo_url_or_path>")
        print("       Supports GitHub URLs or local paths")
        sys.exit(1)

    target = sys.argv[1]
    is_local = os.path.isdir(target)
    findings = {"target": target, "local": is_local}

    if is_local:
        # Scan local directory directly
        findings["scan"] = scan_repo(target)
    else:
        # Clone then scan
        tmp_dir = tempfile.mkdtemp(prefix="pq-scan-")
        try:
            ok, result = git_clone(target, tmp_dir)
            if not ok:
                findings["error"] = result
                print(json.dumps(findings, indent=2))
                sys.exit(1)
            findings["scan"] = scan_repo(tmp_dir)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # Count secrets found
    hist_count = len(findings.get("scan", {}).get("git_history", []))
    env_count = len(findings.get("scan", {}).get("env_files", []))
    findings["total_secrets"] = hist_count + env_count
    findings["summary"] = {
        "git_history_secrets": hist_count,
        "env_file_secrets": env_count,
    }

    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
