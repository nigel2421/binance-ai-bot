"""
Crypto Opportunity Scorer for Deriv Crypto AI Bot Stage 5.

Combines Stage 5 ConsensusResult with Stage 3 market intelligence and Stage 4 strategy evidence
to compute a multi-factor opportunity score (0 to 100).

CRITICAL BOUNDARY:
- NO trade instructions, NO order execution, NO live stake sizing.
- Pure analytical setup opportunity scoring.
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
import time
import uuid
from typing import Dict, List, Optional, Any

from src.consensus.crypto_consensus_engine import ConsensusResult, ConsensusDirection, ConsensusStrength

logger = logging.getLogger("OPPORTUNITY_SCORER")


class OpportunityStatus(str, Enum):
    RESEARCH_ONLY = "RESEARCH_ONLY"
    OBSERVE = "OBSERVE"
    WEAK = "WEAK"
    QUALIFIED_RESEARCH = "QUALIFIED_RESEARCH"
    QUALIFIED_LIVE = "QUALIFIED_LIVE"
    CONFLICTED = "CONFLICTED"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    INVALID = "INVALID"


class OpportunityTier(str, Enum):
    ELITE = "ELITE"        # 85 - 100
    STRONG = "STRONG"      # 75 - 84.99
    MODERATE = "MODERATE"  # 65 - 74.99
    WEAK = "WEAK"          # 55 - 64.99
    REJECT = "REJECT"      # < 55


DEFAULT_COMPONENT_WEIGHTS = {
    "consensus_quality": 0.30,
    "market_quality": 0.15,
    "timeframe_alignment": 0.15,
    "regime_confidence": 0.10,
    "evidence_diversity": 0.10,
    "signal_freshness": 0.10,
    "strategy_signal_quality": 0.10,
}


@dataclass
class CryptoOpportunity:
    opportunity_id: str
    symbol: str
    direction: str                             # BULLISH, BEARISH, NEUTRAL, CONFLICTED
    opportunity_score: float                   # 0.0 to 100.0
    consensus_score: float
    market_quality_score: float
    timeframe_alignment_score: float
    regime_score: float
    evidence_diversity_score: float
    signal_freshness_score: float
    data_recency_score: float = 0.0
    live_freshness_score: float = 0.0
    strategy_quality_score: float = 0.0
    conflict_penalty: float = 0.0
    top_strategy: str = "NONE"
    supporting_strategies: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    status: OpportunityStatus = OpportunityStatus.OBSERVE
    tier: OpportunityTier = OpportunityTier.REJECT
    confidence_saturation_flag: bool = False   # True if raw confidence >= 0.95
    research_ready: bool = False
    live_ready: bool = False

    def is_valid_and_fresh(self, current_time: Optional[float] = None) -> bool:
        if self.status in (OpportunityStatus.EXPIRED, OpportunityStatus.INVALID, OpportunityStatus.CONFLICTED, OpportunityStatus.STALE):
            return False
        now = time.time() if current_time is None else current_time
        if self.expires_at and now >= self.expires_at:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "opportunity_score": round(self.opportunity_score, 1),
            "tier": self.tier.value if isinstance(self.tier, Enum) else str(self.tier),
            "status": self.status.value if isinstance(self.status, Enum) else str(self.status),
            "consensus_score": round(self.consensus_score, 1),
            "market_quality_score": round(self.market_quality_score, 1),
            "timeframe_alignment_score": round(self.timeframe_alignment_score, 1),
            "regime_score": round(self.regime_score, 1),
            "evidence_diversity_score": round(self.evidence_diversity_score, 1),
            "signal_freshness_score": round(self.signal_freshness_score, 1),
            "data_recency_score": round(self.data_recency_score, 1),
            "live_freshness_score": round(self.live_freshness_score, 1),
            "strategy_quality_score": round(self.strategy_quality_score, 1),
            "conflict_penalty": round(self.conflict_penalty, 1),
            "top_strategy": self.top_strategy,
            "supporting_strategies": self.supporting_strategies,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "confidence_saturation_flag": self.confidence_saturation_flag,
            "research_ready": self.research_ready,
            "live_ready": self.live_ready,
        }


class CryptoOpportunityScorer:
    """
    Multi-Factor Opportunity Scorer.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None, opportunity_ttl_sec: float = 300.0):
        self.weights = weights or dict(DEFAULT_COMPONENT_WEIGHTS)
        self.opportunity_ttl_sec = opportunity_ttl_sec
        self.saturation_count = 0
        self.total_scored = 0

    def evaluate_opportunity(
        self,
        consensus: ConsensusResult,
        watcher_health: Dict[str, Any],
        timestamp: Optional[float] = None,
    ) -> CryptoOpportunity:
        """
        Computes opportunity score and assigns research tier for a market consensus result.
        """
        ts = timestamp or time.time()
        op_id = f"op_{consensus.symbol}_{int(ts)}_{uuid.uuid4().hex[:6]}"
        self.total_scored += 1

        is_research_ready = watcher_health.get("research_ready", True) if watcher_health else True
        is_live_ready = watcher_health.get("live_ready", False) if watcher_health else False

        # 1. Handle Conflicted or No-Consensus states immediately
        if consensus.direction in (ConsensusDirection.CONFLICTED, ConsensusDirection.NO_CONSENSUS):
            return CryptoOpportunity(
                opportunity_id=op_id,
                symbol=consensus.symbol,
                direction=consensus.direction.value,
                opportunity_score=0.0,
                consensus_score=0.0,
                market_quality_score=consensus.market_quality,
                timeframe_alignment_score=consensus.timeframe_alignment,
                regime_score=consensus.regime_confidence * 100.0,
                evidence_diversity_score=consensus.evidence_diversity_score,
                signal_freshness_score=0.0,
                data_recency_score=0.0,
                live_freshness_score=0.0,
                strategy_quality_score=0.0,
                conflict_penalty=consensus.conflict_score,
                top_strategy=consensus.strongest_supporter or "NONE",
                supporting_strategies=consensus.participating_agents,
                created_at=ts,
                expires_at=ts + 60.0,
                status=OpportunityStatus.CONFLICTED if consensus.direction == ConsensusDirection.CONFLICTED else OpportunityStatus.OBSERVE,
                tier=OpportunityTier.REJECT,
                research_ready=is_research_ready,
                live_ready=is_live_ready,
            )

        # 2. Compute individual 0-100 components
        c_score = consensus.consensus_confidence * 100.0
        mq_score = max(0.0, min(100.0, consensus.market_quality))
        ta_score = max(0.0, min(100.0, consensus.timeframe_alignment))
        r_score = max(0.0, min(100.0, consensus.regime_confidence * 100.0))
        ed_score = max(0.0, min(100.0, consensus.evidence_diversity_score))

        # Freshness scores: Separate Data Recency from Live Freshness
        data_recency_sec = watcher_health.get("data_recency_sec", 0.0) if watcher_health else 0.0
        data_recency_score = max(0.0, min(100.0, (120.0 - data_recency_sec) / 120.0 * 100.0))

        live_freshness_sec = watcher_health.get("live_stream_freshness_sec", 99999.0) if watcher_health else 99999.0
        if is_live_ready and live_freshness_sec < 99999.0:
            live_freshness_score = max(0.0, min(100.0, (60.0 - live_freshness_sec) / 60.0 * 100.0))
        else:
            live_freshness_score = 0.0

        signal_freshness_score = live_freshness_score if is_live_ready else data_recency_score

        # Strategy quality score (based on agreement & participant strength)
        strat_q_score = consensus.agreement_score

        # 3. Confidence Saturation Tracking
        saturation_flag = consensus.consensus_confidence >= 0.95
        if saturation_flag:
            self.saturation_count += 1
            logger.debug(f"[OPPORTUNITY_SCORER][{consensus.symbol}] High confidence saturation detected ({consensus.consensus_confidence:.4f})")

        # 4. Weighted Base Opportunity Score
        base_score = (
            (c_score * self.weights["consensus_quality"]) +
            (mq_score * self.weights["market_quality"]) +
            (ta_score * self.weights["timeframe_alignment"]) +
            (r_score * self.weights["regime_confidence"]) +
            (ed_score * self.weights["evidence_diversity"]) +
            (signal_freshness_score * self.weights["signal_freshness"]) +
            (strat_q_score * self.weights["strategy_signal_quality"])
        )

        # 5. Apply Conflict & Data Penalties
        conflict_penalty = (consensus.conflict_score * 0.30) + (consensus.disagreement_score * 0.10)
        final_score = max(0.0, min(100.0, base_score - conflict_penalty))

        # 6. Assign Tier & Status
        tier = self._assign_tier(final_score)

        if final_score >= 65.0:
            if is_live_ready:
                status = OpportunityStatus.QUALIFIED_LIVE
            elif is_research_ready:
                status = OpportunityStatus.QUALIFIED_RESEARCH
            else:
                status = OpportunityStatus.RESEARCH_ONLY
        elif final_score >= 50.0:
            status = OpportunityStatus.WEAK
        else:
            status = OpportunityStatus.OBSERVE

        return CryptoOpportunity(
            opportunity_id=op_id,
            symbol=consensus.symbol,
            direction=consensus.direction.value,
            opportunity_score=round(final_score, 1),
            consensus_score=round(c_score, 1),
            market_quality_score=round(mq_score, 1),
            timeframe_alignment_score=round(ta_score, 1),
            regime_score=round(r_score, 1),
            evidence_diversity_score=round(ed_score, 1),
            signal_freshness_score=round(signal_freshness_score, 1),
            data_recency_score=round(data_recency_score, 1),
            live_freshness_score=round(live_freshness_score, 1),
            strategy_quality_score=round(strat_q_score, 1),
            conflict_penalty=round(conflict_penalty, 1),
            top_strategy=consensus.strongest_supporter or "NONE",
            supporting_strategies=consensus.participating_agents,
            created_at=ts,
            expires_at=ts + self.opportunity_ttl_sec,
            status=status,
            tier=tier,
            confidence_saturation_flag=saturation_flag,
            research_ready=is_research_ready,
            live_ready=is_live_ready,
        )

    @staticmethod
    def _assign_tier(score: float) -> OpportunityTier:
        if score >= 85.0:
            return OpportunityTier.ELITE
        elif score >= 75.0:
            return OpportunityTier.STRONG
        elif score >= 65.0:
            return OpportunityTier.MODERATE
        elif score >= 55.0:
            return OpportunityTier.WEAK
        else:
            return OpportunityTier.REJECT

    def get_saturation_analytics(self) -> Dict[str, Any]:
        """Returns saturation metrics for diagnostic monitoring."""
        pct = (self.saturation_count / self.total_scored * 100.0) if self.total_scored > 0 else 0.0
        return {
            "total_scored": self.total_scored,
            "saturation_count": self.saturation_count,
            "saturation_rate_pct": round(pct, 2),
        }
