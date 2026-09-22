import pytest
from unittest.mock import AsyncMock
from src.market.crypto_market_registry import CryptoMarketRegistry, CryptoSymbolInfo, CryptoContractCapability

@pytest.mark.asyncio
async def test_crypto_market_discovery_filtering():
    mock_client = AsyncMock()
    mock_active_symbols = {
        "active_symbols": [
            {
                "symbol": "cryBTCUSD",
                "display_name": "Bitcoin",
                "market": "cryptocurrency",
                "submarket": "non_stable_coin",
                "is_trading_suspended": 0,
                "exchange_is_open": 1
            },
            {
                "symbol": "cryETHUSD",
                "display_name": "Ethereum",
                "market": "cryptocurrency",
                "submarket": "non_stable_coin",
                "is_trading_suspended": 1,  # Suspended
                "exchange_is_open": 0
            },
            {
                "symbol": "R_100",  # Volatility Index (Non-Crypto)
                "display_name": "Volatility 100 Index",
                "market": "synthetic_index",
                "submarket": "random_index",
                "is_trading_suspended": 0,
                "exchange_is_open": 1
            }
        ]
    }
    mock_client.request.return_value = mock_active_symbols

    registry = CryptoMarketRegistry(client=mock_client)
    active_symbols = await registry.discover_markets()

    assert "cryBTCUSD" in active_symbols
    assert "cryETHUSD" not in active_symbols  # Suspended
    assert "R_100" not in active_symbols       # Synthetic Index excluded

    assert len(registry.available_crypto_symbols) == 2
    assert len(registry.active_crypto_symbols) == 1

@pytest.mark.asyncio
async def test_contract_capability_and_supports():
    mock_client = AsyncMock()
    mock_contracts_response = {
        "contracts_for": {
            "available": [
                {
                    "contract_type": "CALL",
                    "contract_category": "callput",
                    "contract_display_name": "Rise",
                    "min_contract_duration": "1m",
                    "max_contract_duration": "1d"
                },
                {
                    "contract_type": "PUT",
                    "contract_category": "callput",
                    "contract_display_name": "Fall",
                    "min_contract_duration": "1m",
                    "max_contract_duration": "1d"
                }
            ]
        }
    }
    mock_client.request.return_value = mock_contracts_response

    registry = CryptoMarketRegistry(client=mock_client)
    registry.symbols_info["cryBTCUSD"] = CryptoSymbolInfo({
        "symbol": "cryBTCUSD",
        "is_trading_suspended": 0,
        "exchange_is_open": 1
    })

    await registry.discover_contracts_for_symbol("cryBTCUSD")

    # Valid query
    supported, reason = registry.supports("cryBTCUSD", "CALL", duration=5, duration_unit="m")
    assert supported is True
    assert reason == "OK"

    # Invalid contract type query
    supported_bad, reason_bad = registry.supports("cryBTCUSD", "MULTUP", duration=5, duration_unit="m")
    assert supported_bad is False
    assert "MULTUP not supported" in reason_bad
