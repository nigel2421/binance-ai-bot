"""
Unit tests for CryptoStructureAgent.
"""

import pytest
from src.agents.crypto_structure_agent import CryptoStructureAgent
from src.strategy.signal import SignalDirection, SignalStatus


def test_structure_agent_bullish_break_of_structure():
    agent = CryptoStructureAgent()
    w_health = {"state": "HEALTHY", "seconds_since_last_tick": 2.0}

    features = {"15m": {"price": 50500.0, "candle_count": 100}}
    regime = {"overall_regime": "UPTREND", "confidence": 0.80, "market_quality": 80.0, "alignment": 0.7}
    struct = {
        "higher_highs_count": 4,
        "higher_lows_count": 4,
        "lower_highs_count": 1,
        "lower_lows_count": 1,
        "support_level": 49000.0,
        "resistance_level": 50450.0,
        "local_swing_high": 50450.0,
        "local_swing_low": 49000.0,
        "structure_state": "BULLISH_STRUCTURE",
    }

    sig = agent.evaluate("cryBTCUSD", features, regime, struct, w_health, allow_offline=True)
    assert sig.status == SignalStatus.CANDIDATE
    assert sig.direction == SignalDirection.BULLISH
    assert sig.entry_context["internal_structure_state"] == "BULLISH_BREAK_STRUCTURE"
