"""
Crypto Mean Reversion Agent for Deriv Crypto AI Bot Stage 4.

Purpose: Identify potential reversion opportunities inside suitable ranging regimes.
Aggressively ABSTAINS during STRONG_UPTREND / STRONG_DOWNTREND unless explicitly allowed.
Does NOT assume oversold = bullish or overbought = bearish; looks for evidence of exhaustion/rejection.
"""

from typing import Dict, Any, List, Optional
from src.agents.base_strategy_agent import BaseStrategyAgent
from src.strategy.signal import (
    StrategySignal,
    SignalDirection,
    SignalStatus,
    RejectionReason,
)


class CryptoMeanReversionAgent(BaseStrategyAgent):

    def __init__(self, primary_timeframe: str = "15m", timeframe_profile: Optional[List[str]] = None):
        profile = timeframe_profile or ["5m", "15m"]
        super().__init__(name="CryptoMeanReversionAgent", primary_timeframe=primary_timeframe, timeframe_profile=profile)

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

        # 1. Aggressive Abstain during strong trending regimes
        if overall_regime in ("STRONG_UPTREND", "STRONG_DOWNTREND"):
            return self.abstain(
                symbol=symbol,
                timeframe=self.primary_timeframe,
                regime=overall_regime,
                regime_confidence=regime_conf,
                market_quality=mkt_quality,
                timeframe_alignment=mtf_align,
                reason=RejectionReason.REGIME_MISMATCH,
                timestamp=timestamp,
            )

        price = features.get("price", 0.0)
        b_pos = features.get("bollinger_position", 0.5)  # 0.0 = lower band, 1.0 = upper band
        rsi = features.get("rsi", 50.0)
        dist_fast = features.get("distance_from_fast_ema", 0.0)
        dist_slow = features.get("distance_from_slow_ema", 0.0)
        roc = features.get("roc", 0.0)
        b_mid = features.get("bollinger_middle", price)

        support = structure_snapshot.get("support_level", 0.0)
        resistance = structure_snapshot.get("resistance_level", 0.0)

        # 2. Bullish Reversion Setup (Price at lower range/band, showing exhaustion)
        bull_supporting: Dict[str, float] = {}
        bull_conflicting: Dict[str, float] = {}

        if b_pos <= 0.15:
            bull_supporting["bollinger_lower_band_touch"] = 0.25
        elif b_pos <= 0.30:
            bull_supporting["near_lower_bollinger_band"] = 0.15
        else:
            bull_conflicting["not_at_lower_band"] = 0.20

        if rsi <= 35.0:
            bull_supporting["rsi_range_exhaustion"] = 0.20
        elif rsi <= 42.0:
            bull_supporting["mild_rsi_oversold"] = 0.10
        else:
            bull_conflicting["rsi_not_oversold"] = 0.15

        if dist_fast < -1.0 or dist_slow < -2.0:
            bull_supporting["stretched_below_ma"] = 0.15
        else:
            bull_conflicting["price_near_ma"] = 0.10

        # Look for momentum deceleration (roc turning positive or zero)
        if -1.0 <= roc <= 0.5:
            bull_supporting["downward_momentum_deceleration"] = 0.15
        elif roc < -2.0:
            bull_conflicting["strong_downward_momentum"] = 0.25

        # 3. Bearish Reversion Setup (Price at upper range/band, showing exhaustion)
        bear_supporting: Dict[str, float] = {}
        bear_conflicting: Dict[str, float] = {}

        if b_pos >= 0.85:
            bear_supporting["bollinger_upper_band_touch"] = 0.25
        elif b_pos >= 0.70:
            bear_supporting["near_upper_bollinger_band"] = 0.15
        else:
            bear_conflicting["not_at_upper_band"] = 0.20

        if rsi >= 65.0:
            bear_supporting["rsi_range_exhaustion"] = 0.20
        elif rsi >= 58.0:
            bear_supporting["mild_rsi_overbought"] = 0.10
        else:
            bear_conflicting["rsi_not_overbought"] = 0.15

        if dist_fast > 1.0 or dist_slow > 2.0:
            bear_supporting["stretched_above_ma"] = 0.15
        else:
            bear_conflicting["price_near_ma"] = 0.10

        if -0.5 <= roc <= 1.0:
            bear_supporting["upward_momentum_deceleration"] = 0.15
        elif roc > 2.0:
            bear_conflicting["strong_upward_momentum"] = 0.25

        # 4. Evaluate Setup Confidence
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
                entry_context={"bollinger_position": b_pos, "rsi": rsi, "target": b_mid},
                invalidation_context={"stop_level": support * 0.99 if support > 0 else price * 0.98},
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
                entry_context={"bollinger_position": b_pos, "rsi": rsi, "target": b_mid},
                invalidation_context={"stop_level": resistance * 1.01 if resistance > 0 else price * 1.02},
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
            reason=RejectionReason.NO_RANGE,
            supporting_evidence=bull_supporting if bull_conf > bear_conf else bear_supporting,
            conflicting_evidence=bull_conflicting if bull_conf > bear_conf else bear_conflicting,
            timestamp=timestamp,
        )
