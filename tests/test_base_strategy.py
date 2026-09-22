"""
Unit tests for BaseStrategyAgent and Data Safety Gate.
"""

import time
import pytest
from src.agents.base_strategy_agent import BaseStrategyAgent
from src.strategy.signal import SignalDirection, SignalStatus, SignalTier, RejectionReason


class DummyStrategyAgent(BaseStrategyAgent):
    def __init__(self):
        super().__init__(name="DummyStrategyAgent", primary_timeframe="15m")

    def _evaluate_internal(self, symbol, feature_snapshots, regime_snapshot, structure_snapshot, watcher_health, timestamp):
        if symbol == "RAISE_ERR":
            raise ValueError("Test forced exception")
        
        return self.build_signal(
            symbol=symbol,
            direction=SignalDirection.BULLISH,
            confidence=0.80,
            regime="UPTREND",
            regime_confidence=0.85,
            market_quality=80.0,
            timeframe_alignment=75.0,
            status=SignalStatus.CANDIDATE,
            timestamp=timestamp,
        )


def test_base_strategy_data_safety_gate_rejections():
    agent = DummyStrategyAgent()
    
    # 1. Test HISTORY_ONLY rejection when allow_offline=False
    w_health = {"state": "HISTORY_ONLY", "seconds_since_last_tick": 10.0}
    sig = agent.evaluate(
        symbol="cryBTCUSD",
        feature_snapshots={"15m": {"candle_count": 100}},
        regime_snapshot={"overall_regime": "UPTREND"},
        structure_snapshot={},
        watcher_health=w_health,
        allow_offline=False,
    )
    assert sig.status == SignalStatus.REJECTED
    assert sig.rejection_reason == RejectionReason.HISTORY_ONLY

    # 2. Test HISTORY_ONLY allowed when allow_offline=True
    sig_offline = agent.evaluate(
        symbol="cryBTCUSD",
        feature_snapshots={"15m": {"candle_count": 100}},
        regime_snapshot={"overall_regime": "UPTREND"},
        structure_snapshot={},
        watcher_health=w_health,
        allow_offline=True,
    )
    assert sig_offline.status == SignalStatus.CANDIDATE
    assert sig_offline.confidence == 0.80

    # 3. Test STALE watcher state
    w_stale = {"state": "STALE", "seconds_since_last_tick": 300.0}
    sig_stale = agent.evaluate(
        symbol="cryBTCUSD",
        feature_snapshots={"15m": {"candle_count": 100}},
        regime_snapshot={"overall_regime": "UPTREND"},
        structure_snapshot={},
        watcher_health=w_stale,
        allow_offline=False,
    )
    assert sig_stale.status == SignalStatus.REJECTED
    assert sig_stale.rejection_reason == RejectionReason.STALE_DATA


def test_base_strategy_exception_isolation():
    agent = DummyStrategyAgent()
    w_health = {"state": "HEALTHY", "seconds_since_last_tick": 5.0}
    
    sig = agent.evaluate(
        symbol="RAISE_ERR",
        feature_snapshots={"15m": {"candle_count": 100}},
        regime_snapshot={"overall_regime": "UPTREND"},
        structure_snapshot={},
        watcher_health=w_health,
        allow_offline=True,
    )
    assert sig.status == SignalStatus.REJECTED
    assert sig.rejection_reason == RejectionReason.STRATEGY_EXCEPTION
