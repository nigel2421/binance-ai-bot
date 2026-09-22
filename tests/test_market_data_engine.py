import pytest
from unittest.mock import AsyncMock
from src.market.market_data_engine import BinanceMarketDataEngine, Candle

@pytest.mark.asyncio
async def test_preload_historical_klines_and_ws_stream():
    mock_client = AsyncMock()
    # Mock REST klines
    # [Open time, Open, High, Low, Close, Volume, ...]
    mock_klines = [
        [1600000000000, "50000.0", "50100.0", "49900.0", "50050.0", "12.5", 1600000059999],
        [1600000060000, "50050.0", "50200.0", "50000.0", "50150.0", "15.0", 1600000119999]
    ]
    mock_client.get_klines.return_value = mock_klines

    engine = BinanceMarketDataEngine(client=mock_client)
    await engine.preload_historical_klines(["BTCUSDT"], intervals=["1m"])

    candles = engine.get_candles("BTCUSDT", "1m")
    assert len(candles) == 2
    assert candles[0].open == 50000.0
    assert candles[1].close == 50150.0

    # Test DataFrame generation
    df = engine.get_dataframe("BTCUSDT", "1m")
    assert len(df) == 2
    assert "close" in df.columns
    assert df.iloc[-1]["close"] == 50150.0

    # Test WS stream candle update
    ws_msg = {
        "data": {
            "e": "kline",
            "k": {
                "s": "BTCUSDT",
                "i": "1m",
                "t": 1600000120000,
                "o": "50150.0",
                "h": "50300.0",
                "l": "50100.0",
                "c": "50250.0",
                "v": "20.0",
                "x": False
            }
        }
    }
    await engine.handle_ws_message(ws_msg)

    candles = engine.get_candles("BTCUSDT", "1m")
    assert len(candles) == 3
    assert candles[-1].close == 50250.0
    assert not engine.is_stale("BTCUSDT")
