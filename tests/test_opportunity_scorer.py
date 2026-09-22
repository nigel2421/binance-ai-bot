"""
Unit tests for CryptoOpportunityScorer.
"""

import time
import pytest
from src.consensus.crypto_consensus_engine import ConsensusResult, ConsensusDirection, ConsensusStrength
from src.opportunity.crypto_opportunity_scorer import CryptoOpportunityScorer, OpportunityTier, OpportunityStatus


def test_opportunity_scorer_qualified_setup():
    scorer = CryptoOpportunityScorer()
    now = time.time()

    consensus = ConsensusResult(
        consensus_id="c1",
        symbol="cryBCHUSD",
        timestamp=now,
        direction=ConsensusDirection.BULLISH,
        consensus_confidence=0.85,
        agreement_score=100.0,
        disagreement_score=0.0,
        conflict_score=0.0,
        bullish_weight=2.5,
        bearish_weight=0.0,
        neutral_weight=0.0,
        participating_agents=["CryptoTrendAgent", "CryptoMomentumAgent", "CryptoStructureAgent"],
        evidence_diversity_score=75.0,
        consensus_strength=ConsensusStrength.VERY_STRONG,
        regime="STRONG_UPTREND",
        regime_confidence=0.90,
        market_quality=95.0,
        timeframe_alignment=100.0,
    )

    watcher_health = {"seconds_since_last_tick": 2.0}

    op = scorer.evaluate_opportunity(consensus, watcher_health, timestamp=now)

    assert op.status in (OpportunityStatus.QUALIFIED_RESEARCH, OpportunityStatus.QUALIFIED_LIVE)
