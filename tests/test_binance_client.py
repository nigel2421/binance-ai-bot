import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.api.binance_client import BinanceClient

@pytest.mark.asyncio
async def test_binance_client_signature():
    client = BinanceClient(api_key="test_key", api_secret="test_secret")
    params = {"symbol": "BTCUSDT", "side": "BUY", "type": "LIMIT", "timestamp": 1600000000000}
    sig = client._generate_signature(params)
    assert isinstance(sig, str)
    assert len(sig) == 64  # SHA256 hex digest length

@pytest.mark.asyncio
async def test_get_exchange_info_mock():
    client = BinanceClient()
    mock_data = {
        "timezone": "UTC",
        "serverTime": 1600000000000,
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
                    {"filterType": "LOT_SIZE", "minQty": "0.00001000", "maxQty": "9000.00000000", "stepSize": "0.00001000"},
                    {"filterType": "PRICE_FILTER", "minPrice": "0.01000000", "maxPrice": "1000000.00000000", "tickSize": "0.01000000"}
                ]
            }
        ]
    }

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=mock_data)
    mock_response.raise_for_status = MagicMock()

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_response)
    cm.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.get.return_value = cm

    with patch.object(client, "_get_session", AsyncMock(return_value=mock_session)):
        res = await client.get_exchange_info()
        assert res["timezone"] == "UTC"
        assert len(res["symbols"]) == 1
        assert res["symbols"][0]["symbol"] == "BTCUSDT"

    await client.close()
