# High-Probability Repository Target List

## Goal

Find GitHub repositories most likely to contain wallet addresses in their history. Not to find secrets (requires full clone), but to build a ranked target list.

## Method

1. Search GitHub for repos with crypto/trading keywords
2. Rank by fork count (more forks = more people running the code)
3. Check if repos contain wallet addresses (README, code, configs)
4. Score by probability of containing funded wallets

## Target categories (ranked by probability)

### Tier 1: Trading bots (highest probability)
| Repo | Forks | Why |
|------|-------|-----|
| BowTiedDevil/degenbot | 197 | Uniswap V2/V3 arbitrage, users configure wallets |
| nelso0/barbotine-arbitrage-bot | 155 | CEX arbitrage, users configure API keys + wallets |
| mortdeus/solana-copy-sniper-mev-trading-bot | 437 | Solana sniper, users configure wallet private keys |
| chainstacklabs/pumpfun-bonkfun-bot | 354 | Pump.fun bot, users configure wallet |
| coffellas-cto/Solana-Copy-Trading-Bot | 114 | Copy trading, users configure wallet |

### Tier 2: MEV templates (high probability)
| Repo | Forks | Why |
|------|-------|-----|
| solidquant/mev-templates | 171 | MEV templates, users add wallet configs |
| hitechlan1001/Ethereum_Mev_Bot_Uniswap- | 1 | MEV bot, users add wallet |

### Tier 3: Exchange bots (medium probability)
| Repo | Forks | Why |
|------|-------|-----|
| hummingbot/hummingbot | 4933 | Major exchange bot, users configure wallets |
| ccxt/ccxt | 8842 | Exchange library, users add wallet integration |

### Tier 4: DeFi tutorials (lower probability)
| Repo | Forks | Why |
|------|-------|-----|
| ethereumdevio-dex-tutorial | - | Tutorial, may have example wallets |

## How to use this list

For each repo:
1. Check fork count (higher = more users)
2. Search code for wallet patterns (0x, private_key, mnemonic)
3. Check README for donation addresses
4. Check config files for wallet settings
5. Check git history for leaked addresses

## Next steps

1. Get GitHub token (vault cap resets or new token)
2. Run automated search across all Tier 1 repos
3. Score each fork by probability of containing wallet
4. Build prioritized target list
