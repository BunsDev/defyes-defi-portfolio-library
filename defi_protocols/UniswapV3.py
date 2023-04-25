import logging
from decimal import Decimal
from enum import IntEnum
from typing import Union, ClassVar
from dataclasses import dataclass, field

from defi_protocols.functions import get_node, get_contract, get_decimals


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# UNISWAP V3 FACTORY
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
FACTORY: str = '0x1F98431c8aD98523631AE4a59f267346ea31F984'

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# UNISWAP V3 POSITIONS NFT
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
POSITIONS_NFT: str = '0xC36442b4a4522E871399CD717aBDD847Ab11FE88'

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# UNISWAP V3 ROUTER 2
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
UNISWAPV3_ROUTER2: str = '0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45'

# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# UNISWAP V3 QUOTER
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
UNISWAPV3_QUOTER: str = "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6"


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# FEES
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Possible Fees for Uniwsap v3 Pools
# https://docs.uniswap.org/sdk/v3/reference/enums/FeeAmount
class FeeAmount(IntEnum):
    LOWEST = 100
    LOW = 500
    MEDIUM = 3000
    HIGH = 10000


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# ABIs
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# Uniswap v3 Factory ABI - getPool
ABI_FACTORY: str = '[{"inputs":[{"internalType":"address","name":"","type":"address"},{"internalType":"address","name":"","type":"address"},{"internalType":"uint24","name":"","type":"uint24"}],"name":"getPool","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"owner","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}]'

# Uniswap v3 Pools ABI - slot0, token0, token1
ABI_POOL: str = '[{"inputs":[],"name":"slot0","outputs":[{"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"},{"internalType":"int24","name":"tick","type":"int24"},{"internalType":"uint16","name":"observationIndex","type":"uint16"},{"internalType":"uint16","name":"observationCardinality","type":"uint16"},{"internalType":"uint16","name":"observationCardinalityNext","type":"uint16"},{"internalType":"uint8","name":"feeProtocol","type":"uint8"},{"internalType":"bool","name":"unlocked","type":"bool"}],"stateMutability":"view","type":"function"}, \
            {"inputs":[],"name":"token0","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},\
            {"inputs":[],"name":"token1","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}, \
            {"inputs":[],"name":"feeGrowthGlobal0X128","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},\
            {"inputs":[],"name":"feeGrowthGlobal1X128","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}, \
            {"inputs":[{"internalType":"int24","name":"","type":"int24"}],"name":"ticks","outputs":[{"internalType":"uint128","name":"liquidityGross","type":"uint128"},{"internalType":"int128","name":"liquidityNet","type":"int128"},{"internalType":"uint256","name":"feeGrowthOutside0X128","type":"uint256"},{"internalType":"uint256","name":"feeGrowthOutside1X128","type":"uint256"},{"internalType":"int56","name":"tickCumulativeOutside","type":"int56"},{"internalType":"uint160","name":"secondsPerLiquidityOutsideX128","type":"uint160"},{"internalType":"uint32","name":"secondsOutside","type":"uint32"},{"internalType":"bool","name":"initialized","type":"bool"}],"stateMutability":"view","type":"function"}]'

# Uniswap v3 NFT manager - balanceOf, tokenofownerbyindex, positions, ownerof
ABI_POSITIONS_NFT: str = '[{"inputs":[{"internalType":"address","name":"owner","type":"address"}],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"owner","type":"address"},{"internalType":"uint256","name":"index","type":"uint256"}],"name":"tokenOfOwnerByIndex","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"positions","outputs":[{"internalType":"uint96","name":"nonce","type":"uint96"},{"internalType":"address","name":"operator","type":"address"},{"internalType":"address","name":"token0","type":"address"},{"internalType":"address","name":"token1","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"int24","name":"tickLower","type":"int24"},{"internalType":"int24","name":"tickUpper","type":"int24"},{"internalType":"uint128","name":"liquidity","type":"uint128"},{"internalType":"uint256","name":"feeGrowthInside0LastX128","type":"uint256"},{"internalType":"uint256","name":"feeGrowthInside1LastX128","type":"uint256"},{"internalType":"uint128","name":"tokensOwed0","type":"uint128"},{"internalType":"uint128","name":"tokensOwed1","type":"uint128"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"uint256","name":"tokenId","type":"uint256"}],"name":"ownerOf","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"}]'

