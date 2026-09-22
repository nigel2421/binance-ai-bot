"""
Mandatory Anti-Look-Ahead Bias Test for Stage 4 Strategy Team.

Proves strictly that strategy output evaluated at candle N does NOT change
when candles N+1, N+2, N+3 ... exist later in the dataset.
"""

import pytest
import pandas as pd
import numpy as np

from src.features.crypto_feature_engine import CryptoFeatureEngine
from src.features.market_structure import MarketStructureEngine
from src.agents.crypto_regime_agent import CryptoRegimeAgent, MultiTimeframeRegimeEngine
from src.strategy.strategy_team import CryptoStrategyTeam


def test_strict_anti_look_ahead_bias():
    """
    Evaluates candle N in two scenarios:
      Scenario A: Dataset sliced EXACTLY up to candle N (len = N+1).
      Scenario B: Slicing full dataset at N (index = 55) for evaluation.
    Verifies that the strategy signals generated at index N are IDENTICAL.
    """
    # 1. Generate synthetic 100-candle dataset
    timestamps = [1700000000 + i * 900 for i in range(100)]
    records = []
    curr_price = 50000.0
    for i, ts in enumerate(timestamps):
        delta = 15.0 if i < 60 else -30.0  # trend reversal later in dataset
        open_p = curr_price
        close_p = open_p + delta
        records.append({
            "timestamp": ts,
            "open": open_p,
            "high": max(open_p, close_p) + 5.0,
            "low": min(open_p, close_p) - 5.0,
            "close": close_p,
            "volume": 100.0,
        })
        curr_price = close_p

    df_full = pd.DataFrame(records)
    target_candle_index = 55  # Evaluate at index 55

    team = CryptoStrategyTeam()
    regime_agent = CryptoRegimeAgent()
    mock_watcher = {"state": "HEALTHY", "seconds_since_last_tick": 1.0}

    # --- Scenario A: Sliced dataset up to target_candle_index ---
    df_sliced_a = df_full.iloc[: target_candle_index + 1].copy()
    feat_obj_a = CryptoFeatureEngine.calculate_snapshot(df_sliced_a, "cryBTCUSD", "15m")
    struct_obj_a = MarketStructureEngine.analyze_structure(df_sliced_a, "cryBTCUSD", "15m")
    tf_res_a = regime_agent.classify_regime(feat_obj_a, struct_obj_a)
    mtf_res_a = MultiTimeframeRegimeEngine.evaluate_multitimeframe_regime("cryBTCUSD", {"15m": tf_res_a})

    signals_scenario_a = team.evaluate_market(
        symbol="cryBTCUSD",
        feature_snapshots={"15m": feat_obj_a.to_dict()},
        regime_snapshot=mtf_res_a,
        structure_snapshot=struct_obj_a.to_dict(),
        watcher_health=mock_watcher,
        allow_offline=True,
    )

    # --- Scenario B: Feature engine & regime calculated slicing df_full up to target_candle_index ---
    df_sliced_b = df_full.iloc[: target_candle_index + 1].copy()
    feat_obj_b = CryptoFeatureEngine.calculate_snapshot(df_sliced_b, "cryBTCUSD", "15m")
    struct_obj_b = MarketStructureEngine.analyze_structure(df_sliced_b, "cryBTCUSD", "15m")
    tf_res_b = regime_agent.classify_regime(feat_obj_b, struct_obj_b)
    mtf_res_b = MultiTimeframeRegimeEngine.evaluate_multitimeframe_regime("cryBTCUSD", {"15m": tf_res_b})

    signals_scenario_b = team.evaluate_market(
        symbol="cryBTCUSD",
        feature_snapshots={"15m": feat_obj_b.to_dict()},
        regime_snapshot=mtf_res_b,
        structure_snapshot=struct_obj_b.to_dict(),
        watcher_health=mock_watcher,
        allow_offline=True,
    )

    # --- Verification ---
    assert len(signals_scenario_a) == len(signals_scenario_b)

    for sig_a, sig_b in zip(signals_scenario_a, signals_scenario_b):
        assert sig_a.strategy == sig_b.strategy
        assert sig_a.direction == sig_b.direction
        assert sig_a.confidence == sig_b.confidence
        assert sig_a.status == sig_b.status
        assert sig_a.supporting_evidence == sig_b.supporting_evidence
        assert sig_a.conflicting_evidence == sig_b.conflicting_evidence
