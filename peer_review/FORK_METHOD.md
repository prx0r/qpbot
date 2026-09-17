# Wallet → GitHub: The Fork Method

## The insight

People who run trading bots usually fork them from GitHub. The fork owner has a public GitHub profile. If we can find their wallet address in their other repos, we've connected the dots.

## The method

```
1. Find popular trading bot repos (high forks)
2. List fork owners
3. For each fork owner:
   a. Check their public repos for wallet addresses
   b. If found → check if wallet is funded
   c. If funded → we have a funded wallet with GitHub identity
```

## Why this works

- Trading bot developers fork existing bots (not write from scratch)
- Fork owners have public GitHub profiles
- Developers often put wallet addresses in their repos (for donations, testing, config)
- If a wallet is funded AND connected to a fork owner, we've found a live trader

## What we found

| Repo | Forks | What we learned |
|------|-------|-----------------|
| BowTiedDevil/degenbot | 197 | MEV bot, no wallet in README |
| nelso0/barbotine-arbitrage-bot | 155 | Arbitrage bot, no wallet in README |
| mortdeus/solana-copy-sniper-mev-trading-bot | 437 | Solana sniper, no wallet in README |
| hummingbot/hummingbot | 4933 | Major project, needs auth for code search |
| ccxt/ccxt | 8842 | Exchange library, needs auth for code search |

## The gap

GitHub API requires authentication for code search. Without auth, we can't search for wallet addresses inside repos.

## What we need

1. **GitHub token** — to search code for wallet addresses
2. **Or** — manually check fork owners' repos for addresses
3. **Or** — use a different approach (ENS, Farcaster, etc.)

## The smarter approach

Instead of searching for wallets, search for **developers who run trading bots**:

```
1. Find trading bot repos (MEV, arbitrage, sniper)
2. Get list of fork owners
3. For each fork owner:
   - Check their GitHub profile
   - Check their other repos
   - Look for wallet addresses in repos
   - Check if any address is funded
4. If funded → we found a live trader
```

## What to build

A script that:
1. Queries GitHub API for trading bot repos
2. Gets fork owners
3. Searches fork owners' repos for Ethereum addresses
4. Checks balances
5. Creates QP receipt for each finding

## The numbers

- Top trading bot repos: ~50
- Average forks per repo: ~100
- Total fork owners to check: ~5,000
- Percentage with wallet in repos: ~5-10%
- Percentage of those with funded wallets: ~10-20%
- **Estimated hit rate: 25-100 funded wallets with GitHub identity**
