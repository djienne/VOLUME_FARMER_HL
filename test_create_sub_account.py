def try_to_create_sub_account(): # this is the way to check if volune reached 100_000
    import re
    from hyperliquid.exchange import Exchange
    from hyperliquid.info import Info
    from hyperliquid.utils import constants
    import eth_account
    from eth_account.signers.local import LocalAccount
    import math

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
                print("Input is not a dictionary.")
            return None

        response_text = response_data.get('response', '')
        if not isinstance(response_text, str):
            if verbose:
                print("Response is missing or not a string.")
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
                print("Required amount not found in response.")
        else:
            if verbose:
                print(f"Required amount found: {required_match.group(1)}")

        if not traded_match:
            if verbose:
                print("Traded amount not found in response.")
        else:
            if verbose:
                print(f"Traded amount found: {traded_match.group(1)}")

        if traded_match and required_match:
            traded_amount = float(traded_match.group(1).replace(',', ''))
            return traded_amount

        return None

    # config = Configuration.from_files(["user_data/config.json", "user_data/config-private.json"])
    # ex = config.get("exchange", {})
    #address = ex.get("walletAddress")
    #private_key    = ex.get("privateKeyEthWallet")

    address = ""
    private_key = ""

    # Initialize exchange
    account: LocalAccount = eth_account.Account.from_key(private_key)
    exchange = Exchange(account, constants.MAINNET_API_URL, account_address=address)

    name = "test"
    data = exchange.create_sub_account(name)

    return extract_traded_amount(data)


print(try_to_create_sub_account())