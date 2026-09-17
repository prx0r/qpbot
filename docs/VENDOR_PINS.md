# Vendor pins (verified 2026-09-17)

Vendors are unmodified clones. Never patch in place — adapter code lives in
`agentcom/` and `connectors/`. To upgrade: pull upstream, re-run every suite,
update the pin below.

| Vendor | Path | Pin |
|---|---|---|
| Pi runtime | `pi/` | `e4c75a7` |
| Argos desktop | `argos/` | `2db3aebc` |
| AgentDeck controller | `agentdeck/` | `fde84b9` |
| pi-acp bridge | `/home/ubuntu/pi-acp` (external, built `dist/`) | `3f46f29` |
| AgentCom v2 source | `/agentcomfinal` (external, 70 green) | `c2388f4` |
| QP truth core | `/home/ubuntu/qp` (external) | `21588f7` |

## Hygiene rules

- `core/` is stdlib-only Python. No new dependencies without a plan update.
- Secrets never enter the repo: keys via env at runtime only.
- Arena verifier is frozen logic: behavior changes need a new test contract.
- Verbs on `core.cli` are the only subprocess boundary Pi tools may call,
  always argv-parametrized, never string-interpolated.
