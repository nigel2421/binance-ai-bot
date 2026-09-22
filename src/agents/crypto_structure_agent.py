"""
Crypto Market Structure Agent for Deriv Crypto AI Bot Stage 4.

Purpose: Interpret price structure rather than traditional indicator combinations.
Uses higher highs, higher lows, lower highs, lower lows, support, resistance, swing points,
structure breaks, trend continuation, structure failure.

Internal States:
  - BULLISH_CONTINUATION
  - BEARISH_CONTINUATION
  - BULLISH_BREAK_STRUCTURE
  - BEARISH_BREAK_STRUCTURE
  - RANGE_STRUCTURE
  - STRUCTURE_UNCLEAR
Converts internal states into standardized StrategySignal objects.
"""

from typing import Dict, Any, List, Optional
from src.agents.base_strategy_agent import BaseStrategyAgent
from src.strategy.signal import (
    StrategySignal,
    SignalDirection,
    SignalStatus,
    RejectionReason,
)


class CryptoStructureAgent(BaseStrategyAgent):

    def __init__(self, primary_timeframe: str = "15m", timeframe_profile: Optional[List[str]] = None):
        profile = timeframe_profile or ["15m", "30m", "1h"]
        super().__init__(name="CryptoStructureAgent", primary_timeframe=primary_timeframe, timeframe_profile=profile)

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

        hh_count = structure_snapshot.get("higher_highs_count", 0)
        hl_count = structure_snapshot.get("higher_lows_count", 0)
        lh_count = structure_snapshot.get("lower_highs_count", 0)
        ll_count = structure_snapshot.get("lower_lows_count", 0)
        support = structure_snapshot.get("support_level", 0.0)
        resistance = structure_snapshot.get("resistance_level", 0.0)
        local_high = structure_snapshot.get("local_swing_high", 0.0)
        local_low = structure_snapshot.get("local_swing_low", 0.0)
        base_state = structure_snapshot.get("structure_state", "UNCLEAR_STRUCTURE")

        # 1. Determine Internal Structural State
        internal_state = "STRUCTURE_UNCLEAR"
        if base_state == "BULLISH_STRUCTURE" or (hh_count > 2 and hl_count > 2):
            if price > local_high * 0.999:
                internal_state = "BULLISH_BREAK_STRUCTURE"
            else:
                internal_state = "BULLISH_CONTINUATION"
        elif base_state == "BEARISH_STRUCTURE" or (lh_count > 2 and ll_count > 2):
            if price < local_low * 1.001:
                internal_state = "BEARISH_BREAK_STRUCTURE"
            else:
                internal_state = "BEARISH_CONTINUATION"
        elif base_state == "RANGING_STRUCTURE":
            internal_state = "RANGE_STRUCTURE"

        # 2. Bullish Evidence
        bull_supporting: Dict[str, float] = {}
        bull_conflicting: Dict[str, float] = {}

        if internal_state == "BULLISH_BREAK_STRUCTURE":
            bull_supporting["break_of_structure_bullish"] = 0.30
        elif internal_state == "BULLISH_CONTINUATION":
            bull_supporting["bullish_hh_hl_sequence"] = 0.25

        if hh_count > lh_count:
            bull_supporting["higher_highs_dominance"] = 0.15
        else:
            bull_conflicting["lower_highs_present"] = 0.15

        if hl_count > ll_count:
            bull_supporting["higher_lows_dominance"] = 0.15
        else:
            bull_conflicting["lower_lows_present"] = 0.15

        if support > 0 and price > support:
            bull_supporting["price_holding_above_support"] = 0.15

        # 3. Bearish Evidence
        bear_supporting: Dict[str, float] = {}
        bear_conflicting: Dict[str, float] = {}

        if internal_state == "BEARISH_BREAK_STRUCTURE":
            bear_supporting["break_of_structure_bearish"] = 0.30
        elif internal_state == "BEARISH_CONTINUATION":
            bear_supporting["bearish_lh_ll_sequence"] = 0.25

        if lh_count > hh_count:
            bear_supporting["lower_highs_dominance"] = 0.15
        else:
            bear_conflicting["higher_highs_present"] = 0.15

        if ll_count > hl_count:
            bear_supporting["lower_lows_dominance"] = 0.15
        else:
            bear_conflicting["higher_lows_present"] = 0.15

        if resistance > 0 and price < resistance:
            bear_supporting["price_holding_below_resistance"] = 0.15

        # 4. Confidence & Signal creation
        bull_conf = self.calculate_confidence(bull_supporting, bull_conflicting, base_confidence=0.10)
        bear_conf = self.calculate_confidence(bear_supporting, bear_conflicting, base_confidence=0.10)

        if bull_conf >= 0.45 and bull_conf > bear_conf:
            return self.build_signal(
                symbol=symbol,
                direction=SignalDirection.BULLISH,
                confidence=bull_conf,
                regime=overall_regime,
                regime_confidence=regime_conf,
                market_quality=mkt_quality,
                timeframe_alignment=mtf_align,
                entry_context={
                    "internal_structure_state": internal_state,
                    "support_level": support,
                    "resistance_level": resistance,
                },
                invalidation_context={"stop_level": local_low if local_low > 0 else support},
                supporting_evidence=bull_supporting,
                conflicting_evidence=bull_conflicting,
                feature_snapshot_timestamp=features.get("timestamp", 0),
                status=SignalStatus.CANDIDATE,
                timestamp=timestamp,
                source_candle_timestamp=features.get("timestamp"),
            )
        elif bear_conf >= 0.45 and bear_conf > bull_conf:
            return self.build_signal(
                symbol=symbol,
                direction=SignalDirection.BEARISH,
                confidence=bear_conf,
                regime=overall_regime,
                regime_confidence=regime_conf,
                market_quality=mkt_quality,
                timeframe_alignment=mtf_align,
                entry_context={
                    "internal_structure_state": internal_state,
                    "support_level": support,
                    "resistance_level": resistance,
                },
                invalidation_context={"stop_level": local_high if local_high > 0 else resistance},
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
            reason=RejectionReason.STRUCTURE_UNCLEAR,
            supporting_evidence=bull_supporting if bull_conf > bear_conf else bear_supporting,
            conflicting_evidence=bull_conflicting if bull_conf > bear_conf else bear_conflicting,
            timestamp=timestamp,
        )
