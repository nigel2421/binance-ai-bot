"""
Unit tests for Consensus conflict detection and high-confidence opposition penalties.
"""

import time
import pytest
from src.strategy.signal import StrategySignal, SignalDirection, SignalStatus, SignalTier
from src.consensus.crypto_consensus_engine import CryptoConsensusEngine, ConsensusDirection, ConsensusStrength


def test_high_confidence_opposition_conflict():
    engine = CryptoConsensusEngine()
    now = time.time()

    # Trend is Bullish (0.75), Momentum is Bearish (0.80) -> Explicit Conflict
    sig_trend = StrategySignal("s1", "cryADAUSD", "CryptoTrendAgent", now, "15m", SignalDirection.BULLISH, 0.75, "UPTREND", 0.80, 75.0, 70.0, status=SignalStatus.CANDIDATE, tier=SignalTier.A)
    sig_mom = StrategySignal("s2", "cryADAUSD", "CryptoMomentumAgent", now, "15m", SignalDirection.BEARISH, 0.80, "UPTREND", 0.80, 75.0, 70.0, status=SignalStatus.CANDIDATE, tier=SignalTier.A)
    sig_struct = StrategySignal("s3", "cryADAUSD", "CryptoStructureAgent", now, "15m", SignalDirection.BULLISH, 0.50, "UPTREND", 0.80, 75.0, 70.0, status=SignalStatus.CANDIDATE, tier=SignalTier.C)

    regime = {"overall_regime": "UPTREND", "confidence": 0.80, "market_quality": 75.0, "alignment": 70.0}

    res = engine.evaluate_consensus("cryADAUSD", [sig_trend, sig_mom, sig_struct], regime)

    assert res.direction == ConsensusDirection.CONFLICTED
    assert res.consensus_strength == ConsensusStrength.CONFLICTED
    assert res.conflict_score > 40.0
    assert res.consensus_confidence == 0.0
