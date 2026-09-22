"""
Base Strategy Agent for Deriv Crypto AI Bot Stage 4.

Provides standardized base class, live data safety gate checks, error isolation,
confidence score calculation, tier assignment, and signal generation.
"""

from abc import ABC, abstractmethod
import logging
import time
from typing import Dict, Any, List, Optional, Tuple

from src.strategy.signal import (
    StrategySignal,
    SignalDirection,
    SignalStatus,
    SignalTier,
    RejectionReason,
)

logger = logging.getLogger("STRATEGY_AGENT")


class BaseStrategyAgent(ABC):
    """
    Abstract Base Class for Crypto Strategy Agents.
    
    All strategy agents must inherit from this class and implement `_evaluate_internal`.
    Includes strict exception isolation, global data safety checks, and tiering.
    """

    def __init__(self, name: str, primary_timeframe: str = "15m", timeframe_profile: Optional[List[str]] = None):
        self.name = name
        self.primary_timeframe = primary_timeframe
        self.timeframe_profile = timeframe_profile or [primary_timeframe]

    def evaluate(
        self,
        symbol: str,
        feature_snapshots: Dict[str, Dict[str, Any]],
        regime_snapshot: Dict[str, Any],
        structure_snapshot: Dict[str, Any],
        watcher_health: Dict[str, Any],
        allow_offline: bool = False,
    ) -> StrategySignal:
        """
        Public evaluation method with strict exception isolation and data safety gates.
        """
        timestamp = time.time()
        
        # 1. Global Data Safety Gate
        data_rejection = self.validate_data(symbol, feature_snapshots, watcher_health, allow_offline)
        if data_rejection is not None:
            return self.reject(
                symbol=symbol,
                timeframe=self.primary_timeframe,
                reason=data_rejection,
                regime=regime_snapshot.get("overall_regime", "UNCERTAIN"),
                regime_confidence=regime_snapshot.get("confidence", 0.0),
                market_quality=regime_snapshot.get("market_quality", 0.0),
                timeframe_alignment=regime_snapshot.get("alignment", 0.0),
                timestamp=timestamp,
            )

        # 2. Regime Readiness Check
        regime_rejection = self.validate_regime(regime_snapshot)
        if regime_rejection is not None:
            return self.reject(
                symbol=symbol,
                timeframe=self.primary_timeframe,
                reason=regime_rejection,
                regime=regime_snapshot.get("overall_regime", "UNCERTAIN"),
                regime_confidence=regime_snapshot.get("confidence", 0.0),
                market_quality=regime_snapshot.get("market_quality", 0.0),
                timeframe_alignment=regime_snapshot.get("alignment", 0.0),
                timestamp=timestamp,
            )

        # 3. Strategy Evaluation wrapped in isolated exception handling
        try:
            return self._evaluate_internal(
                symbol=symbol,
                feature_snapshots=feature_snapshots,
                regime_snapshot=regime_snapshot,
                structure_snapshot=structure_snapshot,
                watcher_health=watcher_health,
                timestamp=timestamp,
            )
        except Exception as err:
            logger.error(f"[{self.name}][{symbol}] Strategy evaluation exception: {err}", exc_info=True)
            return self.reject(
                symbol=symbol,
                timeframe=self.primary_timeframe,
                reason=RejectionReason.STRATEGY_EXCEPTION,
                regime=regime_snapshot.get("overall_regime", "UNCERTAIN"),
                regime_confidence=regime_snapshot.get("confidence", 0.0),
                market_quality=regime_snapshot.get("market_quality", 0.0),
                timeframe_alignment=regime_snapshot.get("alignment", 0.0),
                timestamp=timestamp,
                conflicting_evidence={"exception": 1.0},
            )

    @abstractmethod
    def _evaluate_internal(
        self,
        symbol: str,
        feature_snapshots: Dict[str, Dict[str, Any]],
        regime_snapshot: Dict[str, Any],
        structure_snapshot: Dict[str, Any],
        watcher_health: Dict[str, Any],
        timestamp: float,
    ) -> StrategySignal:
        """Subclasses must implement specific strategy logic here."""
        pass

    def validate_data(
        self,
        symbol: str,
        feature_snapshots: Dict[str, Dict[str, Any]],
        watcher_health: Dict[str, Any],
        allow_offline: bool = False,
    ) -> Optional[RejectionReason]:
        """
        Global Data Safety Gate.
        Rejects if watcher status is NO_DATA, STALE, DISCONNECTED, ERROR, HISTORY_ONLY (unless allow_offline=True).
        Also checks live tick freshness and feature snapshot readiness.
        """
        if not watcher_health:
            return RejectionReason.DATA_NOT_READY

        state = watcher_health.get("state", "NO_DATA")
        
        # Check explicit prohibited states
        if state == "HISTORY_ONLY" and not allow_offline:
            return RejectionReason.HISTORY_ONLY
        elif state in ("STALE", "DISCONNECTED") and not allow_offline:
            return RejectionReason.STALE_DATA
        elif state in ("NO_DATA", "ERROR", "SCANNING", "WARMING_UP") and not allow_offline:
            return RejectionReason.DATA_NOT_READY

        # Check live data freshness if not offline replay
        if not allow_offline:
            sec_since_tick = watcher_health.get("seconds_since_last_tick", 99999.0)
            if sec_since_tick > 120.0:  # Live data older than 2 minutes
                return RejectionReason.STALE_DATA

        # Check feature snapshot presence for primary timeframe
        primary_tf_features = feature_snapshots.get(self.primary_timeframe)
        if not primary_tf_features:
            return RejectionReason.INSUFFICIENT_DATA

        # Check minimum candles requirement (e.g., at least 30 candles)
        candle_count = primary_tf_features.get("candles_used", primary_tf_features.get("candle_count", 0))
        if candle_count < 30:
            return RejectionReason.INSUFFICIENT_DATA

        return None

    def validate_regime(self, regime_snapshot: Dict[str, Any]) -> Optional[RejectionReason]:
        """Check if regime snapshot is initialized and valid."""
        if not regime_snapshot:
            return RejectionReason.REGIME_NOT_READY
            
        overall_regime = regime_snapshot.get("overall_regime", "INSUFFICIENT_DATA")
        if overall_regime in ("INSUFFICIENT_DATA", "NOT_READY"):
            return RejectionReason.REGIME_NOT_READY

        return None

    def calculate_confidence(
        self,
        supporting_evidence: Dict[str, float],
        conflicting_evidence: Dict[str, float],
        base_confidence: float = 0.50,
    ) -> float:
        """
        Calculates strategy setup confidence score (0.00 to 1.00).
        Sums supporting evidence weights and subtracts conflicting penalties.
        """
        support_sum = sum(supporting_evidence.values())
        conflict_sum = sum(conflicting_evidence.values())

        raw_score = base_confidence + support_sum - conflict_sum
        return max(0.00, min(1.00, raw_score))

    def determine_tier(self, confidence: float, status: SignalStatus) -> SignalTier:
        """Maps setup confidence to analytical SignalTier."""
        if status != SignalStatus.CANDIDATE:
            return SignalTier.REJECT
        if confidence >= 0.75:
            return SignalTier.A
        elif confidence >= 0.55:
            return SignalTier.B
        elif confidence >= 0.40:
            return SignalTier.C
        else:
            return SignalTier.REJECT

    def build_signal(
        self,
        symbol: str,
        direction: SignalDirection,
        confidence: float,
        regime: str,
        regime_confidence: float,
        market_quality: float,
        timeframe_alignment: float,
        timeframe: Optional[str] = None,
        entry_context: Optional[Dict[str, Any]] = None,
        invalidation_context: Optional[Dict[str, Any]] = None,
        supporting_evidence: Optional[Dict[str, float]] = None,
        conflicting_evidence: Optional[Dict[str, float]] = None,
        feature_snapshot_timestamp: float = 0.0,
        data_quality: float = 1.0,
        status: SignalStatus = SignalStatus.CANDIDATE,
        rejection_reason: Optional[RejectionReason] = None,
        timestamp: Optional[float] = None,
        source_candle_timestamp: Optional[float] = None,
        cooldown_seconds: float = 300.0,
    ) -> StrategySignal:
        """Constructs a standardized StrategySignal object."""
        ts = timestamp or time.time()
        tf = timeframe or self.primary_timeframe
        sig_id = StrategySignal.create_id(symbol, self.name, tf, ts)
        tier = self.determine_tier(confidence, status)

        return StrategySignal(
            signal_id=sig_id,
            symbol=symbol,
            strategy=self.name,
            timestamp=ts,
            timeframe=tf,
            direction=direction,
            confidence=round(confidence, 4),
            regime=regime,
            regime_confidence=round(regime_confidence, 4),
            market_quality=round(market_quality, 4),
            timeframe_alignment=round(timeframe_alignment, 4),
            entry_context=entry_context or {},
            invalidation_context=invalidation_context or {},
            supporting_evidence=supporting_evidence or {},
            conflicting_evidence=conflicting_evidence or {},
            feature_snapshot_timestamp=feature_snapshot_timestamp,
            data_quality=data_quality,
            status=status,
            rejection_reason=rejection_reason,
            tier=tier,
            created_at=ts,
            expires_at=ts + cooldown_seconds if status == SignalStatus.CANDIDATE else ts + 60.0,
            source_candle_timestamp=source_candle_timestamp,
        )

    def abstain(
        self,
        symbol: str,
        timeframe: str,
        regime: str,
        regime_confidence: float,
        market_quality: float,
        timeframe_alignment: float,
        reason: Optional[RejectionReason] = None,
        supporting_evidence: Optional[Dict[str, float]] = None,
        conflicting_evidence: Optional[Dict[str, float]] = None,
        timestamp: Optional[float] = None,
    ) -> StrategySignal:
        """Helper to create an ABSTAIN signal."""
        return self.build_signal(
            symbol=symbol,
            direction=SignalDirection.ABSTAIN,
            confidence=0.0,
            regime=regime,
            regime_confidence=regime_confidence,
            market_quality=market_quality,
            timeframe_alignment=timeframe_alignment,
            timeframe=timeframe,
            supporting_evidence=supporting_evidence,
            conflicting_evidence=conflicting_evidence,
            status=SignalStatus.ABSTAINED,
            rejection_reason=reason,
            timestamp=timestamp,
        )

    def reject(
        self,
        symbol: str,
        timeframe: str,
        reason: RejectionReason,
        regime: str,
        regime_confidence: float,
        market_quality: float,
        timeframe_alignment: float,
        supporting_evidence: Optional[Dict[str, float]] = None,
        conflicting_evidence: Optional[Dict[str, float]] = None,
        timestamp: Optional[float] = None,
    ) -> StrategySignal:
        """Helper to create a REJECTED signal."""
        return self.build_signal(
            symbol=symbol,
            direction=SignalDirection.ABSTAIN,
            confidence=0.0,
            regime=regime,
            regime_confidence=regime_confidence,
            market_quality=market_quality,
            timeframe_alignment=timeframe_alignment,
            timeframe=timeframe,
            supporting_evidence=supporting_evidence,
            conflicting_evidence=conflicting_evidence,
            status=SignalStatus.REJECTED,
            rejection_reason=reason,
            timestamp=timestamp,
        )
