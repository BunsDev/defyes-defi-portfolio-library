from decimal import Decimal
from functools import cached_property
from typing import Iterator, NamedTuple

from web3 import Web3
from web3.exceptions import BadFunctionCallOutput

from defyes.constants import Chain
from defyes.explorer import ChainExplorer
from defyes.financial import ChainedPrice, Interval
from defyes.functions import ensure_a_block_number
from defyes.lazytime import Duration, Time
from defyes.types import Addr, Token, TokenAmount

from .autogenerated import BaseVault


class BaseVault(BaseVault):
    @cached_property
    def management_withdraw_fee_factor(self) -> Decimal:
        return Decimal(self.get_withdraw_fee_ratio) / self.denominator

    @cached_property
    def share_token(self):
        return Token.get_instance(self.address, self.blockchain, self.block)

    @cached_property
    def asset_token(self):
        return Token.get_instance(self.asset, self.blockchain, self.block)

    def __repr__(self):
        return f"{self.address}:{self.__class__.__name__}"

    @cached_property
    def _chain_explorer(self):
        return ChainExplorer(self.blockchain)

    @cached_property
    def time(self) -> Time:
        return Time(self._chain_explorer.time_from_block(self.block))

    @cached_property
    def year_beginning(self):
        return Time.from_calendar(self.time.calendar.year, 1, 1)

    @cached_property
    def month_beginning(self):
        return Time.from_calendar(self.time.calendar.year, self.time.calendar.month, 1)

    @cached_property
    def at_30days_before(self) -> BaseVault:
        prev_time = self.time - Duration.days(30)
        prev_block = self._chain_explorer.block_after(prev_time)
        return self.__class__(self.blockchain, prev_block, self.address)

    @cached_property
    def at_year_beginning(self) -> BaseVault:
        prev_block = self._chain_explorer.block_after(self.year_beginning)
        return self.__class__(self.blockchain, prev_block, self.address)

    @cached_property
    def at_month_beginning(self) -> BaseVault:
        prev_block = self._chain_explorer.block_after(self.month_beginning)
        return self.__class__(self.blockchain, prev_block, self.address)

    @cached_property
    def at_previous_month_beginning(self) -> BaseVault:
        prev_month_last_day = self.month_beginning - Duration.days(1)
        prev_month_beginning = Time.from_calendar(
            prev_month_last_day.calendar.year, prev_month_last_day.calendar.month, 1
        )
        prev_block = self._chain_explorer.block_after(prev_month_beginning)
        return self.__class__(self.blockchain, prev_block, self.address)

    @cached_property
    def share_price_decimal(self):
        try:
            return Decimal(self.share_price).scaleb(-self.decimals)
        except BadFunctionCallOutput:
            return None

    @cached_property
    def share_chained_price(self):
        return ChainedPrice(self.share_price_decimal, self.block, self.time)

    @cached_property
    def last_30_days(self):
        return Interval(
            initial=self.at_30days_before.share_chained_price,
            final=self.share_chained_price,
        )

    @cached_property
    def current_month(self):
        return Interval(
            initial=self.at_month_beginning.share_chained_price,
            final=self.share_chained_price,
        )

    @cached_property
    def current_year(self):
        return Interval(
            initial=self.at_year_beginning.share_chained_price,
            final=self.share_chained_price,
        )

    @cached_property
    def previous_month(self):
        return Interval(
            initial=self.at_previous_month_beginning.share_chained_price,
            final=self.at_month_beginning.share_chained_price,
        )


class StEthVolatilityVault(BaseVault):
    """
    stETH Volatility Vault

    This is a low-risk strategy that focuses on ETH accumulation. It invests in Lido and uses part of Lido's yield to
    set up strangles weekly. It accumulates more ETH whenever the price goes up and when it goes down.
    """

    default_addresses: dict[str, str] = {
        Chain.ETHEREUM: Addr("0x463F9ED5e11764Eb9029762011a03643603aD879"),
        Chain.GOERLI: Addr("0x626bC69e52A543F8dea317Ff885C9060b8ebbbf5"),
    }


class EthphoriaVault(BaseVault):
    """
    ETHphoria Vault

    This is a low-risk strategy that focuses on ETH accumulation. The vault stakes ETH in Lido and uses all weekly yield
    to buy one-week ETH call options on a weekly basis. It accumulates more ETH whenever the price goes up. It is a way
    to go long on ETH without risking the principal.
    """

    default_addresses: dict[str, str] = {
        Chain.ETHEREUM: Addr("0x5FE4B38520e856921978715C8579D2D7a4d2274F"),
    }


class UsdcFudVault(BaseVault):
    """
    USDC FUD Vault

    This is a low-risk strategy that focuses on hedging against market crashes. The vault invests USDC in Aave and uses
    all weekly yield to buy one-week ETH put options on a weekly basis. It accumulates more USDC whenever the price goes
    down.
    """

    default_addresses: dict[str, str] = {
        Chain.ETHEREUM: Addr("0x287f941aB4B5AaDaD2F13F9363fcEC8Ee312a969"),
    }


class VaultClasses(tuple):
    def instances(self, blockchain, block_id):
        for vault_class in self:
            yield vault_class(blockchain, block_id)


vault_classes = VaultClasses(
    (
        StEthVolatilityVault,
        EthphoriaVault,
        UsdcFudVault,
    )
)


class VaultAssetShare(NamedTuple):
    vault: BaseVault
    asset_amount: TokenAmount
    share_amount: TokenAmount


def underlyings_holdings(wallet: Addr, block_id: int, blockchain: Chain = Chain.ETHEREUM) -> Iterator[VaultAssetShare]:
    for vault_class in vault_classes:
        vault = vault_class(blockchain, block_id)
        shares = vault.balance_of(wallet)
        assets = vault.preview_redeem(shares) + vault.idle_assets_of(wallet)  # includes management fee
        yield VaultAssetShare(
            vault,
            TokenAmount.from_teu(assets, vault.asset_token),
            TokenAmount.from_teu(shares, vault.share_token),
        )


def get_protocol_data(
    wallet: Addr, block: int | str = "latest", blockchain: Chain = Chain.ETHEREUM, decimals: bool = True
) -> dict:
    wallet = Web3.to_checksum_address(wallet)
    block_id = ensure_a_block_number(block, blockchain)

    positions = {
        vault.address: {
            "underlyings": [asset_amount.as_dict(decimals)],
            "holdings": [share_amount.as_dict(decimals)],
        }
        for vault, asset_amount, share_amount in underlyings_holdings(wallet, block_id, blockchain)
        if asset_amount != 0 or share_amount != 0
    }

    vaults_metrics = {
        vault.address: {
            "management_fee": vault.management_withdraw_fee_factor,
            "intervals": {
                "last_30_days": vault.last_30_days.rate,
                "current_month": vault.current_month.rate,
                "previous_month": vault.previous_month.rate,
                "current_year": vault.current_year.rate,
            },
        }
        for vault in vault_classes.instances(blockchain, block)
    }

    return {
        "blockchain": blockchain,
        "block_id": block_id,
        "protocol": "Pods",
        "version": 0,
        "wallet": wallet,
        "decimals": decimals,
        "positions": positions,
        "positions_key": "vault_address",
        "financial_metrics": vaults_metrics,
    }
