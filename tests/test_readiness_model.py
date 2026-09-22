import time
import pytest
from src.monitoring.watcher_health import CryptoWatcher, WatcherState


def test_watcher_readiness_model_historical_only():
    w = CryptoWatcher("cryBTCUSD")
    
    # Preload candles (historical ready)
    w.update_timeframe_readiness({
        "1m": "READY", "5m": "READY", "15m": "READY",
        "30m": "READY", "1h": "READY", "4h": "READY"
    }, last_candle_time=time.time())

    # Update intelligence (features & regime ready)
    w.update_intelligence({"overall_regime": "STRONG_UPTREND", "regime_confidence": 0.85}, quality_score=90.0)
    w.strategy_ready = True
    w.consensus_ready = True

    # No live tick stream received yet
    w.evaluate_health(is_ws_connected=True)

    assert w.historical_ready is True
    assert w.features_ready is True
    assert w.regime_ready is True
    assert w.strategy_ready is True
    assert w.consensus_ready is True
    assert w.research_ready is True
    assert w.live_stream_ready is False
    assert w.live_ready is False
    assert w.state == WatcherState.HISTORY_ONLY


def test_watcher_readiness_model_live_ready():
    w = CryptoWatcher("cryETHUSD")
    w.update_timeframe_readiness({
        "1m": "READY", "5m": "READY", "15m": "READY",
        "30m": "READY", "1h": "READY", "4h": "READY"
    }, last_candle_time=time.time())
    w.update_intelligence({"overall_regime": "RANGING", "regime_confidence": 0.70}, quality_score=80.0)
    w.strategy_ready = True
    w.consensus_ready = True

    # Receive live tick stream
    now = time.time()
    w.update_tick(price=2500.0, timestamp=now, rate_per_min=20.0, is_live_stream=True)
    w.evaluate_health(is_ws_connected=True)

    assert w.historical_ready is True
    assert w.live_stream_ready is True
    assert w.research_ready is True
    assert w.live_ready is True
    assert w.state == WatcherState.HEALTHY
