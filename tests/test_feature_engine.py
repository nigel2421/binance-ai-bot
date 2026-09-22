import pytest
import numpy as np
import pandas as pd
from src.features.crypto_feature_engine import CryptoFeatureEngine, MarketFeatureSnapshot

def generate_synthetic_uptrend_df(n: int = 50) -> pd.DataFrame:
    base_price = 100.0
    timestamps = [1600000000 + i * 60 for i in range(n)]
    closes = [base_price + i * 1.5 + (i % 3) * 0.2 for i in range(n)]
    highs = [c + 0.5 for c in closes]
    lows = [c - 0.5 for c in closes]
    opens = [c - 0.2 for c in closes]

    return pd.DataFrame({
        "timestamp": timestamps,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "tick_count": [10] * n,
        "complete": [True] * n
    })

def test_data_quality_verification():
    df_clean = generate_synthetic_uptrend_df(50)
    score_clean, issues_clean = CryptoFeatureEngine.verify_data_quality(df_clean)
    assert score_clean == 100.0
    assert len(issues_clean) == 0

    # Malformed dataframe with OHLC violation
    df_bad = df_clean.copy()
    df_bad.loc[10, "high"] = 50.0  # high < open
    score_bad, issues_bad = CryptoFeatureEngine.verify_data_quality(df_bad)
    assert score_bad < 100.0
    assert len(issues_bad) > 0

def test_feature_snapshot_calculation():
    df = generate_synthetic_uptrend_df(50)
    feat = CryptoFeatureEngine.calculate_snapshot(df, "cryBTCUSD", "1m")

    assert feat.symbol == "cryBTCUSD"
    assert feat.timeframe == "1m"
    assert feat.is_ready is True
    assert feat.ema_fast > feat.ema_slow  # Uptrend hierarchy
    assert feat.rsi > 50.0                # Positive RSI
    assert feat.macd_histogram >= 0.0     # Positive MACD
    assert feat.adx > 0.0
    assert feat.bollinger_upper > feat.bollinger_middle > feat.bollinger_lower
    assert feat.higher_highs > 0