# Uniswap v3 Quoter ABI
ABI_QUOTER_V3: str = '[{"inputs":[{"internalType":"address","name":"tokenIn","type":"address"},{"internalType":"address","name":"tokenOut","type":"address"},{"internalType":"uint24","name":"fee","type":"uint24"},{"internalType":"uint256","name":"amountIn","type":"uint256"},{"internalType":"uint160","name":"sqrtPriceLimitX96","type":"uint160"}],"name":"quoteExactInputSingle","outputs":[{"internalType":"uint256","name":"amountOut","type":"uint256"}],"stateMutability":"nonpayable","type":"function"}]'


class NFTOwnerError(Exception):
    logger.warning('Wallet is not owner of this NFT')


@dataclass
class PositionNFT:
    # Based on Uniswap V3 whitepaper:
    # https://uniswap.org/whitepaper-v3.pdf
    # Glossary:
    # token0
    # token1
    # fee
    # Lower tick: il
    # Upper tick iu
    # Current tick: ic
    # feeGrowthInside0LastX128: fr0
    # feeGrowthInside1LastX128: fr1
    # feeGrowthGlobal0: fg0
    # feeGrowthGlobal1: fg1
    # feeGrowthOutside0X128low: fo0l
    # feeGrowthOutside1X128low: fo1l
    # feeGrowthOutside0X128up: fo0u
    # feeGrowthOutside1X128up: fo0l
    # seconds spent above: sa
    # seconds spent below: sb
    # fees earned per unit of liquidity in token 0: fa
    # fees earned per unit of liquidity in token 1: fb
    BASETICK: ClassVar[int] = 1.0001

    wallet: str
    nftid: int
    blockchain: str
    block: Union[int|str]
    web3: object
    decimals: bool
    token0: str = field(init=False)
    token1: str = field(init=False)
    il: int = field(init=False)
    iu: int = field(init=False)
    fr0: int = field(init=False)
    fr1: int = field(init=False)
    liquidity: Decimal = field(init=False)
    decimals0: int = field(init=False)
    decimals1: int = field(init=False)

    def __post_init__(self):
        nft_contract = get_contract(POSITIONS_NFT, self.blockchain, web3=self.web3, abi=ABI_POSITIONS_NFT, block=self.block)
        nft_owner = nft_contract.functions.ownerOf(self.nftid).call(block_identifier=self.block)
        if nft_owner != self.wallet:
            raise NFTOwnerError(f"{self.nftid=} does not belong to {self.wallet}")

        self.token0, self.token1, self.fee, self.il, self.iu, liquidity, self.fr0, self.fr1 = nft_contract.functions.positions(self.nftid).call(block_identifier=self.block)[2:10]
        self.liquidity = Decimal(liquidity)
        if self.decimals:
            self.decimals0 = get_decimals(self.token0, self.blockchain, self.web3)
            self.decimals1 = get_decimals(self.token1, self.blockchain, self.web3)

    def get_fees(self, ic, fg0, fg1, fo0low, fo1low, fo0up, fo1up):
        if ic >= self.il:
            fee_lower_token0 = fo0low
            fee_lower_token1 = fo1low
        else:
            fee_lower_token0 = fg0 - fo0low
            fee_lower_token1 = fg1 - fo1low
        if ic >= self.iu:
            fee_upper_token0 = fg0 - fo0up
            fee_upper_token1 = fg1 - fo1up
        else:
            fee_upper_token0 = fo0up
            fee_upper_token1 = fo1up

        fa = int(Decimal((fg0 - fee_lower_token0 - fee_upper_token0 - self.fr0) * self.liquidity) / Decimal(2 ** 128))
        fb = int(Decimal((fg1 - fee_lower_token1 - fee_upper_token1 - self.fr1) * self.liquidity) / Decimal(2 ** 128))

        return fa, fb

    def get_balance(self, ic, current_square_price, fees):
        balances = []
        if self.liquidity != 0:
            if not fees:
                fa, fb = [0, 0]
            else:
                fa, fb = fees

            sa = Decimal(self.BASETICK) ** Decimal(int(self.il) / 2)
            sb = Decimal(self.BASETICK) ** Decimal(int(self.iu) / 2)

            if self.iu <= ic:
                amount0 = 0
                amount0fee = fa if fa > 0 else 0
                amount1 = self.liquidity * (sb - sa)
                amount1fee = fb
            elif self.il < ic < self.iu:
                amount0 = self.liquidity * (sb - current_square_price) / (current_square_price * sb)
                amount0fee = fa
                amount1 = self.liquidity * (current_square_price - sa)
                amount1fee = fb
            else:
                amount0 = self.liquidity * (sb - sa) / (sa * sb)
                amount0fee = fa
                amount1 = 0
                amount1fee = fb if fb > 0 else 0

            amount0 = Decimal(amount0) + Decimal(amount0fee)
            amount1 = Decimal(amount1) + Decimal(amount1fee)

            if self.decimals:
                amount0 = float(amount0 / Decimal(10 ** self.decimals0))
                amount1 = float(amount1 / Decimal(10 ** self.decimals1))
            else:
                amount0 = int(amount0)
                amount1 = int(amount1)

            if amount0 > 0:
                balances.append([self.token0, amount0])

            if amount1 > 0:
                balances.append([self.token1, amount1])
        return balances


