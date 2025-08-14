# VOLUME_FARMER – Freqtrade Strategy for Hyperliquid Volume Farming

> ⚠️ **BIG WARNING:** This bot **will lose money** (fees/slippage) and **is NOT intended to make profits**. It is solely to **farm trading volume**. Use at your own risk. *Not financial advice.*

Youtube video link presenting this Freqtrade strategy: [to be provided soon].

## What it does
Automates volume farming on Hyperliquid to reach **100,000 USDC traded volume**. Once the target is reached (or the API check fails), the bot **halts automatically**.

## Why it matters
🎯 **WHY IS THIS IMPORTANT?**  
✅ Unlocks sub-accounts on Hyperliquid  

✅ Grants “Institutional” status on Liminal for an easy to use Delta Neutral strategy (positions executed on your account), profitability ~5-40% APR

✅ Increases your chances for a future Hyperliquid airdrop and potentially other ecosystem projects  

## How it works (very short)
- Trades **PAXG/USDC Perp** with **limit orders only** (maker fees).
- Uses **5x leverage**, then **2x** when total volume ≥ **95k** to avoid overshooting.
- Periodically calls Hyperliquid API (via a dummy sub-account create call) to **read total traded volume**.
- Logs actions to `volume_spammer.log` (keeps ~45 lines).

## Requirements
- Hyperliquid account funded (works from ≈ **100 USDC** ; expect ~**20–40 USDC** costs to hit 100k volume, no matter what is your initial capital).
- Docker installed.
- `walletAddress` (Address of your EVM Wallet) and `privateKey` (generated in Hyperliquid More->API) configured in `user_data/config.json`.

## Quick start
```bash
# Clone repo / place strategy
# Put API keys. Youtube video link to be provided soon.

# Build & run
docker compose build
docker compose up
```

## Notes
- **Limit orders @ order book top** to stay maker.
- Single-position logic; try to maker exit immediately after entries to churn volume.
- Monitor progress on Hyperliquid portfolio and `volume_spammer.log`.
- Use **short-lived API keys** (few days) for safety.

