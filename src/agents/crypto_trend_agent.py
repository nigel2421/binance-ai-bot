"""
Crypto Trend Agent for Deriv Crypto AI Bot Stage 4.

Purpose: Find continuation opportunities within established directional trends.
Uses EMA alignment (9/21/50), slopes, ADX, +/-DI, market structure, ROC, MTF regime alignment.
Does NOT force candidates during CHOPPY / UNCERTAIN regimes.
"""

from typing import Dict, Any, List, Optional
from src.agents.base_strategy_agent import BaseStrategyAgent
from src.strategy.signal import (
    StrategySignal,
    SignalDirection,
    SignalStatus,
    RejectionReason,
)


class CryptoTrendAgent(BaseStrategyAgent):

    def __init__(self, primary_timeframe: str = "15m", timeframe_profile: Optional[List[str]] = None):
        profile = timeframe_profile or ["15m", "30m", "1h"]
        super().__init__(name="CryptoTrendAgent", primary_timeframe=primary_timeframe, timeframe_profile=profile)

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

        # 1. Reject if regime is unsuitable
        if overall_regime in ("CHOPPY", "UNCERTAIN", "RANGING"):
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
        ema_fast = features.get("ema_fast", 0.0)
        ema_med = features.get("ema_medium", 0.0)
        ema_slow = features.get("ema_slow", 0.0)
        trend_slope = features.get("trend_slope", 0.0)
        adx = features.get("adx", 0.0)
        plus_di = features.get("plus_di", 0.0)
        minus_di = features.get("minus_di", 0.0)
        roc = features.get("roc", 0.0)
        structure_state = structure_snapshot.get("structure_state", "UNCLEAR_STRUCTURE")

        supporting: Dict[str, float] = {}
        conflicting: Dict[str, float] = {}

        # 2. Bullish Trend Evidence
        bullish_score = 0.0
        if ema_fast > ema_med > ema_slow:
            supporting["ema_alignment"] = 0.20
            bullish_score += 0.20
        elif ema_fast > ema_slow:
            supporting["partial_ema_alignment"] = 0.10
            bullish_score += 0.10
        else:
            conflicting["ema_alignment"] = 0.15

        if price > ema_fast:
            supporting["price_above_fast_ema"] = 0.10
            bullish_score += 0.10
        else:
            conflicting["price_below_fast_ema"] = 0.10

        if trend_slope > 0.05:
            supporting["positive_trend_slope"] = 0.15
            bullish_score += 0.15
        elif trend_slope < -0.05:
            conflicting["negative_trend_slope"] = 0.15

        if adx >= 20.0:
            supporting["adx_strength"] = 0.15
            bullish_score += 0.15
            if plus_di > minus_di:
                supporting["plus_di_domination"] = 0.10
                bullish_score += 0.10
            else:
                conflicting["minus_di_domination"] = 0.15
        else:
            conflicting["weak_adx"] = 0.10

        if structure_state == "BULLISH_STRUCTURE":
            supporting["bullish_structure"] = 0.15
            bullish_score += 0.15
        elif structure_state == "BEARISH_STRUCTURE":
            conflicting["bearish_structure"] = 0.20

        if mtf_align > 0.5:
            supporting["mtf_alignment"] = 0.15
            bullish_score += 0.15
        elif mtf_align < -0.2:
            conflicting["mtf_conflict"] = 0.15

        if roc > 0:
            supporting["positive_roc"] = 0.05
        else:
            conflicting["negative_roc"] = 0.05

        # 3. Bearish Trend Evidence
        bearish_score = 0.0
        bear_supporting: Dict[str, float] = {}
        bear_conflicting: Dict[str, float] = {}

        if ema_fast < ema_med < ema_slow:
            bear_supporting["ema_alignment"] = 0.20
            bearish_score += 0.20
        elif ema_fast < ema_slow:
            bear_supporting["partial_ema_alignment"] = 0.10
            bearish_score += 0.10
        else:
            bear_conflicting["ema_alignment"] = 0.15

        if price < ema_fast:
            bear_supporting["price_below_fast_ema"] = 0.10
            bearish_score += 0.10
        else:
            bear_conflicting["price_above_fast_ema"] = 0.10

        if trend_slope < -0.05:
            bear_supporting["negative_trend_slope"] = 0.15
            bearish_score += 0.15
        elif trend_slope > 0.05:
            bear_conflicting["positive_trend_slope"] = 0.15

        if adx >= 20.0:
            bear_supporting["adx_strength"] = 0.15
            bearish_score += 0.15
            if minus_di > plus_di:
                bear_supporting["minus_di_domination"] = 0.10
                bearish_score += 0.10
            else:
                bear_conflicting["plus_di_domination"] = 0.15
        else:
            bear_conflicting["weak_adx"] = 0.10

        if structure_state == "BEARISH_STRUCTURE":
            bear_supporting["bearish_structure"] = 0.15
            bearish_score += 0.15
        elif structure_state == "BULLISH_STRUCTURE":
            bear_conflicting["bullish_structure"] = 0.20

        if mtf_align < -0.5:
            bear_supporting["mtf_alignment"] = 0.15
            bearish_score += 0.15
        elif mtf_align > 0.2:
            bear_conflicting["mtf_conflict"] = 0.15

        if roc < 0:
            bear_supporting["negative_roc"] = 0.05
        else:
            bear_conflicting["positive_roc"] = 0.05

        # 4. Determine direction and calculate setup confidence
        if overall_regime in ("STRONG_UPTREND", "UPTREND") and bullish_score >= 0.40:
            confidence = self.calculate_confidence(supporting, conflicting, base_confidence=0.10)
            if confidence >= 0.40:
                return self.build_signal(
                    symbol=symbol,
                    direction=SignalDirection.BULLISH,
                    confidence=confidence,
                    regime=overall_regime,
                    regime_confidence=regime_conf,
                    market_quality=mkt_quality,
                    timeframe_alignment=mtf_align,
                    entry_context={"ema_fast": ema_fast, "ema_slow": ema_slow, "slope": trend_slope},
                    invalidation_context={"stop_level": ema_slow},
                    supporting_evidence=supporting,
                    conflicting_evidence=conflicting,
                    feature_snapshot_timestamp=features.get("timestamp", 0),
                    status=SignalStatus.CANDIDATE,
                    timestamp=timestamp,
                    source_candle_timestamp=features.get("timestamp"),
                )
        elif overall_regime in ("STRONG_DOWNTREND", "DOWNTREND") and bearish_score >= 0.40:
            confidence = self.calculate_confidence(bear_supporting, bear_conflicting, base_confidence=0.10)
            if confidence >= 0.40:
                return self.build_signal(
                    symbol=symbol,
                    direction=SignalDirection.BEARISH,
                    confidence=confidence,
                    regime=overall_regime,
                    regime_confidence=regime_conf,
                    market_quality=mkt_quality,
                    timeframe_alignment=mtf_align,
                    entry_context={"ema_fast": ema_fast, "ema_slow": ema_slow, "slope": trend_slope},
                    invalidation_context={"stop_level": ema_slow},
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
            reason=RejectionReason.WEAK_TREND,
            supporting_evidence=supporting if bullish_score > bearish_score else bear_supporting,
            conflicting_evidence=conflicting if bullish_score > bearish_score else bear_conflicting,
            timestamp=timestamp,
        )
