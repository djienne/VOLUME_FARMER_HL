import logging
import logging.handlers
import re
import time
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd
from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

warnings.filterwarnings(
    'ignore', message='The objective has been evaluated at this point before.')
warnings.simplefilter(action="ignore", category=pd.errors.PerformanceWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

logger = logging.getLogger(__name__)

# Sentinel distinct from None: lets callers tell "transient API error" apart from
# "response parsed but no volume found" (the real halt signal).
_API_ERROR = object()

_LOG_PATH = Path(__file__).resolve().parent / "volume_spammer.log"
# ~45 lines of ~100 chars each -> ~4.5 KB cap; one backup keeps ~90 lines available.
_volume_logger = logging.getLogger("volume_spammer")
_volume_logger.setLevel(logging.INFO)
_volume_logger.propagate = False
if not _volume_logger.handlers:
    _handler = logging.handlers.RotatingFileHandler(
        _LOG_PATH, maxBytes=4500, backupCount=1, encoding="utf-8"
    )
    _handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
    _volume_logger.addHandler(_handler)


def write_log(message: str) -> None:
    _volume_logger.info(message)


def _extract_traded_amount(response_data):
    """
    Extracts the traded-volume amount from a Hyperliquid sub-account-creation error
    payload. Returns float on success, None when the response is shaped like a dict
    but no 'traded' figure was present.
    """
    if not isinstance(response_data, dict):
        write_log("API response is not a dict.")
        return None

    response_text = response_data.get('response', '')
    if not isinstance(response_text, str):
        write_log("API response field is missing or not a string.")
        return None

    traded_match = re.search(
        r'traded\s*[:\-]?\s*\$?([\d,]+(?:\.\d{1,2})?)',
        response_text,
        re.IGNORECASE,
    )
    required_match = re.search(
        r'required\s*[:\-]?\s*\$?([\d,]+(?:\.\d{1,2})?)',
        response_text,
        re.IGNORECASE,
    )

    if traded_match:
        if required_match:
            write_log(
                f"Parsed traded={traded_match.group(1)} required={required_match.group(1)}"
            )
        else:
            write_log(
                f"Parsed traded={traded_match.group(1)} (no 'required' field in response)"
            )
        return float(traded_match.group(1).replace(',', ''))

    write_log(f"No 'traded' value in response. Raw (truncated): {response_text[:500]!r}")
    return None


def _fetch_total_traded_volume():
    """
    Calls Hyperliquid's create_sub_account endpoint. When volume < 100k the call
    fails and the error message contains the traded total, which we parse out.
    Retries on transient network/exchange errors and returns _API_ERROR rather
    than None so the caller can distinguish "try again later" from "halt".
    """
    from freqtrade.configuration import Configuration
    from hyperliquid.exchange import Exchange
    from hyperliquid.utils import constants
    import eth_account
    from eth_account.signers.local import LocalAccount

    config = Configuration.from_files([
        "user_data/config.json",
        "user_data/config-private.json",
    ])
    ex = config.get("exchange", {})
    address = ex.get("walletAddress")
    private_key = ex.get("privateKey")

    if not address or not private_key:
        write_log("Missing walletAddress/privateKey in config-private.json.")
        return _API_ERROR

    delays = (1, 3, 9)
    last_err = None
    for attempt, delay in enumerate(delays, start=1):
        try:
            account: LocalAccount = eth_account.Account.from_key(private_key)
            exchange = Exchange(account, constants.MAINNET_API_URL, account_address=address)
            data = exchange.create_sub_account("test")
            return _extract_traded_amount(data)
        except Exception as exc:  # noqa: BLE001 — Hyperliquid SDK raises many types
            last_err = exc
            write_log(f"API error (attempt {attempt}/{len(delays)}): {exc!r}")
            if attempt < len(delays):
                time.sleep(delay)

    write_log(f"API error persisted after {len(delays)} attempts: {last_err!r}")
    return _API_ERROR


class VOLUME_FARMER(IStrategy):
    minimal_roi = {"0": 5000.0}
    stoploss = -0.90
    timeframe = '15m'
    startup_candle_count: int = 0
    can_short: bool = False
    process_only_new_candles: bool = False

    LEVERAGE_val = 5

    # State: last known total volume. None = halt; float = running.
    total_vol = 0

    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'limit',
        'stoploss_on_exchange': False,
    }

    order_time_in_force = {
        'entry': 'gtc',
        'exit': 'gtc',
    }

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        result = _fetch_total_traded_volume()

        if result is _API_ERROR:
            # Transient: don't overwrite last-known total_vol, just skip this cycle.
            dataframe['signal'] = 0
            write_log("Transient API error — skipping this cycle, bot still running.")
            return dataframe

        self.total_vol = result

        if self.total_vol is None:
            dataframe['signal'] = 0
            write_log("Volume not found in response — halting (likely 100k reached).")
            return dataframe

        write_log(f"Total traded volume: {self.total_vol} USDC")

        # Lock in the reduced-leverage regime before the next stake is sized.
        self.LEVERAGE_val = 2 if self.total_vol > 95_000 else 5

        if self.total_vol > 100_000:
            dataframe['signal'] = 0
            write_log("Total traded volume is above 100,000 USDC: bot stopping.")
        else:
            dataframe['signal'] = 1
            write_log(
                f"Below 100k on {metadata['pair']}... leverage = {self.LEVERAGE_val}"
            )

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[dataframe['signal'] == 1, 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[dataframe['signal'] == 0, 'exit_long'] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs):
        return "always_exit"

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: float | None, max_stake: float,
                            leverage: float, entry_tag: str | None, side: str,
                            **kwargs) -> float:
        if self.total_vol is None:
            return 0.0

        dust_USDC = 0.51
        returned_val = max_stake - dust_USDC
        write_log(
            f"Opening Long with real stake: {returned_val * self.LEVERAGE_val:.2f} USDC "
            f"(leverage {self.LEVERAGE_val})"
        )
        return returned_val

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str | None, side: str,
                 **kwargs) -> float:
        return min(self.LEVERAGE_val, max_leverage)
