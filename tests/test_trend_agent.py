"""
Unit tests for CryptoTrendAgent.
"""

import pytest
from src.agents.crypto_trend_agent import CryptoTrendAgent
from src.strategy.signal import SignalDirection, SignalStatus, RejectionReason


def test_trend_agent_uptrend_candidate():
    agent = CryptoTrendAgent()
    w_health = {"state": "HEALTHY", "seconds_since_last_tick": 2.0}

    features = {
        "15m": {
            "price": 50000.0,
            "ema_fast": 50500.0,
            "ema_medium": 49800.0,
            "ema_slow": 49000.0,
            "trend_slope": 0.12,
            "adx": 28.0,
            "plus_di": 32.0,
            "minus_di": 12.0,
            "roc": 1.5,
            "candle_count": 100,
        }
    }
    regime = {
        "overall_regime": "UPTREND",
        "confidence": 0.85,
        "market_quality": 82.0,
        "alignment": 0.8,
    }
    struct = {"structure_state": "BULLISH_STRUCTURE"}

    sig = agent.evaluate("cryBTCUSD", features, regime, struct, w_health, allow_offline=True)
    assert sig.status == SignalStatus.CANDIDATE
    assert sig.direction == SignalDirection.BULLISH
    assert sig.confidence >= 0.50


def test_trend_agent_abstain_in_choppy():
    agent = CryptoTrendAgent()
    w_health = {"state": "HEALTHY", "seconds_since_last_tick": 2.0}

    features = {"15m": {"price": 50000.0, "candle_count": 100}}
    regime = {"overall_regime": "CHOPPY", "confidence": 0.50, "market_quality": 30.0, "alignment": 0.0}

    sig = agent.evaluate("cryBTCUSD", features, regime, {}, w_health, allow_offline=True)
    assert sig.status == SignalStatus.ABSTAINED
    assert sig.rejection_reason == RejectionReason.REGIME_MISMATCH
