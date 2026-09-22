import pytest
import pandas as pd
from src.features.market_structure import MarketStructureEngine, MarketStructureSnapshot
from tests.test_feature_engine import generate_synthetic_uptrend_df

def generate_synthetic_ranging_df(n: int = 50) -> pd.DataFrame:
    timestamps = [1600000000 + i * 60 for i in range(n)]
    # Oscillation around 100
    closes = [100.0 + (1.0 if i % 2 == 0 else -1.0) for i in range(n)]
    highs = [c + 0.3 for c in closes]
    lows = [c - 0.3 for c in closes]
    opens = [c - 0.1 for c in closes]

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "tick_count": [10] * n,
        "complete": [True] * n
    })

def test_bullish_market_structure():
    df = generate_synthetic_uptrend_df(50)
    struct = MarketStructureEngine.analyze_structure(df, "cryBTCUSD", "1m")

    assert struct.symbol == "cryBTCUSD"
    assert struct.structure_state == "BULLISH_STRUCTURE"
    assert struct.higher_highs_count > struct.lower_highs_count
    assert struct.support_level < struct.resistance_level

def test_ranging_market_structure():
    df = generate_synthetic_ranging_df(50)
    struct = MarketStructureEngine.analyze_structure(df, "cryBTCUSD", "1m")

    assert struct.structure_state in ("RANGING_STRUCTURE", "UNCLEAR_STRUCTURE")
    assert struct.local_swing_high >= struct.local_swing_low
