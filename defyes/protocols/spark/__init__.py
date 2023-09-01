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
    def assets_with_reserve_tokens(self) -> Iterator[tuple[Token, Token]]:
        for _, main_token in self.all_reserves_tokens:
            tokens = self.get_reserve_tokens_addresses(main_token)
            yield main_token, tokens

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

    def holding_underlying_iter(self, wallet: Addr) -> Iterator[tuple[TokenAmount, TokenAmount]]:
        for asset, tokens in self.assets_with_reserve_tokens:
            user_reserve_data = UserReserveData(*self.get_user_reserve_data(asset, wallet))
            teu_balance = user_reserve_data.sp - user_reserve_data.stable_debt - user_reserve_data.variable_debt
            balance = TokenAmount(teu_balance, asset)

            for teu_amount, token in zip(user_reserve_data[:3], tokens):
                if teu_amount != 0:
                    yield TokenAmount.from_teu(teu_amount, token), balance

    class HoldingsUnderlyings(NamedTuple):
        holdings: list[TokenAmount]
        underlying: list[TokenAmount]

    def position(self, wallet: Addr) -> HoldingsUnderlyings:
        """This is just a column-wise version of the holding/underlying pair list."""
        return self.HoldingsUnderlyings(*zip(*self.holding_underlying_iter(wallet)))


def get_protocol_data(wallet: Addr, block: int | str, chain: Chain, decimals: bool = True) -> dict:
    wallet = Addr(wallet)
    holdings, underlyings = ProtocolDataProvider(chain, block).position(wallet)
    pap = PoolAddressesProvider(chain, block)
    user_account_data = pap.pool_contract.user_account_data(wallet)

    def as_dict_list(token_amounts):
        return [token_amount.as_dict(decimals) for token_amount in token_amounts]

    return {
        "blockchain": chain,
        "block_id": block,
        "protocol": "Spark",
        "version": 0,
        "wallet": wallet,
        "decimals": decimals,
        "positions": {
            "single_position": {
                "holdings": as_dict_list(holdings),
                "underlyings": as_dict_list(underlyings),
            }
        },
        "positions_key": None,
        "finantial_metrics": {
            "collateral_ratio": user_account_data.collateral_ratio,
            "liquidation_ratio": user_account_data.liquidation_ratio,
        },
    }


def get_full_finantial_metrics(wallet: Addr, block: int | str, chain: Chain, decimals: bool = True) -> dict:
    wallet = Addr(wallet)
    pap = PoolAddressesProvider(chain, block)

    user_account_data = pap.pool_contract.user_account_data(wallet)
    ret = {
        "collateral_ratio": user_account_data.collateral_ratio,
        "liquidation_ratio": user_account_data.liquidation_ratio,
        "native_token_price_usd": chainlink.get_native_token_price(pap.contract.w3, block, chain, decimals=True),
        "collaterals": (collaterals := []),
        "debts": (debts := []),
    }

    currency_unit = Decimal(pap.price_oracle_contract.base_currency_unit)
    for _, underlying in ProtocolDataProvider(chain, block).holding_underlying_iter(wallet):
        asset = {
            "token_address": underlying.token,
            "token_amount": abs(amount := underlying.as_dict(decimals)["balance"]),
            "token_price_usd": pap.price_oracle_contract.get_asset_price(underlying.token) / currency_unit,
        }
        if amount < 0:
            debts.append(asset)
        else:
            collaterals.append(asset)

    return ret
