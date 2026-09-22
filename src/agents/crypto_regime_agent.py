import logging
import time
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

from src.config import config
from src.features.crypto_feature_engine import CryptoFeatureEngine, MarketFeatureSnapshot
from src.features.market_structure import MarketStructureEngine, MarketStructureSnapshot

logger = logging.getLogger("REGIME")

class TrendSnapshot:
    def __init__(self, direction: str = "NEUTRAL", strength: float = 0.0):
        self.direction = direction  # STRONG_BULLISH, BULLISH, NEUTRAL, BEARISH, STRONG_BEARISH
        self.strength = float(strength)  # 0 to 100

class MomentumSnapshot:
    def __init__(self, state: str = "NEUTRAL", strength: float = 0.0):
        self.state = state  # STRONG_POSITIVE, POSITIVE, NEUTRAL, NEGATIVE, STRONG_NEGATIVE
        self.strength = float(strength)  # 0 to 100

class VolatilitySnapshot:
    def __init__(self, level: str = "NORMAL", state: str = "STABLE"):
        self.level = level  # VERY_LOW, LOW, NORMAL, HIGH, EXTREME
        self.state = state  # EXPANDING, STABLE, CONTRACTING

class SingleTimeframeRegimeResult:
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        raw_regime: str = "INSUFFICIENT_DATA",
        confirmed_regime: str = "INSUFFICIENT_DATA",
        confidence: float = 0.0,
        trend: Optional[TrendSnapshot] = None,
        momentum: Optional[MomentumSnapshot] = None,
        volatility: Optional[VolatilitySnapshot] = None,
        market_structure: str = "UNCLEAR_STRUCTURE",
        supporting_features: Optional[List[str]] = None,
        conflicting_features: Optional[List[str]] = None,
        timestamp: int = 0
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.raw_regime = raw_regime
        self.confirmed_regime = confirmed_regime
        self.confidence = float(confidence)
        self.trend = trend or TrendSnapshot()
        self.momentum = momentum or MomentumSnapshot()
        self.volatility = volatility or VolatilitySnapshot()
        self.market_structure = market_structure
        self.supporting_features = supporting_features or []
        self.conflicting_features = conflicting_features or []
        self.timestamp = timestamp or int(time.time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "raw_regime": self.raw_regime,
            "confirmed_regime": self.confirmed_regime,
            "regime": self.confirmed_regime,
            "confidence": round(self.confidence, 2),
            "trend_direction": self.trend.direction,
            "trend_strength": round(self.trend.strength, 1),
            "momentum_state": self.momentum.state,
            "momentum_strength": round(self.momentum.strength, 1),
            "volatility_level": self.volatility.level,
            "volatility_state": self.volatility.state,
            "market_structure": self.market_structure,
            "supporting_features": self.supporting_features,
            "conflicting_features": self.conflicting_features,
            "timestamp": self.timestamp,
        }

