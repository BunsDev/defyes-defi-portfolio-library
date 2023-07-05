from time import sleep

import requests
from web3 import Web3

from defi_protocols.constants import (
    API_ETHERSCAN_GETTOKENINFO,
    API_KEY_ETHERSCAN,
    ETHEREUM,
    MAX_EXECUTIONS,
    ZERO_ADDRESS,
)
from defi_protocols.functions import GetNodeIndexError, block_to_timestamp, get_node, timestamp_to_block
from defi_protocols.prices import Chainlink, CoinGecko, Zapper, _1inch

ONEINCH_CONNECTOR_DICT = {
    "0x6aC78efae880282396a335CA2F79863A1e6831D4": "0x9C58BAcC331c9aa871AFD802DB6379a98e80CEdb",
    "0xA4eF9Da5BA71Cc0D2e5E877a910A37eC43420445": "0x9C58BAcC331c9aa871AFD802DB6379a98e80CEdb",
    "0x532801ED6f82FFfD2DAB70A19fC2d7B2772C4f4b": "0x9C58BAcC331c9aa871AFD802DB6379a98e80CEdb",
    "0x4f4F9b8D5B4d0Dc10506e5551B0513B61fD59e75": "0x9C58BAcC331c9aa871AFD802DB6379a98e80CEdb",
    "0x177127622c4A00F3d409B75571e12cB3c8973d3c": "0x9C58BAcC331c9aa871AFD802DB6379a98e80CEdb",
    "0x6cAcDB97e3fC8136805a9E7c342d866ab77D0957": "0x9C58BAcC331c9aa871AFD802DB6379a98e80CEdb",
    "0xf6537FE0df7F0Cc0985Cf00792CC98249E73EFa0": "0x9C58BAcC331c9aa871AFD802DB6379a98e80CEdb",
    "0xDEf1CA1fb7FBcDC777520aa7f396b4E015F497aB": "0x9C58BAcC331c9aa871AFD802DB6379a98e80CEdb",
}

SOURCES_LIST = ["chainlink", "1inch", "coingecko"]


def get_price(token_address, block, blockchain, web3=None, source: str = "chainlink"):
    # Checks
    assert source in SOURCES_LIST, 'Please input an existing oracle.'

    if web3 is None:
        web3 = get_node(blockchain, block=block)

    token_address = Web3.to_checksum_address(token_address)

    # Get price directly from Chainlink in case of native token.
    if token_address == ZERO_ADDRESS:
        return Chainlink.get_native_token_price(web3, block, blockchain), "chainlink", blockchain

    # As chainlink is just for eth, we switch to 1inch in case of xdai and other blockchains.
    if blockchain != ETHEREUM and source == "chainlink":
        source = "1inch"

    price = _get_price_from_source(source, token_address, block, blockchain)

    # Created this flag to avoid returning None.
    flag_zero = False

    # Go to the next source in case price is None or 0.
    while price is None or price == 0:
        if price == 0:
            flag_zero = True
        try:
            source = SOURCES_LIST[SOURCES_LIST.index(source) + 1]
            price = _get_price_from_source(source, token_address, block, blockchain)
            print(source, price, type(0.0))
        except IndexError:
            if flag_zero:
                price = 0.0
            return (price, source, blockchain)

    return (price, source, blockchain)


def _get_price_from_source(source: str, token_address: str, block: int, blockchain: str):
    """Get the price from the selected source.
    Used by the get_price function, it helps with the logic of choosing the source.

    Returns:
        float: price.
    """
    if source == "chainlink":
        try:
            price = Chainlink.get_mainnet_price(token_address, block)
        except Exception:
            price = None

    elif source == "1inch":
        connector = ONEINCH_CONNECTOR_DICT.get(token_address, None)
        try:
            price = _1inch.get_price(token_address, block, blockchain, connector=connector)
        except Exception:
            price = None

    elif source == 'coingecko':
        price = CoinGecko.get_price(token_address, block, blockchain)

        # In case there is the error for too many requests
        while price[0] == 429:
            sleep(1)
            price = CoinGecko.get_price(token_address, block, blockchain)

        price = price[1][1]

    return price


def get_etherscan_price(token_address):
    """Get token price from etherscan.

    Args:
        token_address (str).

    Returns:
        float, str, str: price, source(etherscan), blockchain
    """
    price = requests.get(API_ETHERSCAN_GETTOKENINFO % (token_address, API_KEY_ETHERSCAN)).json()["result"][0][
        "tokenPriceUSD"
    ]

    return price, "etherscan", ETHEREUM


if __name__ == "__main__":
    # print(Chainlink.get_mainnet_price('0x4da27a545c0c5B758a6BA100e3a049001de870f5', 17628203))
    # print(_1inch.get_price('0x4da27a545c0c5B758a6BA100e3a049001de870f5', 17628203, 'ethereum'))
    # print(CoinGecko.get_price('0xae7ab96520de3a18e5e111b5eaab095312d7fe84', 17628203, 'ethereum'))
    # print(
    #     Zapper.get_price(
    #         '0x4da27a545c0c5B758a6BA100e3a049001de870f5',
    #         block_to_timestamp(17628203, 'ethereum'),
    #         'ethereum',
    #     )
    # )
    print(get_price('0xBFAbdE619ed5C4311811cF422562709710DB587d', 17628203, 'ethereum'))
