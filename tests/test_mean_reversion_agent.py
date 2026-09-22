"""
Unit tests for CryptoMeanReversionAgent.
"""

import pytest
from src.agents.crypto_mean_reversion_agent import CryptoMeanReversionAgent
from src.strategy.signal import SignalDirection, SignalStatus, RejectionReason


def test_mean_reversion_agent_abstain_in_strong_uptrend():
    agent = CryptoMeanReversionAgent()
    w_health = {"state": "HEALTHY", "seconds_since_last_tick": 2.0}

    features = {"15m": {"price": 50000.0, "bollinger_position": 0.05, "rsi": 30.0, "candle_count": 100}}
    regime = {"overall_regime": "STRONG_UPTREND", "confidence": 0.90, "market_quality": 90.0, "alignment": 0.9}

    sig = agent.evaluate("cryBTCUSD", features, regime, {}, w_health, allow_offline=True)
    assert sig.status == SignalStatus.ABSTAINED
    assert sig.rejection_reason == RejectionReason.REGIME_MISMATCH


def test_mean_reversion_agent_bullish_range_reversion():
    agent = CryptoMeanReversionAgent()
    w_health = {"state": "HEALTHY", "seconds_since_last_tick": 2.0}

    features = {
        "15m": {
            "price": 49000.0,
            "bollinger_position": 0.08,
            "bollinger_middle": 50000.0,
            "rsi": 32.0,
            "distance_from_fast_ema": -1.5,
            "distance_from_slow_ema": -2.5,
            "roc": -0.2,
            "candle_count": 100,
        }
    }
    regime = {"overall_regime": "RANGING", "confidence": 0.75, "market_quality": 70.0, "alignment": 0.2}
    struct = {"support_level": 48900.0, "resistance_level": 51000.0}

    sig = agent.evaluate("cryBTCUSD", features, regime, struct, w_health, allow_offline=True)
    assert sig.status == SignalStatus.CANDIDATE
    assert sig.direction == SignalDirection.BULLISH
