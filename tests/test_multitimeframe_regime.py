import pytest
from src.features.crypto_feature_engine import CryptoFeatureEngine
from src.features.market_structure import MarketStructureEngine
from src.agents.crypto_regime_agent import (
    CryptoRegimeAgent,
    MultiTimeframeRegimeEngine,
    CryptoMarketQualityEngine,
    SingleTimeframeRegimeResult
)
from tests.test_feature_engine import generate_synthetic_uptrend_df

def test_multitimeframe_alignment_and_weighting():
    df = generate_synthetic_uptrend_df(50)
    agent = CryptoRegimeAgent()

    tf_results = {}
    for tf in ["1m", "5m", "15m", "30m", "1h", "4h"]:
        feat = CryptoFeatureEngine.calculate_snapshot(df, "cryBTCUSD", tf)
        struct = MarketStructureEngine.analyze_structure(df, "cryBTCUSD", tf)
        res = agent.classify_regime(feat, struct)
        tf_results[tf] = res

    mtf_res = MultiTimeframeRegimeEngine.evaluate_multitimeframe_regime("cryBTCUSD", tf_results)

    assert mtf_res["symbol"] == "cryBTCUSD"
    assert mtf_res["overall_regime"] in ("UPTREND", "STRONG_UPTREND")
    assert mtf_res["timeframe_alignment"] > 70.0
    assert mtf_res["regime_confidence"] > 0.5

def test_market_quality_scoring():
    score = CryptoMarketQualityEngine.calculate_quality_score(
        data_quality=100.0,
        regime_confidence=0.85,
        timeframe_alignment=80.0,
        trend_strength=70.0
    )
    assert 0.0 <= score <= 100.0
    assert score > 70.0  # High quality environment
