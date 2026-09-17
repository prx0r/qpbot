"""Deterministic scanners — recon that feeds the core loop.

Scanners find, the LLM loop captures. Every scanner emits findings:
  {scanner, target_id, kind, detail, confidence, ts}
Recon only: scanners never submit flags. Run: python3 -m scanners.run_all
Wordlists under scanners/wordlists/ grow from captures (feed-out).
"""
