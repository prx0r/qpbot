# qpbot — autonomous red-team system

One repo: the working core plus the vendors it builds on.

## Layout

- `core/` — the running game. Arena with server-side verifier, hash-chained
  ledger with receipts, red-team agent loop, three-lane tournament,
  autopilot with spend caps, promotion gate, CLI. Stdlib Python only.
- `connectors/pi-xmrecon/` — Pi integration. Raw chat mode (no tools) and
  red-team mode (explicit arena tools backed by `core/`). Needs `npm
  install` plus your own model key at runtime; nothing stored.
- `pi/` — Pi agent runtime vendor (unmodified clone).
- `argos/` — desktop control plane vendor (unmodified clone).
- `agentdeck/` — phone/desktop controller vendor (unmodified clone).

## The working model you can test right now

```bash
python3 -m pytest tests/ -q
python3 -m core.cli tournament
python3 -m core.cli autopilot --rounds 3
python3 -m core.cli run --agent red-01 --pack demo
```

Tournament runs three strategy lanes against the demo pack and ranks them.
Autopilot loops rounds until capture with global caps. Promotion requires
minimum uses, 90% pass rate, zero regressions — nothing self-certifies.

## How the pieces connect

Pi red-team mode calls arena tools that shell out to `core.cli`. Every
claim settles server-side; Pi never sees flag plaintext. Receipts chain in
the ledger. AgentDeck watches sessions (working / waiting / idle) and
approvals from the phone. Argos hosts the desktop side over ACP via pi-acp.
See `docs/STACK.md`.
