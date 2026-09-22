"""
Crypto Breakout Agent for Deriv Crypto AI Bot Stage 4.

Purpose: Identify potential breakout environments and candidates.
Tracks two phases:
  1. COMPRESSION (volatility contraction, tight Bollinger width)
  2. BREAKOUT CANDIDATE (volatility expansion, price beyond S/R or Bollinger band, momentum confirmation)

Stores context metrics: compression_score, breakout_strength, distance_from_breakout_level.
"""

from typing import Dict, Any, List, Optional
from src.agents.base_strategy_agent import BaseStrategyAgent
from src.strategy.signal import (
    StrategySignal,
    SignalDirection,
    SignalStatus,
    RejectionReason,
)


class CryptoBreakoutAgent(BaseStrategyAgent):

    def __init__(self, primary_timeframe: str = "15m", timeframe_profile: Optional[List[str]] = None):
        profile = timeframe_profile or ["1m", "5m", "15m"]
        super().__init__(name="CryptoBreakoutAgent", primary_timeframe=primary_timeframe, timeframe_profile=profile)

    def _evaluate_internal(
        self,
        symbol: str,
        feature_snapshots: Dict[str, Dict[str, Any]],
        regime_snapshot: Dict[str, Any],
        structure_snapshot: Dict[str, Any],
        watcher_health: Dict[str, Any],
        timestamp: float,
    ) -> StrategySignal:
        features = feature_snapshots.get(self.primary_timeframe, {})
        overall_regime = regime_snapshot.get("overall_regime", "UNCERTAIN")
        regime_conf = regime_snapshot.get("confidence", 0.0)
        mkt_quality = regime_snapshot.get("market_quality", 0.0)
        mtf_align = regime_snapshot.get("alignment", 0.0)

        price = features.get("price", 0.0)
        bb_upper = features.get("bollinger_upper", 0.0)
        bb_lower = features.get("bollinger_lower", 0.0)
        bb_width = features.get("bollinger_width", 0.0)
        atr_pct = features.get("atr_percent", 0.0)
        volatility = features.get("rolling_volatility", 0.0)
        roc = features.get("roc", 0.0)

        resistance = structure_snapshot.get("resistance_level", bb_upper)
        support = structure_snapshot.get("support_level", bb_lower)

        # 1. Compute compression score (0.0 to 1.0)
        # Tight Bollinger width (< 0.03 or 3%) indicates compression
        compression_score = max(0.0, min(1.0, (0.05 - bb_width) / 0.04)) if bb_width > 0 else 0.5

        # 2. Check Bullish Breakout Candidate
        bull_supporting: Dict[str, float] = {}
        bull_conflicting: Dict[str, float] = {}

        dist_res_pct = ((price - resistance) / resistance * 100.0) if resistance > 0 else 0.0
        dist_bb_upper_pct = ((price - bb_upper) / bb_upper * 100.0) if bb_upper > 0 else 0.0

        if price >= resistance or price >= bb_upper:
            bull_supporting["price_above_breakout_level"] = 0.25
        elif dist_res_pct >= -0.2:  # within 0.2% of resistance
            bull_supporting["price_at_breakout_threshold"] = 0.15
        else:
            bull_conflicting["price_below_resistance"] = 0.20

        if compression_score >= 0.4:
            bull_supporting["prior_compression"] = 0.20
        else:
            bull_conflicting["no_prior_compression"] = 0.10

        if roc > 0.4:
            bull_supporting["breakout_momentum_confirmation"] = 0.20
        else:
            bull_conflicting["weak_breakout_momentum"] = 0.15

        if volatility > 0.2 or atr_pct > 0.5:
            bull_supporting["volatility_expansion"] = 0.15

        # 3. Check Bearish Breakout Candidate
        bear_supporting: Dict[str, float] = {}
        bear_conflicting: Dict[str, float] = {}

        dist_supp_pct = ((support - price) / support * 100.0) if support > 0 else 0.0

        if price <= support or price <= bb_lower:
            bear_supporting["price_below_breakout_level"] = 0.25
        elif dist_supp_pct >= -0.2:
            bear_supporting["price_at_breakout_threshold"] = 0.15
        else:
            bear_conflicting["price_above_support"] = 0.20

        if compression_score >= 0.4:
            bear_supporting["prior_compression"] = 0.20
        else:
            bear_conflicting["no_prior_compression"] = 0.10

        if roc < -0.4:
            bear_supporting["breakout_momentum_confirmation"] = 0.20
        else:
            bear_conflicting["weak_breakout_momentum"] = 0.15

        if volatility > 0.2 or atr_pct > 0.5:
            bear_supporting["volatility_expansion"] = 0.15

        # 4. Compute confidence & candidate status
        bull_conf = self.calculate_confidence(bull_supporting, bull_conflicting, base_confidence=0.10)
        bear_conf = self.calculate_confidence(bear_supporting, bear_conflicting, base_confidence=0.10)

        breakout_strength = max(bull_conf, bear_conf)

        if bull_conf >= 0.50 and bull_conf > bear_conf:
            return self.build_signal(
                symbol=symbol,
                direction=SignalDirection.BULLISH,
                confidence=bull_conf,
                regime=overall_regime,
                regime_confidence=regime_conf,
                market_quality=mkt_quality,
                timeframe_alignment=mtf_align,
                entry_context={
                    "breakout_level": resistance,
                    "compression_score": round(compression_score, 4),
                    "breakout_strength": round(breakout_strength, 4),
                    "distance_from_breakout_level": round(dist_res_pct, 4),
                },
                invalidation_context={"stop_level": (price + resistance) / 2.0},
                supporting_evidence=bull_supporting,
                conflicting_evidence=bull_conflicting,
                feature_snapshot_timestamp=features.get("timestamp", 0),
                status=SignalStatus.CANDIDATE,
                timestamp=timestamp,
                source_candle_timestamp=features.get("timestamp"),
            )
        elif bear_conf >= 0.50 and bear_conf > bull_conf:
            return self.build_signal(
                symbol=symbol,
                direction=SignalDirection.BEARISH,
                confidence=bear_conf,
                regime=overall_regime,
                regime_confidence=regime_conf,
                market_quality=mkt_quality,
                timeframe_alignment=mtf_align,
                entry_context={
                    "breakout_level": support,
                    "compression_score": round(compression_score, 4),
                    "breakout_strength": round(breakout_strength, 4),
                    "distance_from_breakout_level": round(dist_supp_pct, 4),
                },
                invalidation_context={"stop_level": (price + support) / 2.0},
                supporting_evidence=bear_supporting,
                conflicting_evidence=bear_conflicting,
                feature_snapshot_timestamp=features.get("timestamp", 0),
                status=SignalStatus.CANDIDATE,
                timestamp=timestamp,
                source_candle_timestamp=features.get("timestamp"),
            )

        return self.abstain(
            symbol=symbol,
            timeframe=self.primary_timeframe,
            regime=overall_regime,
            regime_confidence=regime_conf,
            market_quality=mkt_quality,
            timeframe_alignment=mtf_align,
            reason=RejectionReason.NO_BREAKOUT,
            supporting_evidence=bull_supporting if bull_conf > bear_conf else bear_supporting,
            conflicting_evidence=bull_conflicting if bull_conf > bear_conf else bear_conflicting,
            timestamp=timestamp,
        )
