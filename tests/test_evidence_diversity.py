"""
Unit tests for Evidence Diversity scoring.
"""

import time
import pytest
from src.strategy.signal import StrategySignal, SignalDirection, SignalStatus, SignalTier
from src.consensus.crypto_consensus_engine import CryptoConsensusEngine


def test_evidence_diversity_scoring():
    engine = CryptoConsensusEngine()
    now = time.time()

    # Trend + Momentum + Structure = 3 distinct feature families
    sig1 = StrategySignal("s1", "cryBTCUSD", "CryptoTrendAgent", now, "15m", SignalDirection.BULLISH, 0.80, "UPTREND", 0.85, 80.0, 75.0, status=SignalStatus.CANDIDATE, tier=SignalTier.A, supporting_evidence={"ema_alignment": 0.20})
    sig2 = StrategySignal("s2", "cryBTCUSD", "CryptoMomentumAgent", now, "15m", SignalDirection.BULLISH, 0.75, "UPTREND", 0.85, 80.0, 75.0, status=SignalStatus.CANDIDATE, tier=SignalTier.A, supporting_evidence={"healthy_bullish_rsi": 0.20})
    sig3 = StrategySignal("s3", "cryBTCUSD", "CryptoStructureAgent", now, "15m", SignalDirection.BULLISH, 0.70, "UPTREND", 0.85, 80.0, 75.0, status=SignalStatus.CANDIDATE, tier=SignalTier.B, supporting_evidence={"bullish_hh_hl_sequence": 0.25})

    regime = {"overall_regime": "UPTREND", "confidence": 0.85, "market_quality": 80.0, "alignment": 75.0}

    res = engine.evaluate_consensus("cryBTCUSD", [sig1, sig2, sig3], regime)

    assert res.evidence_diversity_score >= 75.0  # 3 families * 25 = 75
