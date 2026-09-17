# qpbot — On-Chain Tools

## Available tools

| Tool | Script | Network | Description |
|------|--------|---------|-------------|
| whale_feed | simulations/whale_feed.py | Yes | Large BTC/ETH transactions |
| eth_check | simulations/eth_check.py | Yes | ETH + ERC-20 balance |
| sol_check | simulations/sol_check.py | Yes | SOL + SPL balance |
| fomo_leaderboard | simulations/fomo_leaderboard.py | Yes | Top traders from fomo.family |
| wallet_investigate | simulations/wallet_investigate.py | Yes | Full OSINT chain |
| wallet_github | simulations/wallet_github_search.py | Yes | Search GitHub for wallet |
| clone_scan | simulations/clone_and_scan.py | Yes | Clone repo, scan secrets |
| classify | simulations/classify_secret.py | No | Detect key type |
| drain_classify | simulations/drain_classify.py | No | Drain authority class |
| batch_check | simulations/batch_check.py | Yes | Check many addresses |
| mnemonic_derive | simulations/mnemonic_derive.py | No | BIP-39 derivation |
| gh_search | simulations/gh_secret_scanner.py | Yes | Search GitHub for leaked keys |
| env_extract | simulations/env_extract.py | No | Scan .env files |
| git_history | simulations/git_history_scan.py | No | Find secrets in git history |

## Usage

```bash
# Whale feed (transactions > $100k)
python3 scripts/simulations/whale_feed.py 100000

# ETH balance
python3 scripts/simulations/eth_check.py 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045

# FOMO leaderboard
python3 scripts/simulations/fomo_leaderboard.py leaderboard
python3 scripts/simulations/fomo_leaderboard.py lookup <handle>

# Wallet investigation (full OSINT)
python3 scripts/simulations/wallet_investigate.py 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045

# Clone and scan repo
python3 scripts/simulations/clone_and_scan.py https://github.com/user/repo
```

## Python API

```python
from scanners.registry import fire, tool_names

# List available tools
print(tool_names())

# Execute a tool
result = fire("whale_feed", ["100000"])
print(result)  # {"ok": True, "data": {...}, "tool": "whale_feed"}
```

## Tool output format

```json
{
  "ok": true,
  "data": { ... },
  "tool": "whale_feed"
}
```

## Categories

**On-chain discovery:**
- whale_feed, eth_check, sol_check, fomo_leaderboard
- wallet_investigate, wallet_github, wallet_identity

**Secret detection:**
- clone_scan, env_extract, git_history, gh_search

**Classification:**
- classify, drain_classify

**Utility:**
- batch_check, mnemonic_derive
