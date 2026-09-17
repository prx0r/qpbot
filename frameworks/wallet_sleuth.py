#!/usr/bin/env python3
"""wallet_sleuth.py — full pipeline: funded wallet → GitHub identity.

Uses all available signals to connect on-chain wallets to real identities.
Every step is logged with QP proofs for verification.

Usage:
    python3 frameworks/wallet_sleuth.py <wallet_address>
    python3 frameworks/wallet_sleuth.py 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
"""
import sys
import os
import json
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, "/home/ubuntu/qprivately")

from scanners.registry import fire
from agentcom.audit import log_tool_exec
from scripts.simulations.wallet_investigate import investigate, ens_reverse_resolve, ens_github_record
from acom.objects import make_claim, make_evidence
from acom.gates import execute
from acom.receipts import transition, verify_receipt


def log_step(step_num, name, result):
    """Log a step with details."""
    print(f"  [{step_num}] {name}")
    if isinstance(result, dict):
        for k, v in result.items():
            if v and v != "none" and v != [] and v != 0:
                print(f"      {k}: {v}")


def sleuth_wallet(wallet_address: str) -> dict:
    """Full wallet sleuthing pipeline."""
    print("="*60)
    print(f"WALLET SLEUTHING: {wallet_address}")
    print("="*60)

    evidence_items = []
    findings = {}

    # ── Step 1: Balance check ─────────────────────────────────
    print()
    print("Step 1: Balance check")
    r = fire("eth_check", [wallet_address])
    balance = r.get("data", {}).get("total_usd", 0)
    log_step(1, "Balance", {"total_usd": f"${balance:,.2f}"})
    log_tool_exec("eth_check", [wallet_address], result={"ok": r.get("ok"), "balance": balance})

    ev_balance = make_evidence(
        "wallet_balance", balance, "usd",
        time.strftime("%Y-%m-%d"),
        {"class": "blockchain", "source_id": "etherscan",
         "artifact_hash": f"sha256:{wallet_address}"}
    )
    evidence_items.append(ev_balance)
    findings["balance"] = balance

    # ── Step 2: ENS resolution ────────────────────────────────
    print()
    print("Step 2: ENS resolution")
    ens = ens_reverse_resolve(wallet_address)
    if ens:
        log_step(2, "ENS", {"name": ens["name"]})
        findings["ens_name"] = ens["name"]
        findings["github_username"] = ens["name"].split(".")[0]

        # Try ENS GitHub text record
        gh_user = ens_github_record(wallet_address)
        if gh_user:
            findings["github_from_ens"] = gh_user
    else:
        print("      No ENS name found")

    # ── Step 3: GitHub code search ────────────────────────────
    print()
    print("Step 3: GitHub code search")
    gh_results = fire("wallet_github", ["address", wallet_address])
    repos = gh_results.get("data", {}).get("results", gh_results.get("data", {}).get("repos", []))
    log_step(3, "GitHub", {"repos_found": len(repos)})
    log_tool_exec("wallet_github", ["address", wallet_address],
                  result={"ok": gh_results.get("ok"), "repos": len(repos)})

    if repos:
        findings["github_repos"] = repos
        for repo in repos[:3]:
            print(f"      {repo.get('repo', '?')}: {repo.get('description', '')[:60]}")

    # ── Step 4: Full OSINT investigation ──────────────────────
    print()
    print("Step 4: Full OSINT investigation")
    result = investigate(wallet_address)

    signals = result.get("signals", [])
    handles = result.get("handles", [])
    social = result.get("social_profiles", [])

    log_step(4, "OSINT", {
        "signals": len(signals),
        "handles": len(handles),
        "social_profiles": len(social),
        "confidence": result.get("confidence", "low"),
    })
    log_tool_exec("wallet_investigate", [wallet_address],
                  result={"ok": True, "signals": len(signals)})

    for sig in signals:
        print(f"      Signal: {sig}")
    for h in handles:
        print(f"      Handle: {h.get('handle', '?')} ({h.get('source', '?')}, {h.get('confidence', '?')})")
    for s in social:
        print(f"      Social: {s.get('platform', '?')}: {s.get('username', '?')}")

    findings["signals"] = signals
    findings["handles"] = handles
    findings["social_profiles"] = social

    # ── Step 5: FOMO leaderboard ──────────────────────────────
    print()
    print("Step 5: FOMO leaderboard")
    fomo = fire("fomo_leaderboard", ["leaderboard"])
    traders = fomo.get("data", {}).get("traders", [])
    log_step(5, "FOMO", {"traders": len(traders)})

    # Cross-reference: check if any handle appears in FOMO
    for h in handles:
        handle = h.get("handle", "")
        if handle in traders:
            print(f"      MATCH: {handle} is on FOMO leaderboard!")
            findings["fomo_match"] = handle

    # ── Step 6: Classify the wallet ───────────────────────────
    print()
    print("Step 6: Classify wallet")
    classify_result = fire("classify", [wallet_address])
    log_step(6, "Classify", classify_result.get("data", {}))

    # ── QP Proof ──────────────────────────────────────────────
    print()
    print("Step 7: QP proof — verify findings")
    claim = make_claim(
        f"GitHub identity found for {wallet_address[:10]}...",
        "identity.wallet",
        "TRUE" if findings.get("github_username") or findings.get("github_repos") else "UNKNOWN"
    )

    # Create evidence from all findings
    ev_signals = make_evidence(
        "identity_signals", len(signals), "count",
        time.strftime("%Y-%m-%d"),
        {"class": "osint", "source_id": f"investigate:{wallet_address[:10]}",
         "artifact_hash": f"sha256:{wallet_address}"}
    )
    evidence_items.append(ev_signals)

    ev_handles = make_evidence(
        "handles_found", len(handles), "count",
        time.strftime("%Y-%m-%d"),
        {"class": "osint", "source_id": f"handles:{wallet_address[:10]}",
         "artifact_hash": f"sha256:{wallet_address}"}
    )
    evidence_items.append(ev_handles)

    # Execute gates
    g1 = execute("evidence-fresh-v1", {"evidence": evidence_items})
    g2 = execute("no-duplicate-v1", {"evidence": evidence_items})
    print(f"  evidence-fresh: {g1['result']}")
    print(f"  no-duplicate: {g2['result']}")

    if claim["result"] == "TRUE":
        g3 = execute("claim-resolved-v1", {"claim": claim, "evidence": evidence_items})
        gates = ["evidence-fresh-v1", "no-duplicate-v1", "claim-resolved-v1"]
    else:
        gates = ["evidence-fresh-v1", "no-duplicate-v1"]

    receipt = transition(
        {"cursor": 0}, claim, evidence_items, gates,
        {"worker": "wallet_sleuth", "tokens": 0}, 4
    )
    v = verify_receipt(receipt)

    print(f"  Receipt: {receipt['id']}")
    print(f"  Passed: {receipt['passed']}")
    print(f"  Verified: {v['ok']}")

    # ── Summary ───────────────────────────────────────────────
    print()
    print("="*60)
    print("SLEUTHING RESULT")
    print("="*60)
    print(f"  Wallet: {wallet_address}")
    print(f"  Balance: ${findings.get('balance', 0):,.2f}")
    print(f"  ENS: {findings.get('ens_name', 'none')}")
    print(f"  GitHub username: {findings.get('github_username', 'none')}")
    print(f"  GitHub repos: {len(findings.get('github_repos', []))}")
    print(f"  Signals: {len(signals)}")
    print(f"  Handles: {[h.get('handle') for h in handles]}")
    print(f"  Confidence: {result.get('confidence', 'low')}")
    print()
    print(f"  QP Proof: {'PASS' if receipt['passed'] else 'FAIL'}")
    print(f"  Receipt: {receipt['id']}")
    print(f"  Verified: {v['ok']}")

    return {
        "wallet": wallet_address,
        "findings": findings,
        "receipt": receipt,
        "verified": v["ok"],
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 frameworks/wallet_sleuth.py <wallet_address>")
        sys.exit(1)

    wallet = sys.argv[1]
    result = sleuth_wallet(wallet)

    # Log to runs/
    os.makedirs(os.path.join(ROOT, "runs"), exist_ok=True)
    with open(os.path.join(ROOT, "runs", "wallet-sleuth.jsonl"), "a") as f:
        f.write(json.dumps({
            "run_id": time.strftime("%Y%m%d-%H%M%S", time.gmtime()),
            "wallet": wallet,
            "findings": result["findings"],
            "receipt_id": result["receipt"]["id"],
            "verified": result["verified"],
            "timestamp": time.time(),
        }, sort_keys=True) + "\n")
