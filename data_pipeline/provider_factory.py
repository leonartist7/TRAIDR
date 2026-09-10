"""Factory for the safe, read-only provider set used by TRAIDR research."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from data_pipeline.market_data_providers import (
    BitunixPrivateReadOnlyBoundary,
    BitunixPublicProvider,
    CoinGeckoProvider,
    CoinGlassProvider,
    CoinMarketCapProvider,
    CryptoPanicProvider,
)
from data_pipeline.provider_contracts import ReadOnlyMarketProvider


def build_read_only_market_providers(
    *,
    coingecko_coin_ids: Mapping[str, str],
    coinglass_api_key: str | None = None,
    coinmarketcap_api_key: str | None = None,
    cryptopanic_api_key: str | None = None,
) -> tuple[ReadOnlyMarketProvider, ...]:
    """Build providers with credentials kept in memory and execution absent.

    CoinGlass and CoinMarketCap keys are optional. A missing key produces an
    explicit insufficient-data result. The disabled Bitunix private boundary is
    intentionally not returned because it is not a market-data provider.
    """

    providers = (
        BitunixPublicProvider(),
        CoinGlassProvider(api_key=coinglass_api_key),
        CoinGeckoProvider(coin_ids=coingecko_coin_ids),
        CoinMarketCapProvider(api_key=coinmarketcap_api_key),
        CryptoPanicProvider(api_key=cryptopanic_api_key),
    )
    return cast(tuple[ReadOnlyMarketProvider, ...], providers)


def build_disabled_private_boundary() -> BitunixPrivateReadOnlyBoundary:
    """Expose the future account-read boundary without enabling any endpoint."""

    return BitunixPrivateReadOnlyBoundary()
