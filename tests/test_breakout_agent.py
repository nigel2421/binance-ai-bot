"""
Unit tests for CryptoBreakoutAgent.
"""

import pytest
from src.agents.crypto_breakout_agent import CryptoBreakoutAgent
from src.strategy.signal import SignalDirection, SignalStatus


def test_breakout_agent_bullish_breakout():
    agent = CryptoBreakoutAgent()
    w_health = {"state": "HEALTHY", "seconds_since_last_tick": 2.0}

    features = {
        "15m": {
            "price": 50500.0,
            "bollinger_upper": 50400.0,
            "bollinger_lower": 49600.0,
            "bollinger_width": 0.016,  # compression
            "atr_percent": 0.8,
            "rolling_volatility": 0.35,
            "roc": 1.4,
            "candle_count": 100,
        }
    }
    regime = {"overall_regime": "BREAKOUT_BULLISH", "confidence": 0.80, "market_quality": 85.0, "alignment": 0.8}
    struct = {"resistance_level": 50400.0, "support_level": 49600.0}

    sig = agent.evaluate("cryBTCUSD", features, regime, struct, w_health, allow_offline=True)
    assert sig.status == SignalStatus.CANDIDATE
    assert sig.direction == SignalDirection.BULLISH
    assert "compression_score" in sig.entry_context
