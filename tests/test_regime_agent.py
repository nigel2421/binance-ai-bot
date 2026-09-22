import pytest
from src.features.crypto_feature_engine import CryptoFeatureEngine
from src.features.market_structure import MarketStructureEngine
from src.agents.crypto_regime_agent import CryptoRegimeAgent
from tests.test_feature_engine import generate_synthetic_uptrend_df
from tests.test_market_structure import generate_synthetic_ranging_df

def test_uptrend_regime_classification():
    df = generate_synthetic_uptrend_df(50)
    feat = CryptoFeatureEngine.calculate_snapshot(df, "cryBTCUSD", "1m")
    struct = MarketStructureEngine.analyze_structure(df, "cryBTCUSD", "1m")

    agent = CryptoRegimeAgent()
    res = agent.classify_regime(feat, struct)

    assert res.confirmed_regime in ("UPTREND", "STRONG_UPTREND")
    assert res.confidence > 0.5
    assert res.trend.direction in ("BULLISH", "STRONG_BULLISH")
    assert res.momentum.state in ("POSITIVE", "STRONG_POSITIVE")

def test_uncertain_regime_when_signals_conflict():
    df = generate_synthetic_uptrend_df(50)
    feat = CryptoFeatureEngine.calculate_snapshot(df, "cryBTCUSD", "1m")
    struct = MarketStructureEngine.analyze_structure(df, "cryBTCUSD", "1m")

    # Artificially inject conflicting momentum (RSI negative, trend bullish)
    feat.rsi = 25.0
    feat.macd_histogram = -5.0
    feat.momentum_state = "NEGATIVE"

    agent = CryptoRegimeAgent()
    res = agent.classify_regime(feat, struct)

    assert res.raw_regime == "UNCERTAIN"
    assert len(res.conflicting_features) > 0