class CryptoRegimeAgent:
    """
    Crypto Regime Intelligence Agent analyzing trend, momentum, volatility,
    and market structure to classify market regimes without trading signal generation.
    """

    def __init__(self):
        # Per (symbol, timeframe) regime transition tracking
        # key -> {last_raw, last_confirmed, transition_time, persistence_count}
        self._history_state: Dict[str, Dict[str, Any]] = {}

    def _get_state_key(self, symbol: str, timeframe: str) -> str:
        return f"{symbol}_{timeframe}"

    def evaluate_trend(self, feat: MarketFeatureSnapshot, struct: MarketStructureSnapshot) -> TrendSnapshot:
        """Evaluate trend direction and strength from multiple independent measurements."""
        if not feat.is_ready:
            return TrendSnapshot("NEUTRAL", 0.0)

        bull_points = 0
        bear_points = 0

        # 1. EMA Hierarchy
        if feat.ema_fast > feat.ema_medium > feat.ema_slow:
            bull_points += 30
        elif feat.ema_fast < feat.ema_medium < feat.ema_slow:
            bear_points += 30

        # 2. Price relative to EMA
        if feat.price > feat.ema_fast:
            bull_points += 15
        elif feat.price < feat.ema_fast:
            bear_points += 15

        # 3. Trend Slope & ADX
        if feat.trend_slope > 0.05:
            bull_points += 20
        elif feat.trend_slope < -0.05:
            bear_points += 20

        if feat.adx > 25:
            if feat.plus_di > feat.minus_di:
                bull_points += 15
            elif feat.minus_di > feat.plus_di:
                bear_points += 15

        # 4. Market Structure
        if struct.structure_state == "BULLISH_STRUCTURE":
            bull_points += 20
        elif struct.structure_state == "BEARISH_STRUCTURE":
            bear_points += 20

        # Determine direction and strength
        net_score = bull_points - bear_points
        strength = min(100.0, max(0.0, abs(net_score)))

        if net_score >= 60:
            direction = "STRONG_BULLISH"
        elif net_score >= 25:
            direction = "BULLISH"
        elif net_score <= -60:
            direction = "STRONG_BEARISH"
        elif net_score <= -25:
            direction = "BEARISH"
        else:
            direction = "NEUTRAL"

        return TrendSnapshot(direction=direction, strength=strength)

    def evaluate_momentum(self, feat: MarketFeatureSnapshot) -> MomentumSnapshot:
        """Evaluate momentum state and strength."""
        if not feat.is_ready:
            return MomentumSnapshot("NEUTRAL", 0.0)

        pos_points = 0
        neg_points = 0

        # RSI analysis
        if feat.rsi > 60:
            pos_points += 30
        elif feat.rsi < 40:
            neg_points += 30

        # MACD histogram analysis
        if feat.macd_histogram > 0:
            pos_points += 30
        elif feat.macd_histogram < 0:
            neg_points += 30

        # ROC analysis
        if feat.roc > 0.5:
            pos_points += 25
        elif feat.roc < -0.5:
            neg_points += 25

        # Distance from fast EMA
        if feat.distance_from_fast_ema > 0.2:
            pos_points += 15
        elif feat.distance_from_fast_ema < -0.2:
            neg_points += 15

        net_score = pos_points - neg_points
        strength = min(100.0, max(0.0, abs(net_score)))

        if net_score >= 50:
            state = "STRONG_POSITIVE"
        elif net_score >= 20:
            state = "POSITIVE"
        elif net_score <= -50:
            state = "STRONG_NEGATIVE"
        elif net_score <= -20:
            state = "NEGATIVE"
        else:
            state = "NEUTRAL"

        return MomentumSnapshot(state=state, strength=strength)

    def evaluate_volatility(self, feat: MarketFeatureSnapshot) -> VolatilitySnapshot:
        """Evaluate volatility level and expansion/contraction state."""
        if not feat.is_ready:
            return VolatilitySnapshot("NORMAL", "STABLE")

        vol_pct = feat.rolling_volatility
        bw = feat.bollinger_width

        # Volatility level
        if vol_pct > 2.5 or bw > 0.10:
            level = "EXTREME"
        elif vol_pct > 1.5 or bw > 0.06:
            level = "HIGH"
        elif vol_pct < 0.3 or bw < 0.015:
            level = "VERY_LOW"
        elif vol_pct < 0.6 or bw < 0.025:
            level = "LOW"
        else:
            level = "NORMAL"

        # Volatility state
        if bw > 0.05 and feat.atr_percent > 1.2:
            state = "EXPANDING"
        elif bw < 0.02 and feat.atr_percent < 0.5:
            state = "CONTRACTING"
        else:
            state = "STABLE"

        return VolatilitySnapshot(level=level, state=state)

    def classify_regime(
        self,
        feat: MarketFeatureSnapshot,
        struct: MarketStructureSnapshot
    ) -> SingleTimeframeRegimeResult:
        """Classify regime for a single timeframe with hysteresis and confidence evaluation."""
        symbol = feat.symbol
        tf = feat.timeframe

        if not feat.is_ready:
            return SingleTimeframeRegimeResult(
                symbol=symbol,
                timeframe=tf,
                raw_regime="INSUFFICIENT_DATA",
                confirmed_regime="INSUFFICIENT_DATA",
                confidence=0.0,
                timestamp=feat.timestamp
            )

        trend = self.evaluate_trend(feat, struct)
        momentum = self.evaluate_momentum(feat)
        volatility = self.evaluate_volatility(feat)

        supporting = []
        conflicting = []

        # Classification logic
        if trend.direction in ("STRONG_BULLISH", "BULLISH") and momentum.state in ("STRONG_POSITIVE", "POSITIVE"):
            supporting.append("Bullish trend & positive momentum alignment")
            raw_regime = "STRONG_UPTREND" if trend.direction == "STRONG_BULLISH" else "UPTREND"
        elif trend.direction in ("STRONG_BEARISH", "BEARISH") and momentum.state in ("STRONG_NEGATIVE", "NEGATIVE"):
            supporting.append("Bearish trend & negative momentum alignment")
            raw_regime = "STRONG_DOWNTREND" if trend.direction == "STRONG_BEARISH" else "DOWNTREND"
        elif volatility.state == "EXPANDING" and feat.bollinger_position > 0.9 and feat.adx > 20:
            supporting.append("Volatility expansion & upper Bollinger band breakout")
            raw_regime = "BREAKOUT_BULLISH"
        elif volatility.state == "EXPANDING" and feat.bollinger_position < 0.1 and feat.adx > 20:
            supporting.append("Volatility expansion & lower Bollinger band breakdown")
            raw_regime = "BREAKOUT_BEARISH"
        elif struct.structure_state == "RANGING_STRUCTURE" or (trend.direction == "NEUTRAL" and feat.adx < 20):
            supporting.append("Low ADX and ranging market structure")
            raw_regime = "RANGING"
        elif volatility.level in ("HIGH", "EXTREME") and trend.direction == "NEUTRAL":
            supporting.append("High volatility without clear trend")
            raw_regime = "HIGH_VOLATILITY"
        elif volatility.level in ("VERY_LOW", "LOW") and trend.direction == "NEUTRAL":
            supporting.append("Low volatility compression")
            raw_regime = "LOW_VOLATILITY"
        elif trend.direction != "NEUTRAL" and momentum.state != "NEUTRAL" and (
            ("BULLISH" in trend.direction and "NEGATIVE" in momentum.state) or
            ("BEARISH" in trend.direction and "POSITIVE" in momentum.state)
        ):
            conflicting.append(f"Trend ({trend.direction}) conflicts with Momentum ({momentum.state})")
            raw_regime = "UNCERTAIN"
        else:
            conflicting.append("Mixed indicator signals without dominant regime pattern")
            raw_regime = "UNCERTAIN"

        # Confidence calculation
        confidence_base = (feat.data_quality_score / 100.0) * 0.4
        trend_contrib = (trend.strength / 100.0) * 0.3
        momentum_contrib = (momentum.strength / 100.0) * 0.2
        conflict_penalty = 0.25 if conflicting else 0.0

        confidence = max(0.0, min(1.0, confidence_base + trend_contrib + momentum_contrib - conflict_penalty))

        # Hysteresis and regime persistence filtering
        key = self._get_state_key(symbol, tf)
        state_entry = self._history_state.get(key, {
            "last_raw": raw_regime,
            "last_confirmed": raw_regime,
            "persistence_count": 0
        })

        if raw_regime == state_entry["last_raw"]:
            state_entry["persistence_count"] += 1
        else:
            state_entry["last_raw"] = raw_regime
            state_entry["persistence_count"] = 1

        # Confirm regime if persistent or high confidence
        if state_entry["persistence_count"] >= 2 or confidence >= 0.75:
            state_entry["last_confirmed"] = raw_regime

        self._history_state[key] = state_entry
        confirmed_regime = state_entry["last_confirmed"]

        return SingleTimeframeRegimeResult(
            symbol=symbol,
            timeframe=tf,
            raw_regime=raw_regime,
            confirmed_regime=confirmed_regime,
            confidence=confidence,
            trend=trend,
            momentum=momentum,
            volatility=volatility,
            market_structure=struct.structure_state,
            supporting_features=supporting,
            conflicting_features=conflicting,
            timestamp=feat.timestamp
        )

