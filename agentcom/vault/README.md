# Vault — why this shape

Advice.md demands: encrypted value, allowed tools/workers, project scope,
expiry, usage count, never-expose-to-model, capability token to a specific
tool/process, model sees only `credential_available("x")`.

Evaluated: HashiCorp Vault (server + network — wrong for privacy-first
local), cloud KMS (wrong trust model), SOPS+age (great for secrets-in-git,
no runtime scoping/expiry/usage semantics), OS keychain (no per-tool grants
or audit, needs new deps). Cohesive fit: local AES-256-GCM vault file via
the already-installed `cryptography` Fernet, master key from env or a
0600 key file, scoped grants with expiry and usage caps, append-only audit.
No new dependencies, no network, no server. SOPS+age stays the answer if
vault contents ever need to live in git — different problem.