def underlying(wallet: str, nftid: int, block: Union[int, str], blockchain: str, web3=None, decimals: bool = True, fee: bool = False) -> list:
    """Returns the balances of the underlying assets corresponding to a position held by a wallet.
    Parameters
    ----------
    wallet : str
        address of the wallet holding the position
    nftid : int
        address of the token identifying the position in the protocol
    block : int or 'latest'
        block number at which the data is queried
    blockchain : str
        blockchain in which the position is held
    web3: obj
        optional, already instantiated web3 object
    decimals: bool
        specifies whether balances are returned as int if set to False, or float with the appropriate decimals if set
        to True
    fee: bool
        ¿f set to True, the balances of the unclaimed fees corresponding to the position are appended to the returned
        list

    Returns
    ----------
    list
        a list where each element is a list with two elements, the underlying token address and its corresponding amount
    """
    if web3 is None:
        web3 = get_node(blockchain, block=block)

    wallet = web3.to_checksum_address(wallet)
    try:
        position_nft = PositionNFT(wallet, nftid, blockchain, block, web3, decimals)
    except NFTOwnerError:
        return []

    factory_address = get_contract(FACTORY, blockchain, web3=web3, abi=ABI_FACTORY, block=block)
    pool_address = factory_address.functions.getPool(position_nft.token0, position_nft.token1, position_nft.fee).call(block_identifier=block)
    pool_contract = get_contract(pool_address, blockchain, web3=web3, abi=ABI_POOL, block=block)

    current_tick = pool_contract.functions.slot0().call(block_identifier=block)[1]
    sqrt_price_x96 = pool_contract.functions.slot0().call(block_identifier=block)[0]
    current_square_price = Decimal(sqrt_price_x96) / Decimal(2 ** 96)

    feeGrowthGlobal0 = pool_contract.functions.feeGrowthGlobal0X128().call(block_identifier=block)
    feeGrowthGlobal1 = pool_contract.functions.feeGrowthGlobal1X128().call(block_identifier=block)
    feeGrowthOutside0X128low, feeGrowthOutside1X128low = pool_contract.functions.ticks(position_nft.il).call(block_identifier=block)[2:4]
    feeGrowthOutside0X128up, feeGrowthOutside1X128up = pool_contract.functions.ticks(position_nft.iu).call(block_identifier=block)[2:4]

    fees = None
    if fee:
        fees = position_nft.get_fees(current_tick,
                                     feeGrowthGlobal0,
                                     feeGrowthGlobal1,
                                     feeGrowthOutside0X128low,
                                     feeGrowthOutside1X128low,
                                     feeGrowthOutside0X128up,
                                     feeGrowthOutside1X128up)

    balances = position_nft.get_balance(current_tick, current_square_price, fees)

    return balances