class MultiTimeframeRegimeEngine:
    """
    Combines single-timeframe regime results across 1m, 5m, 15m, 30m, 1h, 4h
    using weighted alignment scoring to determine overall market regime.
    """

    @staticmethod
    def evaluate_multitimeframe_regime(
        symbol: str,
        tf_results: Dict[str, SingleTimeframeRegimeResult]
    ) -> Dict[str, Any]:
        if not tf_results:
            return {
                "symbol": symbol,
                "overall_regime": "INSUFFICIENT_DATA",
                "overall_direction": "NEUTRAL",
                "regime_confidence": 0.0,
                "timeframe_alignment": 0.0,
                "timeframe_regimes": {},
            }

        weights = config.timeframe_weights
        total_weight = 0.0
        weighted_direction_score = 0.0
        weighted_confidence = 0.0
        aligned_count = 0
        valid_tfs = 0

        directions_map = {
            "STRONG_BULLISH": 2.0,
            "BULLISH": 1.0,
            "NEUTRAL": 0.0,
            "BEARISH": -1.0,
            "STRONG_BEARISH": -2.0
        }

        primary_tf = "15m"
        primary_regime = tf_results.get(primary_tf, SingleTimeframeRegimeResult(symbol, primary_tf)).confirmed_regime

        tf_summaries = {}
        dir_counts = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0}

        for tf, res in tf_results.items():
            w = weights.get(tf, 0.15)
            tf_summaries[tf] = res.to_dict()

            if res.confirmed_regime == "INSUFFICIENT_DATA":
                continue

            valid_tfs += 1
            total_weight += w
            weighted_confidence += res.confidence * w

            d_val = directions_map.get(res.trend.direction, 0.0)
            weighted_direction_score += d_val * w

            if "BULLISH" in res.trend.direction:
                dir_counts["BULLISH"] += 1
            elif "BEARISH" in res.trend.direction:
                dir_counts["BEARISH"] += 1
            else:
                dir_counts["NEUTRAL"] += 1

        if total_weight > 0:
            norm_direction = weighted_direction_score / total_weight
            overall_confidence = weighted_confidence / total_weight
        else:
            norm_direction = 0.0
            overall_confidence = 0.0

        # Calculate Timeframe Alignment Score (0 to 100)
        max_dir_count = max(dir_counts.values()) if valid_tfs > 0 else 0
        alignment_score = (max_dir_count / valid_tfs * 100.0) if valid_tfs > 0 else 0.0

        # Determine Overall Direction
        if norm_direction >= 1.2:
            overall_direction = "STRONG_BULLISH"
        elif norm_direction >= 0.4:
            overall_direction = "BULLISH"
        elif norm_direction <= -1.2:
            overall_direction = "STRONG_BEARISH"
        elif norm_direction <= -0.4:
            overall_direction = "BEARISH"
        else:
            overall_direction = "NEUTRAL"

        # Determine Overall Regime
        if alignment_score >= 80.0 and "BULLISH" in overall_direction:
            overall_regime = "STRONG_UPTREND" if overall_direction == "STRONG_BULLISH" else "UPTREND"
        elif alignment_score >= 80.0 and "BEARISH" in overall_direction:
            overall_regime = "STRONG_DOWNTREND" if overall_direction == "STRONG_BEARISH" else "DOWNTREND"
        elif primary_regime in ("UPTREND", "STRONG_UPTREND", "DOWNTREND", "STRONG_DOWNTREND", "RANGING"):
            overall_regime = primary_regime
        elif norm_direction == 0.0 and alignment_score < 50.0:
            overall_regime = "UNCERTAIN"
        else:
            overall_regime = primary_regime

        return {
            "symbol": symbol,
            "overall_regime": overall_regime,
            "overall_direction": overall_direction,
            "regime_confidence": overall_confidence,
            "timeframe_alignment": alignment_score,
            "timeframe_regimes": tf_summaries,
        }

class CryptoMarketQualityEngine:
    """
    Computes Market Quality Score (0 to 100) measuring how clearly interpretable
    and structurally sound a cryptocurrency market environment currently is.
    """

    @staticmethod
    def calculate_quality_score(
        data_quality: float,
        regime_confidence: float,
        timeframe_alignment: float,
        trend_strength: float
    ) -> float:
        score = (
            (data_quality * 0.25) +
            (regime_confidence * 100.0 * 0.35) +
            (timeframe_alignment * 0.25) +
            (trend_strength * 0.15)
        )
        return max(0.0, min(100.0, score))
