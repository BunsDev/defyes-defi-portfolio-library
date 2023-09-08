"""
Spark protocol (by default in Ethereum mainnet)

Mainnet Addresses https://docs.sparkprotocol.io/developers/deployed-contracts/mainnet-addresses
"""

from decimal import Decimal, DivisionByZero, InvalidOperation
from functools import cached_property
from typing import Iterator, NamedTuple

from defyes.constants import Chain
from defyes.prices import Chainlink as chainlink
from defyes.types import Addr, Token, TokenAmount

from .autogenerated import Oracle, Pool, PoolAddressesProvider, ProtocolDataProvider


class ReserveTokens(NamedTuple):
    sp: Token
    stable_debt: Token
    variable_debt: Token


class UserReserveData(NamedTuple):
    sp: int
    stable_debt: int
    variable_debt: int
    principal_stable_debt: int
    scaled_variable_debt: int
    stable_borrow_rate: int
    reserve_liquidity_rate: int
    timestamp: int
    is_collateral: bool

    @property
    def underlying(self):
        return self.sp - self.stable_debt - self.variable_debt


class UserAccountData(NamedTuple):
    total_collateral_base: int
    total_debt_base: int
    available_borrows_base: int
    current_liquidation_threshold: int
    ltv: int
    health_factor: int

    @property
    def collateral_ratio(self):
        try:
            return 100 * Decimal(self.total_collateral_base) / self.total_debt_base
        except DivisionByZero:
            return Decimal("infinity")
        except InvalidOperation:
            return Decimal("nan")

    @property
    def liquidation_ratio(self):
        try:
            return 1000000 / Decimal(self.current_liquidation_threshold)
        except DivisionByZero:
            return Decimal("infinity")


class Pool(Pool):
    def user_account_data(self, user: str) -> UserAccountData:
        return UserAccountData(*self.get_user_account_data(user))


class PoolAddressesProvider(PoolAddressesProvider):
    default_addresses: dict[str, str] = {
        Chain.ETHEREUM: Addr("0x02C3eA4e34C0cBd694D2adFa2c690EECbC1793eE"),
    }

    @cached_property
    def pool_contract(self):
        return Pool(self.blockchain, self.block, address=self.get_pool)

    @cached_property
    def price_oracle_contract(self):
        return Oracle(self.blockchain, self.block, address=self.get_price_oracle)


class ProtocolDataProvider(ProtocolDataProvider):
    default_addresses: dict[str, str] = {
        Chain.ETHEREUM: Addr("0xFc21d6d146E6086B8359705C8b28512a983db0cb"),
    }

    @property
    def all_reserves_tokens(self) -> Iterator[tuple[str, Token]]:
        for symbol, addr in self.get_all_reserves_tokens:
            yield symbol, Token.get_instance(addr, self.blockchain)

    def get_reserve_tokens_addresses(self, asset_addr: str) -> ReserveTokens:
        addresses = super().get_reserve_tokens_addresses(asset_addr)
        return ReserveTokens(*(Token.get_instance(addr, self.blockchain) for addr in addresses))

    @property
    def last_block_id(self):
        return self.web3.eth.block_number

    @property
    def block_id(self):
        return self.block if isinstance(self.block, int) else self.last_block_id

    def all_user_reserve_data(self, wallet: Addr) -> Iterator[tuple[Token, UserReserveData]]:
        for _, asset in self.all_reserves_tokens:
            yield asset, UserReserveData(*self.get_user_reserve_data(asset, wallet))

    def underlyings(self, wallet: Addr) -> Iterator[TokenAmount]:
        for asset, user_reserve_data in self.all_user_reserve_data(wallet):
            underlying = user_reserve_data.underlying
            if underlying != 0:
                yield TokenAmount.from_teu(underlying, asset)

    def holdings(self, wallet: Addr) -> Iterator[TokenAmount]:
        for asset, user_reserve_data in self.all_user_reserve_data(wallet):
            tokens = self.get_reserve_tokens_addresses(asset)
            for amount, token in zip(user_reserve_data, tokens):  # sp, stable_debt, variable_debt
                if amount != 0:
                    yield TokenAmount.from_teu(amount, token)


def get_protocol_data(wallet: Addr, block: int | str, blockchain: Chain, decimals: bool = True) -> dict:
    wallet = Addr(wallet)
    pap = PoolAddressesProvider(blockchain, block)
    user_account_data = pap.pool_contract.user_account_data(wallet)
    pdp = ProtocolDataProvider(blockchain, block)

    def as_dict_list(token_amounts):
        return [token_amount.as_dict(decimals) for token_amount in token_amounts]

    return {
        "blockchain": blockchain,
        "block_id": block,
        "protocol": "Spark",
        "version": 0,
        "wallet": wallet,
        "decimals": decimals,
        "positions": {
            "single_position": {
                "underlyings": as_dict_list(pdp.underlyings(wallet)),
                "holdings": as_dict_list(pdp.holdings(wallet)),
            }
        },
        "positions_key": None,
        "finantial_metrics": {
            "collateral_ratio": user_account_data.collateral_ratio,
            "liquidation_ratio": user_account_data.liquidation_ratio,
        },
    }


def get_full_finantial_metrics(wallet: Addr, block: int | str, blockchain: Chain, decimals: bool = True) -> dict:
    wallet = Addr(wallet)
    pap = PoolAddressesProvider(blockchain, block)

    user_account_data = pap.pool_contract.user_account_data(wallet)
    ret = {
        "collateral_ratio": user_account_data.collateral_ratio,
        "liquidation_ratio": user_account_data.liquidation_ratio,
        "native_token_price_usd": chainlink.get_native_token_price(pap.contract.w3, block, blockchain, decimals=True),
        "collaterals": (collaterals := []),
        "debts": (debts := []),
    }

    currency_unit = Decimal(pap.price_oracle_contract.base_currency_unit)
    for underlying in ProtocolDataProvider(blockchain, block).underlyings(wallet):
        asset = {
            "token_address": underlying.token,
            "token_amount": abs(underlying.as_dict(decimals)["balance"]),
            "token_price_usd": pap.price_oracle_contract.get_asset_price(underlying.token) / currency_unit,
        }
        if underlying.amount < 0:
            debts.append(asset)
        else:
            collaterals.append(asset)

    return ret
