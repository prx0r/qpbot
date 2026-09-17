# PRIVACY — what cannot leak, and how that's proven

## Guarantees

- Model sees booleans, never values. `credential_available(name)` is the
  only secret-related symbol in model context. Tool outputs carrying
  resolved values never enter chat history — resolution happens in the
  tool channel, results stay evidence-side.
- Store file holds ciphertext plus grant metadata only. Verified by test:
  marker secret absent from raw file bytes.
- Audit holds names, tools, workers, timestamps — metadata, never values.
- H-task surfaces (views, queue JSON, bridge tiles) carry questions and
  predictions only. Secret-kind tasks hold no value field at all; answering
  one with a value raises.
- Errors are generic (`unknown secret`, `capability mismatch`, grant
  denials). No error path echoes a value, a capability, or which check
  failed first.
- Daemon journal and status feed carry ids and states only.
- Sim-game credentials in `core/` (admin/admin etc.) are puzzle fixtures
  the agent is meant to guess, not secrets. Out of scope by design.
- Repo scan: no live keys anywhere outside vendored SDK type declarations
  (false positives in node_modules). `QPBOT_VAULT_KEY` resolves env-first;
  nothing writes it to disk or logs.

## Known local-only exposures (accepted, documented)

- Flag strings pass via subprocess argv to `core.cli submit`, visible
  momentarily in the local process table. CTF flags are game data the
  model already holds, not user secrets. Never run shared multi-user
  without containers.
- Vault key file is 0600 on local disk. Device compromise equals vault
  compromise — same as any local keychain. No mitigation beyond OS
  full-disk encryption and not running as shared user.

## Operator rules

Keys via env at runtime, never repo or chat. Vault file never committed
(`runs/`, key paths ignored). New channels that touch secrets must add a
marker test in `tests/test_privacy.py` before merging.
