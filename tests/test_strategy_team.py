"""
Unit tests for CryptoStrategyTeam orchestrator.
"""

import pytest
from src.strategy.strategy_team import CryptoStrategyTeam
from src.strategy.signal import SignalStatus


def test_strategy_team_evaluates_all_five_agents():
    team = CryptoStrategyTeam()
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
            "rsi": 62.0,
            "macd": 15.0,
            "macd_signal": 10.0,
            "macd_histogram": 5.0,
            "roc": 1.5,
            "bollinger_position": 0.6,
            "candle_count": 100,
        }
    }
    regime = {"overall_regime": "UPTREND", "confidence": 0.85, "market_quality": 85.0, "alignment": 0.8}
    struct = {
        "higher_highs_count": 4,
        "higher_lows_count": 4,
        "lower_highs_count": 1,
        "lower_lows_count": 1,
        "support_level": 49000.0,
        "resistance_level": 50450.0,
        "structure_state": "BULLISH_STRUCTURE",
    }

    signals = team.evaluate_market("cryBTCUSD", features, regime, struct, w_health, allow_offline=True)
    
    assert len(signals) == 5
    strat_names = {s.strategy for s in signals}
    assert strat_names == {
        "CryptoTrendAgent",
        "CryptoMomentumAgent",
        "CryptoBreakoutAgent",
        "CryptoMeanReversionAgent",
        "CryptoStructureAgent",
    }

    # Verify MeanReversionAgent was routed out (ABSTAINED due to REGIME_MISMATCH)
    rev_sig = next(s for s in signals if s.strategy == "CryptoMeanReversionAgent")
    assert rev_sig.status == SignalStatus.ABSTAINED
