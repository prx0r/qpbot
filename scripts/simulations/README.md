# scripts/simulations — CTF flag capture tools

Extracted from `stallshark/BLUE-TEAM-COMBINED.md` (Cloudflare R2: `blog-video-assets` bucket).

## Scripts

| Script | What it does | Usage |
|---|---|---|
| `gh_secret_scanner.py` | Search GitHub for leaked keys (needs `GH_TOKEN`) | `python3 gh_secret_scanner.py` |
| `eth_check.py` | Check ETH + ERC-20 balance (free, no key) | `python3 eth_check.py 0x...` |
| `sol_check.py` | Check SOL + SPL balance (free, no key) | `python3 sol_check.py <address>` |
| `mnemonic_derive.py` | BIP-39 mnemonic → seed derivation | `python3 mnemonic_derive.py "word1 word2 ..."` |
| `env_extract.py` | Scan directory for secrets in .env files | `python3 env_extract.py /path/to/scan` |
| `batch_check.py` | Check many addresses in parallel | `python3 batch_check.py addresses.txt` |
| `classify_secret.py` | Detect secret type (eth/mnemonic/aws/etc) | `python3 classify_secret.py <value>` |
| `git_history_scan.py` | Find secrets in git history | `python3 git_history_scan.py /path/to/repo` |

## Integration with pq

These feed into the core loop:

1. **Scanner phase**: `gh_secret_scanner.py` + `env_extract.py` + `git_history_scan.py` find candidates
2. **Classifier**: `classify_secret.py` types each finding
3. **Triage**: `batch_check.py` + `eth_check.py` + `sol_check.py` rank by value
4. **Prize capture**: classified secrets stored in vault via `vault.store()`

## Vault access

Cloudflare R2 credentials are in the vault under `infrastructure` scope:
- `CF_ACCOUNT_ID`, `CF_API_TOKEN` (worker: `storage` or `tunnel`)
- `CF_R2_ACCESS_KEY`, `CF_R2_SECRET_KEY` (worker: `storage`)
