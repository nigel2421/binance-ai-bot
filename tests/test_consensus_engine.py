"""
Unit tests for CryptoConsensusEngine.
"""

import time
import pytest
from src.strategy.signal import StrategySignal, SignalDirection, SignalStatus, SignalTier
from src.consensus.crypto_consensus_engine import CryptoConsensusEngine, ConsensusDirection, ConsensusStrength


def test_consensus_engine_unanimous_bullish():
    engine = CryptoConsensusEngine()
    now = time.time()

    sig1 = StrategySignal("s1", "cryBTCUSD", "CryptoTrendAgent", now, "15m", SignalDirection.BULLISH, 0.80, "UPTREND", 0.85, 80.0, 75.0, status=SignalStatus.CANDIDATE, tier=SignalTier.A, supporting_evidence={"ema_alignment": 0.20})
    sig2 = StrategySignal("s2", "cryBTCUSD", "CryptoMomentumAgent", now, "15m", SignalDirection.BULLISH, 0.75, "UPTREND", 0.85, 80.0, 75.0, status=SignalStatus.CANDIDATE, tier=SignalTier.A, supporting_evidence={"healthy_bullish_rsi": 0.20})
    sig3 = StrategySignal("s3", "cryBTCUSD", "CryptoStructureAgent", now, "15m", SignalDirection.BULLISH, 0.70, "UPTREND", 0.85, 80.0, 75.0, status=SignalStatus.CANDIDATE, tier=SignalTier.B, supporting_evidence={"bullish_hh_hl_sequence": 0.25})

    regime = {"overall_regime": "UPTREND", "confidence": 0.85, "market_quality": 80.0, "alignment": 75.0}

    res = engine.evaluate_consensus("cryBTCUSD", [sig1, sig2, sig3], regime)

    assert res.direction == ConsensusDirection.BULLISH
    assert res.consensus_confidence > 0.40
    assert res.conflict_score == 0.0
    assert res.agreement_score == 100.0
    assert res.consensus_strength in (ConsensusStrength.VERY_STRONG, ConsensusStrength.STRONG)