def get_rate_uniswap_v3(token_src: str, token_dst: str, block: Union[int, str], blockchain: str, web3=None, fee: int = FeeAmount.LOWEST) -> float:
    """Returns the price of a token .
    Parameters
    ----------
    token_src : str
        address of the source token of the pool
    token_dst : str
        address of the destination token of the pool
    block : int or 'latest'
        block number at which the data is queried
    blockchain : str
        blockchain in which the position is held
    web3: obj
        optional, already instantiated web3 object
    fee: int
        fee which is set for this pool

    Returns
    ----------
    float
        the token price of the source token (token_src) quoted in destination token
    """
    if web3 is None:
        web3 = get_node(blockchain, block=block)

    token_src = web3.to_checksum_address(token_src)
    token_dst = web3.to_checksum_address(token_dst)

    factory_contract = get_contract(FACTORY, blockchain, web3=web3, abi=ABI_FACTORY, block=block)
    pool_address = factory_contract.functions.getPool(token_src, token_dst, fee).call(block_identifier=block)
    pool_contract = get_contract(pool_address, blockchain, web3=web3, abi=ABI_POOL, block=block)

    sqrt_price_x96 = pool_contract.functions.slot0().call(block_identifier=block)[0]
    current_price = (Decimal(sqrt_price_x96) / Decimal(2 ** 96)) ** 2

    token0 = pool_contract.functions.token0().call(block_identifier=block)

    token_src_decimals = get_decimals(token_src, blockchain, web3=web3)
    token_dst_decimals = get_decimals(token_dst, blockchain, web3=web3)

    if token_src == token0:
        factor = current_price
    else:
        factor = 1 / current_price

    return float(factor / Decimal(10 ** (token_dst_decimals - token_src_decimals)))


def allnfts(wallet: str, block: Union[int, str], blockchain: str, web3=None) -> list:
    """Returns all nft ids owned by a wallet.
    Parameters
    ----------
    wallet : str
        address of the wallet holding the position
    block : int or 'latest'
        block number at which the data is queried
    blockchain : str
        blockchain in which the position is held
    web3: obj
        optional, already instantiated web3 object

    Returns
    ----------
    list
        a list where each element is the nft id that is owned by the wallet (open and closed nfts)
    """
    nftids = []

    if web3 is None:
        web3 = get_node(blockchain, block=block)

    nft_contract = get_contract(POSITIONS_NFT, blockchain, web3=web3, abi=ABI_POSITIONS_NFT, block=block)
    nfts = nft_contract.functions.balanceOf(wallet).call(block_identifier=block)
    for nft_index in range(nfts):
        nft_id = nft_contract.functions.tokenOfOwnerByIndex(wallet, nft_index).call(block_identifier=block)
        nftids.append(nft_id)
    return nftids


def underlying_all(wallet: str, block: Union[int, str], blockchain: str, decimals: bool = True, fee: bool = False):
    """Returns the balances of the underlying assets corresponding to all positions held by a wallet.
    Parameters
    ----------
    wallet : str
        address of the wallet holding the position
    block : int or 'latest'
        block number at which the data is queried
    blockchain : str
        blockchain in which the position is held
    decimals: bool
        specifies whether balances are returned as int if set to False, or float with the appropriate decimals if set
        to True
    fee: bool

    Returns
    ----------
    list
        a list where each element is a list with two elements, the underlying token address and its corresponding amount
        (with optional unclaimed fee)
    """

    balances = []
    for nft in allnfts(wallet, block, blockchain):
        balances.append(underlying(wallet, nft, block, blockchain, decimals=decimals, fee=fee))
    return list(filter(None, balances))
