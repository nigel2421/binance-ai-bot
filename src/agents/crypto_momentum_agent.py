"""
Crypto Momentum Agent for Deriv Crypto AI Bot Stage 4.

Purpose: Detect directional acceleration or continuation.
Uses RSI behavior, MACD histogram & delta, ROC, price acceleration, ATR, structure.
Does NOT use naive RSI > 70 SELL / RSI < 30 BUY reversals.
"""

from typing import Dict, Any, List, Optional
from src.agents.base_strategy_agent import BaseStrategyAgent
from src.strategy.signal import (
    StrategySignal,
    SignalDirection,
    SignalStatus,
    RejectionReason,
)


class CryptoMomentumAgent(BaseStrategyAgent):

    def __init__(self, primary_timeframe: str = "15m", timeframe_profile: Optional[List[str]] = None):
        profile = timeframe_profile or ["5m", "15m", "30m"]
        super().__init__(name="CryptoMomentumAgent", primary_timeframe=primary_timeframe, timeframe_profile=profile)

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

        rsi = features.get("rsi", 50.0)
        macd_hist = features.get("macd_histogram", 0.0)
        macd = features.get("macd", 0.0)
        macd_sig = features.get("macd_signal", 0.0)
        roc = features.get("roc", 0.0)
        atr_pct = features.get("atr_percent", 0.0)
        trend_slope = features.get("trend_slope", 0.0)

        # 1. Evaluate Bullish Momentum Continuation
        bull_supporting: Dict[str, float] = {}
        bull_conflicting: Dict[str, float] = {}

        if 50.0 <= rsi <= 75.0:
            bull_supporting["healthy_bullish_rsi"] = 0.20
        elif rsi > 75.0:
            bull_supporting["strong_bullish_rsi"] = 0.15
            bull_conflicting["extreme_rsi_warning"] = 0.05
        else:
            bull_conflicting["rsi_below_50"] = 0.20

        if macd_hist > 0:
            bull_supporting["positive_macd_hist"] = 0.20
            if macd > macd_sig:
                bull_supporting["macd_line_above_signal"] = 0.10
        else:
            bull_conflicting["negative_macd_hist"] = 0.20

        if roc > 0.5:
            bull_supporting["positive_roc_acceleration"] = 0.20
        elif roc > 0:
            bull_supporting["slight_positive_roc"] = 0.10
        else:
            bull_conflicting["negative_roc"] = 0.15

        if trend_slope > 0.02:
            bull_supporting["positive_slope"] = 0.10

        # 2. Evaluate Bearish Momentum Continuation
        bear_supporting: Dict[str, float] = {}
        bear_conflicting: Dict[str, float] = {}

        if 25.0 <= rsi <= 50.0:
            bear_supporting["healthy_bearish_rsi"] = 0.20
        elif rsi < 25.0:
            bear_supporting["strong_bearish_rsi"] = 0.15
            bear_conflicting["extreme_rsi_warning"] = 0.05
        else:
            bear_conflicting["rsi_above_50"] = 0.20

        if macd_hist < 0:
            bear_supporting["negative_macd_hist"] = 0.20
            if macd < macd_sig:
                bear_supporting["macd_line_below_signal"] = 0.10
        else:
            bear_conflicting["positive_macd_hist"] = 0.20

        if roc < -0.5:
            bear_supporting["negative_roc_acceleration"] = 0.20
        elif roc < 0:
            bear_supporting["slight_negative_roc"] = 0.10
        else:
            bear_conflicting["positive_roc"] = 0.15

        if trend_slope < -0.02:
            bear_supporting["negative_slope"] = 0.10

        # 3. Direction decision
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
                entry_context={"rsi": rsi, "macd_histogram": macd_hist, "roc": roc},
                invalidation_context={"invalidation_rsi": 45.0},
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
                entry_context={"rsi": rsi, "macd_histogram": macd_hist, "roc": roc},
                invalidation_context={"invalidation_rsi": 55.0},
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
            reason=RejectionReason.WEAK_MOMENTUM,
            supporting_evidence=bull_supporting if bull_conf > bear_conf else bear_supporting,
            conflicting_evidence=bull_conflicting if bull_conf > bear_conf else bear_conflicting,
            timestamp=timestamp,
        )
