# VOLUME_FARMER – Freqtrade Strategy for Volume Farming on Hyperliquid 

> ⚠️ **BIG WARNING:** This bot **will lose money** (fees/slippage) and **is NOT intended to make profits**. It is solely to **farm trading volume**. Use at your own risk. *Not financial advice.*

Youtube video link presenting this Freqtrade strategy: [https://youtu.be/6wrR-6Wp9JE?si=Rfr0K1GkEX-BI0kk](https://youtu.be/6wrR-6Wp9JE?si=Rfr0K1GkEX-BI0kk)

## What it does
Automates volume farming on Hyperliquid to reach **100,000 USDC traded volume**. Once the target is reached (or the API check fails), the bot **halts automatically**.

## Why it matters
🎯 **WHY IS THIS IMPORTANT?**  
✅ Unlocks sub-accounts on Hyperliquid  

✅ Grants “Institutional” status on Liminal for an easy to use Delta Neutral strategy (positions executed directly on your sub-account), profitability ~5-40% APR

✅ Increases your chances for a future Hyperliquid airdrop and potentially other ecosystem projects  

**💰 Support this project**:
- 💰 **Hyperliquid**: Sign up with [this referral link](https://app.hyperliquid.xyz/join/FREQTRADE) for 10% fee reduction
- 🌊 **Liminal**: Liminal, to run a Delta-Neutral strategy easily (5-40% APR), [referral link](https://liminal.money/join/FREQTRADE)

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
# Copy/paste both API keys inside config.json.

# Build & run
docker compose build
docker compose up
```

## Notes
- **Limit orders @ order book top** to stay maker and get filled fast.
- Single-position logic; try to maker exit immediately after entries to churn volume.
- Monitor progress on Hyperliquid portfolio and `volume_spammer.log`.
- Use **short-lived Private Hyperliquid API key** (few days) for safety.

