from decimal import Decimal

import pytest

from defyes import Honeyswap
from defyes.constants import Chain, GnosisTokenAddr
from defyes.node import get_node

TEST_BLOCK = 27450341
TEST_WALLET = "0x458cd345b4c05e8df39d0a07220feb4ec19f5e6f"
WEB3 = get_node(blockchain=Chain.GNOSIS, block=TEST_BLOCK)

UNIv2 = "0x28dbd35fd79f48bfa9444d330d14683e7101d817"


def test_get_lptoken_data():
    data = Honeyswap.get_lptoken_data(UNIv2, TEST_BLOCK, Chain.GNOSIS, WEB3)
    expected = {
        "decimals": 18,
        "totalSupply": 2780438593422870570963,
        "token0": GnosisTokenAddr.WETH,
        "token1": GnosisTokenAddr.GNO,
        "reserves": [697389190335766422886, 11931109898533386964234, 1681509230],
        "kLast": 8320457320306632575150389158633998324068504,
        "virtualTotalSupply": Decimal("2780443320502662251210.953287"),
    }
    assert expected == {k: data[k] for k in expected}


@pytest.mark.parametrize("decimals", [True, False])
def test_underlying(decimals):
    x = Honeyswap.underlying(TEST_WALLET, UNIv2, TEST_BLOCK, Chain.GNOSIS, WEB3, decimals=decimals)
    assert x == [
        [GnosisTokenAddr.WETH, Decimal("697386974825513061735.0076492") / (10**18 if decimals else 1)],
        [GnosisTokenAddr.GNO, Decimal("11931071995026019072977.21406") / (10**18 if decimals else 1)],
    ]


@pytest.mark.parametrize("decimals", [True, False])
def test_pool_balances(decimals):
    x = Honeyswap.pool_balances(UNIv2, TEST_BLOCK, Chain.GNOSIS, WEB3, decimals=decimals)
    assert x == [
        [GnosisTokenAddr.WETH, Decimal("697389190335766422886") / (10**18 if decimals else 1)],
        [GnosisTokenAddr.GNO, Decimal("11931109898533386964234") / (10**18 if decimals else 1)],
    ]


@pytest.mark.parametrize("decimals", [True, False])
def test_swap_fees(decimals):
    x = Honeyswap.swap_fees(UNIv2, TEST_BLOCK - 1000, TEST_BLOCK, Chain.GNOSIS, WEB3, decimals=decimals)
    assert x["swaps"] == [
        {
            "block": 27449397,
            "token": GnosisTokenAddr.GNO,
            "amount": Decimal("18914160864473196") / Decimal(10**18 if decimals else 1),
        },
        {
            "block": 27450198,
            "token": GnosisTokenAddr.GNO,
            "amount": Decimal("2825275064344436") / (10**18 if decimals else 1),
        },
    ]
