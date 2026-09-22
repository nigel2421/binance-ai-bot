import pytest
from unittest.mock import AsyncMock
from src.market.crypto_market_registry import BinanceMarketRegistry

@pytest.mark.asyncio
async def test_market_discovery_filtering():
    mock_client = AsyncMock()
    mock_exchange_info = {
        "symbols": [
            {
                "symbol": "BTCUSDT",
                "status": "TRADING",
                "baseAsset": "BTC",
                "quoteAsset": "USDT",
                "pricePrecision": 2,
                "quantityPrecision": 5,
                "isSpotTradingAllowed": True,
                "filters": [
                    {"filterType": "LOT_SIZE", "minQty": "0.0001", "stepSize": "0.0001"},
                    {"filterType": "MIN_NOTIONAL", "minNotional": "10.0"}
                ]
            },
            {
                "symbol": "ETHUSDT",
                "status": "BREAK",  # Inactive
                "baseAsset": "ETH",
                "quoteAsset": "USDT",
                "pricePrecision": 2,
                "quantityPrecision": 4,
                "isSpotTradingAllowed": True,
                "filters": []
            },
            {
                "symbol": "BTCBTC",  # Non-USDT quote asset
                "status": "TRADING",
                "baseAsset": "BTC",
                "quoteAsset": "BTC",
                "filters": []
            }
        ]
    }
    mock_client.get_exchange_info.return_value = mock_exchange_info

    registry = BinanceMarketRegistry(client=mock_client)
    active_symbols = await registry.discover_markets(quote_asset="USDT")

    assert "BTCUSDT" in active_symbols
    assert "ETHUSDT" not in active_symbols  # Disabled status
    assert "BTCBTC" not in active_symbols   # Filtered out by quote asset

    info = registry.get_symbol_info("BTCUSDT")
    assert info is not None
    assert info.base_asset == "BTC"
    assert info.min_qty == 0.0001
    assert info.min_notional == 10.0
