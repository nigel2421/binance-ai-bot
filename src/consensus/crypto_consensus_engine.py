"""
Crypto Consensus Engine for Deriv Crypto AI Bot Stage 5.

Transforms independent Stage 4 StrategySignal objects into an evidence-weighted committee consensus.
Avoids simple majority voting. Disagreement produces CONFLICTED states rather than forcing a direction.

IMPORTANT: consensus_confidence measures setup consensus strength (0.00 to 1.00),
NOT win probability.
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
import time
import uuid
from typing import Dict, List, Optional, Set, Any

from src.strategy.signal import StrategySignal, SignalDirection, SignalStatus

logger = logging.getLogger("CONSENSUS_ENGINE")


class ConsensusDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    CONFLICTED = "CONFLICTED"
    NO_CONSENSUS = "NO_CONSENSUS"


class ConsensusStrength(str, Enum):
    VERY_STRONG = "VERY_STRONG"
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    SINGLE_SPECIALIST = "SINGLE_SPECIALIST"
    CONFLICTED = "CONFLICTED"
    NONE = "NONE"


# Feature family mapping for evidence diversity calculation
FEATURE_FAMILY_MAP = {
    "ema_alignment": "TREND",
    "partial_ema_alignment": "TREND",
    "price_above_fast_ema": "TREND",
    "price_below_fast_ema": "TREND",
    "positive_trend_slope": "TREND",
    "negative_trend_slope": "TREND",
    "adx_strength": "TREND",
    "plus_di_domination": "TREND",
    "minus_di_domination": "TREND",
    "positive_roc": "MOMENTUM",
    "negative_roc": "MOMENTUM",
    "healthy_bullish_rsi": "MOMENTUM",
    "strong_bullish_rsi": "MOMENTUM",
    "healthy_bearish_rsi": "MOMENTUM",
    "strong_bearish_rsi": "MOMENTUM",
    "positive_macd_hist": "MOMENTUM",
    "negative_macd_hist": "MOMENTUM",
    "macd_line_above_signal": "MOMENTUM",
    "macd_line_below_signal": "MOMENTUM",
    "positive_roc_acceleration": "MOMENTUM",
    "negative_roc_acceleration": "MOMENTUM",
    "prior_compression": "BREAKOUT",
    "price_above_breakout_level": "BREAKOUT",
    "price_below_breakout_level": "BREAKOUT",
    "breakout_momentum_confirmation": "BREAKOUT",
    "volatility_expansion": "VOLATILITY",
    "bollinger_lower_band_touch": "MEAN_REVERSION",
    "bollinger_upper_band_touch": "MEAN_REVERSION",
    "near_lower_bollinger_band": "MEAN_REVERSION",
    "near_upper_bollinger_band": "MEAN_REVERSION",
    "rsi_range_exhaustion": "MEAN_REVERSION",
    "stretched_below_ma": "MEAN_REVERSION",
    "stretched_above_ma": "MEAN_REVERSION",
    "bullish_structure": "STRUCTURE",
    "bearish_structure": "STRUCTURE",
    "bullish_hh_hl_sequence": "STRUCTURE",
    "bearish_lh_ll_sequence": "STRUCTURE",
    "break_of_structure_bullish": "STRUCTURE",
    "break_of_structure_bearish": "STRUCTURE",
    "price_holding_above_support": "STRUCTURE",
    "price_holding_below_resistance": "STRUCTURE",
}


@dataclass
class ConsensusResult:
    consensus_id: str
    symbol: str
    timestamp: float
    direction: ConsensusDirection
    consensus_confidence: float               # 0.00 - 1.00 setup consensus strength
    agreement_score: float                    # 0 - 100
    disagreement_score: float                 # 0 - 100
    conflict_score: float                     # 0 - 100
    bullish_weight: float
    bearish_weight: float
    neutral_weight: float
    participating_agents: List[str] = field(default_factory=list)
    abstaining_agents: List[str] = field(default_factory=list)
    rejected_agents: List[str] = field(default_factory=list)
    strongest_supporter: Optional[str] = None
    strongest_opponent: Optional[str] = None
    evidence_diversity_score: float = 0.0      # 0 - 100
    signal_strength: float = 0.0               # 0.0 - 1.0 raw directional agreement confidence
    participation_strength: float = 0.0        # 0.0 - 1.0 coverage ratio of eligible agents
    consensus_coverage_score: float = 0.0      # 0 - 100
    consensus_strength: ConsensusStrength = ConsensusStrength.NONE
    regime: str = "UNCERTAIN"
    regime_confidence: float = 0.0
    market_quality: float = 0.0
    timeframe_alignment: float = 0.0
    supporting_evidence: Dict[str, float] = field(default_factory=dict)
    conflicting_evidence: Dict[str, float] = field(default_factory=dict)
    consensus_status: str = "VALID"
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "consensus_id": self.consensus_id,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "direction": self.direction.value if isinstance(self.direction, Enum) else str(self.direction),
            "consensus_confidence": round(self.consensus_confidence, 4),
            "agreement_score": round(self.agreement_score, 1),
            "disagreement_score": round(self.disagreement_score, 1),
            "conflict_score": round(self.conflict_score, 1),
            "bullish_weight": round(self.bullish_weight, 4),
            "bearish_weight": round(self.bearish_weight, 4),
            "neutral_weight": round(self.neutral_weight, 4),
            "participating_agents": self.participating_agents,
            "abstaining_agents": self.abstaining_agents,
            "rejected_agents": self.rejected_agents,
            "strongest_supporter": self.strongest_supporter,
            "strongest_opponent": self.strongest_opponent,
            "evidence_diversity_score": round(self.evidence_diversity_score, 1),
            "signal_strength": round(self.signal_strength, 4),
            "participation_strength": round(self.participation_strength, 4),
            "consensus_coverage_score": round(self.consensus_coverage_score, 1),
            "consensus_strength": self.consensus_strength.value if isinstance(self.consensus_strength, Enum) else str(self.consensus_strength),
            "regime": self.regime,
            "regime_confidence": round(self.regime_confidence, 4),
            "market_quality": round(self.market_quality, 1),
            "timeframe_alignment": round(self.timeframe_alignment, 1),
            "supporting_evidence": {k: round(v, 4) for k, v in self.supporting_evidence.items()},
            "conflicting_evidence": {k: round(v, 4) for k, v in self.conflicting_evidence.items()},
            "consensus_status": self.consensus_status,
            "created_at": self.created_at,
        }


class CryptoConsensusEngine:
    """
    Evidence-Weighted Multi-Agent Consensus Engine.
    """

    def __init__(self, strategy_weights: Optional[Dict[str, float]] = None):
        # Neutral initial strategy weights
        self.strategy_weights = strategy_weights or {
            "CryptoTrendAgent": 1.0,
            "CryptoMomentumAgent": 1.0,
            "CryptoBreakoutAgent": 1.0,
            "CryptoMeanReversionAgent": 1.0,
            "CryptoStructureAgent": 1.0,
        }

    def evaluate_consensus(
        self,
        symbol: str,
        signals: List[StrategySignal],
        regime_snapshot: Dict[str, Any],
        timestamp: Optional[float] = None,
    ) -> ConsensusResult:
        """
        Calculates evidence-weighted consensus across strategy specialist signals.
        """
        ts = timestamp or time.time()
        cid = f"cons_{symbol}_{int(ts)}_{uuid.uuid4().hex[:6]}"

        overall_regime = regime_snapshot.get("overall_regime", "UNCERTAIN")
        regime_conf = regime_snapshot.get("confidence", 0.0)
        mkt_quality = regime_snapshot.get("market_quality", 0.0)
        mtf_align = regime_snapshot.get("alignment", 0.0)

        participating: List[str] = []
        abstaining: List[str] = []
        rejected: List[str] = []

        bull_weight = 0.0
        bear_weight = 0.0
        neut_weight = 0.0

        bull_candidates: List[StrategySignal] = []
        bear_candidates: List[StrategySignal] = []

        all_supporting_evidence: Dict[str, float] = {}
        all_conflicting_evidence: Dict[str, float] = {}

        # 1. Categorize & Weight Signals
        for sig in signals:
            strat = sig.strategy
            if sig.status == SignalStatus.REJECTED:
                rejected.append(strat)
                continue

            if sig.status == SignalStatus.ABSTAINED or sig.direction == SignalDirection.ABSTAIN:
                abstaining.append(strat)
                continue

            # Participating active candidate or neutral evaluation
            participating.append(strat)
            base_w = self.strategy_weights.get(strat, 1.0)
            regime_rel = self._get_regime_relevance(strat, overall_regime)
            quality_factor = max(0.2, mkt_quality / 100.0)

            weighted_score = sig.confidence * base_w * regime_rel * quality_factor

            if sig.direction == SignalDirection.BULLISH:
                bull_weight += weighted_score
                bull_candidates.append(sig)
                for k, v in sig.supporting_evidence.items():
                    all_supporting_evidence[f"{strat}:{k}"] = v
            elif sig.direction == SignalDirection.BEARISH:
                bear_weight += weighted_score
                bear_candidates.append(sig)
                for k, v in sig.supporting_evidence.items():
                    all_conflicting_evidence[f"{strat}:{k}"] = v
            elif sig.direction == SignalDirection.NEUTRAL:
                neut_weight += weighted_score

        # 2. Determine Strongest Supporter and Opponent
        strongest_supporter = None
        strongest_opponent = None

        if bull_candidates:
            bull_candidates.sort(key=lambda s: s.confidence, reverse=True)
        if bear_candidates:
            bear_candidates.sort(key=lambda s: s.confidence, reverse=True)

        if bull_weight >= bear_weight:
            if bull_candidates:
                strongest_supporter = bull_candidates[0].strategy
            if bear_candidates:
                strongest_opponent = bear_candidates[0].strategy
        else:
            if bear_candidates:
                strongest_supporter = bear_candidates[0].strategy
            if bull_candidates:
                strongest_opponent = bull_candidates[0].strategy

        # 3. Calculate Conflict & Disagreement Scores
        total_directional = bull_weight + bear_weight
        if total_directional > 0:
            minority_weight = min(bull_weight, bear_weight)
            majority_weight = max(bull_weight, bear_weight)
            conflict_ratio = minority_weight / majority_weight
            conflict_score = min(100.0, conflict_ratio * 100.0)
            agreement_score = max(0.0, (majority_weight - minority_weight) / total_directional * 100.0)
            disagreement_score = 100.0 - agreement_score
        else:
            conflict_ratio = 0.0
            conflict_score = 0.0
            agreement_score = 0.0
            disagreement_score = 0.0

        # 4. Calculate Evidence Diversity Score
        evidence_diversity_score = self._calculate_evidence_diversity(bull_candidates if bull_weight >= bear_weight else bear_candidates)

        # 5. Check High-Confidence Opposition Penalty & Conflict State
        max_opposing_conf = 0.0
        if bull_weight >= bear_weight and bear_candidates:
            max_opposing_conf = bear_candidates[0].confidence
        elif bear_weight > bull_weight and bull_candidates:
            max_opposing_conf = bull_candidates[0].confidence

        opposition_penalty = 0.35 * conflict_ratio * max_opposing_conf

        # 6. Determine Direction & Consensus Strength
        num_participating = len(participating)
        direction = ConsensusDirection.NO_CONSENSUS
        strength = ConsensusStrength.NONE

        if num_participating == 0:
            direction = ConsensusDirection.NO_CONSENSUS
            strength = ConsensusStrength.NONE
        elif conflict_ratio >= 0.40 and max_opposing_conf >= 0.70:
            # High-confidence opposition -> CONFLICTED state
            direction = ConsensusDirection.CONFLICTED
            strength = ConsensusStrength.CONFLICTED
            logger.info(f"[CONSENSUS][{symbol}] High confidence opposition conflict detected (Ratio: {conflict_ratio:.2f}, MaxOpp: {max_opposing_conf:.2f})")
        elif bull_weight > bear_weight and bull_weight > neut_weight:
            direction = ConsensusDirection.BULLISH
            strength = self._classify_strength(num_participating, bull_weight, conflict_ratio)
        elif bear_weight > bull_weight and bear_weight > neut_weight:
            direction = ConsensusDirection.BEARISH
            strength = self._classify_strength(num_participating, bear_weight, conflict_ratio)
        elif neut_weight >= bull_weight and neut_weight >= bear_weight:
            direction = ConsensusDirection.NEUTRAL
            strength = ConsensusStrength.WEAK

        # 7. Compute Consensus Coverage & Participation Metrics
        expected_agents = self._get_expected_agent_count(overall_regime)
        participation_strength = min(1.0, num_participating / max(1, expected_agents)) if num_participating > 0 else 0.0
        consensus_coverage_score = min(100.0, participation_strength * 100.0)

        # 8. Compute Non-Diluting Final Consensus Confidence (0.00 to 1.00)
        # Denominator equals sum of max possible weights of participating eligible agents only
        quality_factor = max(0.2, mkt_quality / 100.0)
        participating_max_weight = sum(
            self.strategy_weights.get(a, 1.0) * self._get_regime_relevance(a, overall_regime) * quality_factor
            for a in participating
        )
        if participating_max_weight > 0:
            signal_strength = min(1.0, max(bull_weight, bear_weight) / participating_max_weight)
        else:
            signal_strength = 0.0

        normalized_conf = signal_strength * (agreement_score / 100.0) * max(0.5, regime_conf) * max(0.5, quality_factor)
        final_consensus_conf = max(0.00, min(1.00, normalized_conf - opposition_penalty))

        if direction == ConsensusDirection.CONFLICTED:
            final_consensus_conf = 0.0  # Zero out confidence for conflicted direction

        return ConsensusResult(
            consensus_id=cid,
            symbol=symbol,
            timestamp=ts,
            direction=direction,
            consensus_confidence=round(final_consensus_conf, 4),
            agreement_score=round(agreement_score, 1),
            disagreement_score=round(disagreement_score, 1),
            conflict_score=round(conflict_score, 1),
            bullish_weight=round(bull_weight, 4),
            bearish_weight=round(bear_weight, 4),
            neutral_weight=round(neut_weight, 4),
            participating_agents=participating,
            abstaining_agents=abstaining,
            rejected_agents=rejected,
            strongest_supporter=strongest_supporter,
            strongest_opponent=strongest_opponent,
            evidence_diversity_score=round(evidence_diversity_score, 1),
            signal_strength=round(signal_strength, 4),
            participation_strength=round(participation_strength, 4),
            consensus_coverage_score=round(consensus_coverage_score, 1),
            consensus_strength=strength,
            regime=overall_regime,
            regime_confidence=regime_conf,
            market_quality=mkt_quality,
            timeframe_alignment=mtf_align,
            supporting_evidence=all_supporting_evidence,
            conflicting_evidence=all_conflicting_evidence,
            consensus_status="VALID" if direction != ConsensusDirection.NO_CONSENSUS else "NO_SIGNAL",
            created_at=ts,
        )

    @staticmethod
    def _get_expected_agent_count(regime: str) -> int:
        """Returns the number of expected participating specialist agents for a given regime."""
        reg_upper = regime.upper()
        if reg_upper in ("STRONG_UPTREND", "UPTREND", "STRONG_DOWNTREND", "DOWNTREND"):
            return 3  # Trend, Momentum, Structure
        elif reg_upper == "RANGING":
            return 2  # MeanReversion, Structure
        elif "BREAKOUT" in reg_upper:
            return 3  # Breakout, Momentum, Structure
        return 1

    def _get_regime_relevance(self, strategy_name: str, regime: str) -> float:
        """Returns regime relevance multiplier (0.0 to 1.0)."""
        reg_upper = regime.upper()
        if reg_upper in ("STRONG_UPTREND", "UPTREND"):
            return 1.0 if strategy_name in ("CryptoTrendAgent", "CryptoMomentumAgent", "CryptoStructureAgent") else 0.0
        elif reg_upper in ("STRONG_DOWNTREND", "DOWNTREND"):
            return 1.0 if strategy_name in ("CryptoTrendAgent", "CryptoMomentumAgent", "CryptoStructureAgent") else 0.0
        elif reg_upper == "RANGING":
            return 1.0 if strategy_name in ("CryptoMeanReversionAgent", "CryptoStructureAgent") else 0.2
        elif "BREAKOUT" in reg_upper:
            return 1.0 if strategy_name in ("CryptoBreakoutAgent", "CryptoMomentumAgent", "CryptoStructureAgent") else 0.2
        elif reg_upper in ("CHOPPY", "UNCERTAIN"):
            return 0.1
        return 0.5

    def _calculate_evidence_diversity(self, supporting_candidates: List[StrategySignal]) -> float:
        """Calculates evidence diversity score (0 to 100) based on distinct feature families."""
        if not supporting_candidates:
            return 0.0

        families: Set[str] = set()
        for sig in supporting_candidates:
            for feat_key in sig.supporting_evidence.keys():
                family = FEATURE_FAMILY_MAP.get(feat_key, "OTHER")
                families.add(family)

        return min(100.0, len(families) * 25.0)

    def _classify_strength(self, num_participating: int, total_weight: float, conflict_ratio: float) -> ConsensusStrength:
        """Classifies consensus strength based on participant count, weight, and conflict ratio."""
        if num_participating == 1:
            return ConsensusStrength.SINGLE_SPECIALIST
        if conflict_ratio >= 0.35:
            return ConsensusStrength.WEAK
        if total_weight >= 1.5 and num_participating >= 3:
            return ConsensusStrength.VERY_STRONG
        elif total_weight >= 1.0 and num_participating >= 2:
            return ConsensusStrength.STRONG
        elif total_weight >= 0.6:
            return ConsensusStrength.MODERATE
        else:
            return ConsensusStrength.WEAK
