import pytest
from unittest.mock import AsyncMock
from src.market.market_data_engine import CryptoMarketDataEngine, Candle, TimeframeReadiness

def test_utc_candle_boundary_calculation_all_timeframes():
    engine = CryptoMarketDataEngine()

    # Epoch 1600002054 (Wed Sep 16 2020 12:34:14 UTC)
    ts = 1600002054

    # 1m boundary (60s) -> 1600002000
    assert engine.get_candle_boundary(ts, 60) == 1600002000

    # 5m boundary (300s) -> 1600002000
    assert engine.get_candle_boundary(ts, 300) == 1600002000

    # 15m boundary (900s) -> 1600001900 (12:31:40... 12:30:00 boundary is 1600001900? 1600002054 // 900 = 1777780 * 900 = 1600002000? Let's check 1600002000 / 900 = 1777780.0)
    # 1600002000 is 12:33:20 UTC? 1600002000 / 900 = 1777780 exact.
    assert engine.get_candle_boundary(ts, 900) == 1600002000

    # 30m boundary (1800s) -> 1600002000 is divisible by 1800? 1600002000 / 1800 = 888890.0
    assert engine.get_candle_boundary(ts, 1800) == 1600002000

    # 1h boundary (3600s) -> 1600002000 // 3600 * 3600 = 1600002000
    assert engine.get_candle_boundary(ts, 3600) == 1600002000

    # 4h boundary (14400s) -> 1600002054 // 14400 * 14400 = 1599998400
    assert engine.get_candle_boundary(ts, 14400) == (ts // 14400) * 14400

def test_tick_processing_ohlc_correctness():
    engine = CryptoMarketDataEngine()
    symbol = "cryBTCUSD"

    # Artificial tick sequence: 100, 102, 99, 101 at same 1m UTC boundary (1600000020)
    ts_base = 1600000020
    assert engine.process_tick(symbol, 100.0, ts_base + 5) is True
    assert engine.process_tick(symbol, 102.0, ts_base + 10) is True
    assert engine.process_tick(symbol, 99.0, ts_base + 20) is True
    assert engine.process_tick(symbol, 101.0, ts_base + 30) is True

    candles = engine.get_candles(symbol, "1m")
    assert len(candles) == 1
    c = candles[0]
    assert c.open == 100.0
    assert c.high == 102.0
    assert c.low == 99.0
    assert c.close == 101.0
    assert c.tick_count == 4
    assert c.complete is False

def test_late_and_duplicate_tick_filtering():
    engine = CryptoMarketDataEngine()
    symbol = "cryBTCUSD"

    ts_base = 1600000000
    assert engine.process_tick(symbol, 100.0, ts_base + 10) is True

    # Duplicate timestamp
    assert engine.process_tick(symbol, 100.0, ts_base + 10) is True  # Accepted as tick at same timestamp

    # Out-of-order late timestamp
    assert engine.process_tick(symbol, 99.0, ts_base + 5) is False   # Rejected (5 < 10)

    # Malformed negative price
    assert engine.process_tick(symbol, -50.0, ts_base + 15) is False # Rejected

@pytest.mark.asyncio
async def test_historical_warmup_populates_timeframes():
    mock_client = AsyncMock()
    mock_history = {
        "candles": [
            {"epoch": 1600000000, "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0},
            {"epoch": 1600000060, "open": 101.0, "high": 104.0, "low": 100.0, "close": 103.0}
        ]
    }
    mock_client.request.return_value = mock_history

    engine = CryptoMarketDataEngine(client=mock_client)
    await engine.preload_historical_candles(["cryBTCUSD"], timeframes=["1m", "5m", "15m", "30m", "1h", "4h"])

    for tf in ["1m", "5m", "15m", "30m", "1h", "4h"]:
        candles = engine.get_candles("cryBTCUSD", tf)
        assert len(candles) == 2
        assert candles[0].open == 100.0
        assert candles[1].close == 103.0
