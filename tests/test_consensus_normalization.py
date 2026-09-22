import time
import pytest
from src.consensus.crypto_consensus_engine import CryptoConsensusEngine, ConsensusDirection
from src.strategy.signal import StrategySignal, SignalDirection, SignalStatus, SignalTier


def make_sig(symbol: str, strategy: str, direction: SignalDirection, confidence: float, status: SignalStatus) -> StrategySignal:
    ts = time.time()
    return StrategySignal(
        signal_id=f"sig_{strategy}",
        symbol=symbol,
        strategy=strategy,
        timestamp=ts,
        timeframe="15m",
        direction=direction,
        confidence=confidence,
        regime="STRONG_UPTREND",
        regime_confidence=1.0,
        market_quality=100.0,
        timeframe_alignment=100.0,
        status=status,
        tier=SignalTier.A if status == SignalStatus.CANDIDATE else SignalTier.REJECT,
    )


def test_abstain_non_dilution():
    engine = CryptoConsensusEngine()
    
    # 3 participating aligned agents with 0.80 confidence, 2 abstaining
    signals = [
        make_sig("cryBTCUSD", "CryptoTrendAgent", SignalDirection.BULLISH, 0.80, SignalStatus.CANDIDATE),
        make_sig("cryBTCUSD", "CryptoMomentumAgent", SignalDirection.BULLISH, 0.80, SignalStatus.CANDIDATE),
        make_sig("cryBTCUSD", "CryptoStructureAgent", SignalDirection.BULLISH, 0.80, SignalStatus.CANDIDATE),
        make_sig("cryBTCUSD", "CryptoBreakoutAgent", SignalDirection.ABSTAIN, 0.0, SignalStatus.ABSTAINED),
        make_sig("cryBTCUSD", "CryptoMeanReversionAgent", SignalDirection.ABSTAIN, 0.0, SignalStatus.ABSTAINED),
    ]

    regime_snapshot = {
        "overall_regime": "STRONG_UPTREND",
        "confidence": 1.0,
        "market_quality": 100.0,
        "alignment": 100.0,
    }

    res = engine.evaluate_consensus("cryBTCUSD", signals, regime_snapshot)

    assert res.direction == ConsensusDirection.BULLISH
    assert res.signal_strength == 0.80
    assert res.participation_strength == 1.0  # 3 participating out of 3 expected for UPTREND
    assert res.consensus_coverage_score == 100.0
    assert res.consensus_confidence == 0.80
    assert len(res.abstaining_agents) == 2


def test_consensus_coverage_ranging():
    engine = CryptoConsensusEngine()
    
    # RANGING expects 2 agents (MeanReversion and Structure)
    signals = [
        make_sig("cryETHUSD", "CryptoMeanReversionAgent", SignalDirection.BULLISH, 0.75, SignalStatus.CANDIDATE),
        make_sig("cryETHUSD", "CryptoStructureAgent", SignalDirection.BULLISH, 0.75, SignalStatus.CANDIDATE),
    ]

    regime_snapshot = {
        "overall_regime": "RANGING",
        "confidence": 0.90,
        "market_quality": 80.0,
        "alignment": 80.0,
    }

    res = engine.evaluate_consensus("cryETHUSD", signals, regime_snapshot)

    assert res.direction == ConsensusDirection.BULLISH
    assert res.participation_strength == 1.0
    assert res.consensus_coverage_score == 100.0
