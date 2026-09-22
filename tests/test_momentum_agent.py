"""
Unit tests for CryptoMomentumAgent.
"""

import pytest
from src.agents.crypto_momentum_agent import CryptoMomentumAgent
from src.strategy.signal import SignalDirection, SignalStatus


def test_momentum_agent_bullish_acceleration():
    agent = CryptoMomentumAgent()
    w_health = {"state": "HEALTHY", "seconds_since_last_tick": 2.0}

    features = {
        "15m": {
            "price": 50000.0,
            "rsi": 62.0,
            "macd": 15.0,
            "macd_signal": 10.0,
            "macd_histogram": 5.0,
            "roc": 1.2,
            "trend_slope": 0.08,
            "candle_count": 100,
        }
    }
    regime = {"overall_regime": "UPTREND", "confidence": 0.80, "market_quality": 80.0, "alignment": 0.7}

    sig = agent.evaluate("cryBTCUSD", features, regime, {}, w_health, allow_offline=True)
    assert sig.status == SignalStatus.CANDIDATE
    assert sig.direction == SignalDirection.BULLISH
    assert sig.confidence >= 0.50
