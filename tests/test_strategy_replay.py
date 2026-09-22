"""
Unit tests for StrategyReplayEngine.
"""

import pytest
import pandas as pd
import numpy as np

from src.strategy.replay_engine import StrategyReplayEngine
from src.strategy.strategy_analytics import StrategyAnalytics
from src.consensus.consensus_analytics import ConsensusAnalytics


def generate_synthetic_candles(num_candles: int = 100, trend: str = "UPTREND") -> pd.DataFrame:
    timestamps = [1700000000 + i * 900 for i in range(num_candles)]
    base_price = 50000.0

    records = []
    curr_price = base_price
    for i, ts in enumerate(timestamps):
        if trend == "UPTREND":
            delta = 20.0 + (i * 0.5)
        elif trend == "DOWNTREND":
            delta = -20.0 - (i * 0.5)
        else:
            delta = np.sin(i / 5.0) * 15.0

        open_p = curr_price
        close_p = open_p + delta
        high_p = max(open_p, close_p) + 10.0
        low_p = min(open_p, close_p) - 10.0

        records.append({
            "timestamp": ts,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": 100.0,
        })
        curr_price = close_p

    return pd.DataFrame(records)


def test_strategy_replay_engine():
    df_uptrend = generate_synthetic_candles(100, "UPTREND")
    replay = StrategyReplayEngine()

    replay_results = replay.replay_market("cryBTCUSD", df_uptrend, timeframe="15m", min_history_candles=50)

    assert len(replay_results) > 0
    signals = [r["signals"] for r in replay_results]
    consensus_list = [r["consensus"] for r in replay_results]
    opportunities = [r["opportunity"] for r in replay_results]

    assert len(signals) == len(replay_results)
    assert len(consensus_list) == len(replay_results)
    assert len(opportunities) == len(replay_results)
