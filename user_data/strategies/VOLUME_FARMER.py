import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from freqtrade.strategy import (BooleanParameter, CategoricalParameter, DecimalParameter,
                                IStrategy, IntParameter, stoploss_from_absolute, informative, Order)
from freqtrade.optimize.space import Categorical, Dimension, Integer, SKDecimal
from freqtrade.persistence import Trade
from freqtrade.configuration import Configuration
from hyperliquid.info import Info
from hyperliquid.utils import constants
from collections import deque
from dataclasses import dataclass
from pathlib import Path
import logging
import warnings
import csv
import os
import sys

warnings.filterwarnings(
    'ignore', message='The objective has been evaluated at this point before.')
warnings.simplefilter(action="ignore", category=pd.errors.PerformanceWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

logger = logging.getLogger(__name__)

GLOBAL_private_key = None
GLOBAL_address = None

import os
import csv
from datetime import datetime, timedelta
from pathlib import Path

def write_log(message, max_lines=45):
    """
    Writes a log message to the log file volume_spammer.log.
    Maintains a maximum number of lines by removing older entries.
    
    Args:
        message (str): The log message to write.
        max_lines (int): Maximum number of lines to keep in the log file (default: 45).
    """
    here = Path(__file__).resolve().parent
    filename = here / "volume_spammer.log"

    # Trim log file if it exceeds max_lines
    if filename.exists():
        with open(filename, "r") as file:
            lines = file.readlines()
        
        # If we have more than max_lines, keep only the most recent ones
        if len(lines) > max_lines - 1:  # -1 to make room for the new line
            lines_to_keep = lines[-(max_lines - 1):]
            with open(filename, "w") as file:
                file.writelines(lines_to_keep)

    # Add the new log entry
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(filename, "a") as file:
        file.write(f"[{timestamp}] {message}\n")

def try_to_create_sub_account_and_give_total_traded_volume(): # this is the way to check if volune reached 100_000
    import re
    from hyperliquid.exchange import Exchange
    from hyperliquid.info import Info
    from hyperliquid.utils import constants
    import eth_account
    from eth_account.signers.local import LocalAccount
    import math
    global GLOBAL_private_key
    global GLOBAL_address

    def extract_traded_amount(response_data, verbose=True):
        """
        Extracts the traded amount from a response message if both traded and required amounts are present.
        Returns the traded amount as a float, or None if not found or if 'required' is missing.

        Parameters:
            response_data (dict): The dictionary containing a 'response' key.
            verbose (bool): Whether to print diagnostic messages.

        Returns:
            float or None: The traded amount, or None if not found or required amount missing.
        """

        if not isinstance(response_data, dict):
            if verbose:
                write_log("Input is not a dictionary.")
            return None

        response_text = response_data.get('response', '')
        if not isinstance(response_text, str):
            if verbose:
                write_log("Response is missing or not a string.")
            return None

        # Flexible regex patterns
        required_match = re.search(
            r'required\s*[:\-]?\s*\$?([\d,]+(?:\.\d{1,2})?)',
            response_text,
            re.IGNORECASE
        )
        traded_match = re.search(
            r'traded\s*[:\-]?\s*\$?([\d,]+(?:\.\d{1,2})?)',
            response_text,
            re.IGNORECASE
        )

        if not required_match:
            if verbose:
                write_log("Required amount not found in response.")
        else:
            if verbose:
                write_log(f"Required amount found: {required_match.group(1)}")

        if not traded_match:
            if verbose:
                write_log("Traded amount not found in response.")
        else:
            if verbose:
                write_log(f"Traded amount found: {traded_match.group(1)}")

        if traded_match and required_match:
            traded_amount = float(traded_match.group(1).replace(',', ''))
            return traded_amount

        return None

    if GLOBAL_private_key is None or GLOBAL_address is None:
        config = Configuration.from_files(["user_data/config.json"])
        ex = config.get("exchange", {})
        address = ex.get("walletAddress")
        private_key = ex.get("privateKey")
    else:
        address = GLOBAL_address 
        private_key = GLOBAL_private_key    

    # Initialize exchange
    account: LocalAccount = eth_account.Account.from_key(private_key)
    exchange = Exchange(account, constants.MAINNET_API_URL, account_address=address)

    name = "test"
    data = exchange.create_sub_account(name)

    return extract_traded_amount(data)

class VOLUME_FARMER(IStrategy):
    minimal_roi = {
        "0": 5000.0,
    }
    stoploss = -0.90
    timeframe = '15m'
    startup_candle_count: int = 0 
    can_short: bool = False
    process_only_new_candles: bool = False

    LEVERAGE_val = 5

    # state variables, do not touch
    is_working = True
    total_vol = 0

    # Optional order type mapping.
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'limit',
        'stoploss_on_exchange': False
    }

    # Optional order time in force.
    order_time_in_force = { 
        'entry': 'gtc',
        'exit': 'gtc'
    }

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        self.total_vol = try_to_create_sub_account_and_give_total_traded_volume()

        # Handle None/error cases first
        if self.total_vol is None:
            self.is_working = False
            dataframe['signal'] = 0
            write_log("API call failed - bot paused (possibilities: API is down, or 100k volume is reached)")
            return dataframe
        
        # Valid volume received
        write_log(f"Total traded volume: {self.total_vol} USDC")
        
        # Check if volume exceeds threshold
        if self.total_vol > 100_000:
            self.is_working = False
            dataframe['signal'] = 0
            write_log("Total traded volume is above 100,000 USDC: bot stopping.")
        else:
            self.is_working = True
            dataframe['signal'] = 1
            write_log(f"Total traded volume is below 100,000 USDC: continuing on {metadata['pair']}... leverage = {self.LEVERAGE_val}")
        
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[dataframe['signal'] == 1, 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[dataframe['signal'] == 0, 'exit_long'] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs):
        # have directly exit order
        return "always_exit"

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: float | None, max_stake: float,
                            leverage: float, entry_tag: str | None, side: str,
                            **kwargs) -> float:
        # max_stake and self.GET_AVAILABLE_PERP() give the same thing: amount available for trade in the hyperliquid perp account
        # self.wallets.get_total_stake_amount() gives the "available_capital" in the config.json
        if self.total_vol > 95_000:
            self.LEVERAGE_val = 2
        dust_USDC = 0.51
        returned_val = max_stake-dust_USDC
        write_log(f"Opening Long with real stake : {returned_val*self.LEVERAGE_val:.2f} USDC (leverage {self.LEVERAGE_val})")
        return returned_val   
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: str | None, side: str,
                 **kwargs) -> float:
        lev = min(self.LEVERAGE_val, max_leverage)

        return lev

