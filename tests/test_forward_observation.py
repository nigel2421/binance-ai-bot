"""
Unit tests for Extended Forward Observation (+1, +3, +5, +10, +20 bars).
"""

import pytest
import pandas as pd
import numpy as np

from src.strategy.replay_engine import StrategyReplayEngine
from src.consensus.consensus_analytics import ConsensusAnalytics
from tests.test_strategy_replay import generate_synthetic_candles


def test_extended_forward_observation():
    df_uptrend = generate_synthetic_candles(120, "UPTREND")
    replay = StrategyReplayEngine()

    replay_results = replay.replay_market("cryBTCUSD", df_uptrend, timeframe="15m", min_history_candles=50, observation_bars=[1, 3, 5, 10, 20])

    assert len(replay_results) > 0

    # Calibration analytics
    score_cal = ConsensusAnalytics.compute_score_band_calibration(replay_results)
    assert isinstance(score_cal, dict)

    strength_cal = ConsensusAnalytics.compute_strength_calibration(replay_results)
    assert isinstance(strength_cal, dict)
