# qpbot — Vault Guide

## How the vault works

Encrypted secret store at `~/.qpbot/vault.json`. Fernet encryption (AES-128-CBC + HMAC).

## Key concepts

- **Secrets**: encrypted API keys, tokens, credentials
- **Grants**: scoped permissions (tool, worker, scope, expiry, usage cap)
- **Resolution**: 7-check gate before revealing plaintext

## Vault commands

```bash
# List all keys
python3 -m core.cli vault-find --kind llm-inference --tier paid

# Usage stats
python3 -m core.cli vault-usage

# Store a new key
printf 'your-api-key' | python3 -m core.cli vault-store MY_KEY \
  --tools dashboard-chat,harness \
  --workers chat-session,harness \
  --scope opencode-go
```

## Python API

```python
from agentcom.vault.store import Vault

vault = Vault("/home/ubuntu/.qpbot/vault.json")

# Find keys
active = vault.find(kind="llm-inference", tier="paid")

# Resolve a key (7-check gate)
key = vault.resolve(
    name="LLM_KEY",
    tool="dashboard-chat",
    worker="chat-session",
    capability="OdWSXW7NE7cjF27b5B8tMrcX"
)

# Usage summary
usage = vault.usage_summary()
```

## Resolution checks

1. Key exists in vault
2. Key is active
3. Capability matches
4. Tool is granted
5. Worker is granted
6. Scope matches
7. Not expired, usage cap not hit

## Current keys

| Name | Provider | Model | Capability |
|------|----------|-------|------------|
| LLM_KEY | opencode-go | mimo-v2.5 | OdWSXW7NE7cjF27b5B8tMrcX |
| LLM_KEY_2 | opencode-go | mimo-v2.5 | CcHbao2B4vILUS7GYgAsbXgc |
| LLM_KEY_3 | opencode-go | mimo-v2.5 | N5GH4vqBCUbaWFZPGJIuuELJ |
| LLM_KEY_4 | opencode-go | mimo-v2.5 | GxVv8a68yuCZTwu3NOnFCXZ8 |
| LLM_KEY_5 | opencode-go | mimo-v2.5 | P6RE1CSJFStoTHUiDGRqHjGM |

## API endpoint

```
POST https://opencode.ai/zen/go/v1/chat/completions
Headers:
  Authorization: Bearer <key>
  x-opencode-session: <uuid>
Body:
  {"model": "mimo-v2.5", "messages": [...], "max_tokens": 4096}
```
