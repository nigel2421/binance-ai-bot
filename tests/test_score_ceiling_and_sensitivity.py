import time
import pytest
from src.consensus.crypto_consensus_engine import CryptoConsensusEngine, ConsensusDirection
from src.opportunity.crypto_opportunity_scorer import CryptoOpportunityScorer, OpportunityTier, OpportunityStatus
from src.strategy.signal import StrategySignal, SignalDirection, SignalStatus, SignalTier


def make_sig(symbol: str, strategy: str, direction: SignalDirection, confidence: float, status: SignalStatus = SignalStatus.CANDIDATE) -> StrategySignal:
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
        market_quality=95.0,
        timeframe_alignment=100.0,
        supporting_evidence={"ema_alignment": 1.0, "positive_roc": 1.0, "bullish_structure": 1.0} if strategy == "CryptoTrendAgent" else ({"positive_macd_hist": 1.0, "volatility_expansion": 1.0} if strategy == "CryptoMomentumAgent" else {"break_of_structure_bullish": 1.0}),
        status=status,
        tier=SignalTier.A if status == SignalStatus.CANDIDATE else SignalTier.REJECT,
    )


def test_scenario_a_perfect_setup_ceiling():
    consensus_engine = CryptoConsensusEngine()
    scorer = CryptoOpportunityScorer()

    signals = [
        make_sig("cryBTCUSD", "CryptoTrendAgent", SignalDirection.BULLISH, 0.90),
        make_sig("cryBTCUSD", "CryptoMomentumAgent", SignalDirection.BULLISH, 0.90),
        make_sig("cryBTCUSD", "CryptoStructureAgent", SignalDirection.BULLISH, 0.90),
    ]

    regime_snapshot = {
        "overall_regime": "STRONG_UPTREND",
        "confidence": 1.0,
        "market_quality": 95.0,
        "alignment": 100.0,
    }

    consensus = consensus_engine.evaluate_consensus("cryBTCUSD", signals, regime_snapshot)
    
    watcher_health = {
        "seconds_since_last_tick": 1.0,
        "data_recency_sec": 1.0,
        "live_stream_freshness_sec": 1.0,
        "research_ready": True,
        "live_ready": True,
    }

    op = scorer.evaluate_opportunity(consensus, watcher_health)

    assert op.opportunity_score >= 75.0, f"Expected STRONG/ELITE tier (>=75.0), got {op.opportunity_score}"
    assert op.tier in (OpportunityTier.STRONG, OpportunityTier.ELITE)
    assert op.status == OpportunityStatus.QUALIFIED_LIVE


def test_scenario_b_single_specialist_moderate():
    consensus_engine = CryptoConsensusEngine()
    scorer = CryptoOpportunityScorer()

    signals = [
        make_sig("cryBTCUSD", "CryptoTrendAgent", SignalDirection.BULLISH, 0.60),
    ]

    regime_snapshot = {
        "overall_regime": "STRONG_UPTREND",
        "confidence": 0.70,
        "market_quality": 70.0,
        "alignment": 70.0,
    }

    consensus = consensus_engine.evaluate_consensus("cryBTCUSD", signals, regime_snapshot)
    
    watcher_health = {
        "seconds_since_last_tick": 5.0,
        "data_recency_sec": 5.0,
        "live_stream_freshness_sec": 5.0,
        "research_ready": True,
        "live_ready": False,
    }

    op = scorer.evaluate_opportunity(consensus, watcher_health)

    assert op.opportunity_score < 75.0
    assert op.opportunity_score < 65.0 or op.status == OpportunityStatus.QUALIFIED_RESEARCH
    assert op.status != OpportunityStatus.QUALIFIED_LIVE


def test_scenario_c_high_opposition_conflicted():
    consensus_engine = CryptoConsensusEngine()
    scorer = CryptoOpportunityScorer()

    signals = [
        make_sig("cryBTCUSD", "CryptoTrendAgent", SignalDirection.BULLISH, 0.85),
        make_sig("cryBTCUSD", "CryptoMomentumAgent", SignalDirection.BEARISH, 0.85),
    ]

    regime_snapshot = {
        "overall_regime": "UNCERTAIN",
        "confidence": 0.50,
        "market_quality": 50.0,
        "alignment": 50.0,
    }

    consensus = consensus_engine.evaluate_consensus("cryBTCUSD", signals, regime_snapshot)
    watcher_health = {"research_ready": True, "live_ready": True}

    op = scorer.evaluate_opportunity(consensus, watcher_health)

    assert consensus.direction == ConsensusDirection.CONFLICTED
    assert op.opportunity_score == 0.0
    assert op.status == OpportunityStatus.CONFLICTED


def test_score_sensitivity_monotonicity():
    consensus_engine = CryptoConsensusEngine()
    scorer = CryptoOpportunityScorer()

    prev_score = -1.0
    for conf in [0.40, 0.60, 0.80, 0.95]:
        signals = [
            make_sig("cryBTCUSD", "CryptoTrendAgent", SignalDirection.BULLISH, conf),
            make_sig("cryBTCUSD", "CryptoMomentumAgent", SignalDirection.BULLISH, conf),
        ]
        regime_snapshot = {"overall_regime": "STRONG_UPTREND", "confidence": conf, "market_quality": conf * 100.0, "alignment": conf * 100.0}
        consensus = consensus_engine.evaluate_consensus("cryBTCUSD", signals, regime_snapshot)
        watcher_health = {"data_recency_sec": 1.0, "live_stream_freshness_sec": 1.0, "research_ready": True, "live_ready": True}
        op = scorer.evaluate_opportunity(consensus, watcher_health)

        assert op.opportunity_score > prev_score, f"Score monotonicity failed at conf={conf}: {op.opportunity_score} <= {prev_score}"
        prev_score = op.opportunity_score
