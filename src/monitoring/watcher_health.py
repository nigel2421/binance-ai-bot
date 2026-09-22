import time
import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from src.config import config

logger = logging.getLogger("WATCHER")

class WatcherState(str, Enum):
    HEALTHY = "HEALTHY"
    HISTORY_ONLY = "HISTORY_ONLY"
    SCANNING = "SCANNING"
    WARMING_UP = "WARMING_UP"
    STALE = "STALE"
    NO_DATA = "NO_DATA"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"

class CryptoWatcher:
    """
    Independent sub-agent watcher maintaining health status, data readiness,
    and Stage 3 market intelligence metrics for a single cryptocurrency market.
    Implements strict error isolation so exceptions in one watcher do not affect others.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.state: WatcherState = WatcherState.NO_DATA
        self.current_price: float = 0.0
        self.previous_price: float = 0.0
        self.last_tick_time: float = 0.0
        self.ticks_received: int = 0
        self.ticks_per_minute: float = 0.0
        self.last_analysis_time: float = 0.0
        self.error_count: int = 0
        self.candles_ready: bool = False

        # 6-Dimension Readiness Model
        self.historical_ready: bool = False
        self.live_stream_ready: bool = False
        self.features_ready: bool = False
        self.regime_ready: bool = False
        self.strategy_ready: bool = False
        self.consensus_ready: bool = False

        # Recency timestamps (Separating historical data from live stream)
        self.last_historical_candle_time: float = 0.0
        self.last_live_tick_time: float = 0.0

        # Timeframe readiness map
        self.timeframes_ready: Dict[str, str] = {
            "1m": "WARMING_UP",
            "5m": "WARMING_UP",
            "15m": "WARMING_UP",
            "30m": "WARMING_UP",
            "1h": "WARMING_UP",
            "4h": "WARMING_UP",
        }

        # Stage 3 Market Intelligence Context (No trade signals or recommendations)
        self.overall_regime: str = "INSUFFICIENT_DATA"
        self.regime_confidence: float = 0.0
        self.trend_direction: str = "NEUTRAL"
        self.trend_strength: float = 0.0
        self.momentum_state: str = "NEUTRAL"
        self.volatility_state: str = "NORMAL"
        self.timeframe_alignment: float = 0.0
        self.market_quality_score: float = 0.0
        
        # Single Timeframe Regimes Map: timeframe -> regime_str
        self.tf_regimes: Dict[str, str] = {
            "1m": "NOT_READY",
            "5m": "NOT_READY",
            "15m": "NOT_READY",
            "30m": "NOT_READY",
            "1h": "NOT_READY",
            "4h": "NOT_READY",
        }

    @property
    def seconds_since_last_tick(self) -> float:
        if not self.last_live_tick_time and not self.last_tick_time:
            return 99999.0
        ref_t = self.last_live_tick_time or self.last_tick_time
        return max(0.0, time.time() - ref_t)

    @property
    def data_recency_sec(self) -> float:
        if not self.last_historical_candle_time:
            return 99999.0
        return max(0.0, time.time() - self.last_historical_candle_time)

    @property
    def live_stream_freshness_sec(self) -> float:
        if not self.last_live_tick_time:
            return 99999.0
        return max(0.0, time.time() - self.last_live_tick_time)

    @property
    def research_ready(self) -> bool:
        """True if market data, features, regime, strategies, and consensus are evaluated and ready for historical research."""
        return (
            self.historical_ready and
            self.features_ready and
            self.regime_ready and
            self.strategy_ready and
            self.consensus_ready
        )

    @property
    def live_ready(self) -> bool:
        """True if research_ready AND an active certified live tick stream is streaming fresh ticks."""
        return self.research_ready and self.live_stream_ready

    def update_tick(self, price: float, timestamp: float = 0.0, rate_per_min: float = 0.0, is_live_stream: bool = True):
        """Update watcher state with new tick (isolated exception handling)."""
        try:
            self.previous_price = self.current_price or price
            self.current_price = price
            self.ticks_received += 1
            ts = timestamp or time.time()
            self.last_tick_time = ts
            if is_live_stream:
                self.last_live_tick_time = ts
                self.live_stream_ready = True
            self.ticks_per_minute = rate_per_min

            if self.state in (WatcherState.NO_DATA, WatcherState.STALE, WatcherState.DISCONNECTED, WatcherState.HISTORY_ONLY):
                self.state = WatcherState.HEALTHY
        except Exception as err:
            self.error_count += 1
            logger.error(f"[WATCHER][{self.symbol}] Isolated tick update exception: {err}")

    def update_timeframe_readiness(self, readiness_map: Dict[str, str], last_candle_time: float = 0.0):
        """Update timeframe readiness metrics for watcher."""
        try:
            self.timeframes_ready.update(readiness_map)
            self.candles_ready = all(v == "READY" for v in self.timeframes_ready.values())
            self.historical_ready = any(v in ("READY", "WARMING_UP") for v in self.timeframes_ready.values())
            if last_candle_time > 0:
                self.last_historical_candle_time = last_candle_time
            elif self.candles_ready and not self.last_historical_candle_time:
                self.last_historical_candle_time = time.time()
        except Exception as err:
            self.error_count += 1
            logger.error(f"[WATCHER][{self.symbol}] Isolated readiness update exception: {err}")

    def update_intelligence(self, mtf_regime_res: Dict[str, Any], quality_score: float):
        """Update watcher with Stage 3 market intelligence results."""
        try:
            self.overall_regime = mtf_regime_res.get("overall_regime", "INSUFFICIENT_DATA")
            self.regime_confidence = mtf_regime_res.get("regime_confidence", 0.0)
            self.trend_direction = mtf_regime_res.get("overall_direction", "NEUTRAL")
            self.timeframe_alignment = mtf_regime_res.get("timeframe_alignment", 0.0)
            self.market_quality_score = quality_score
            self.last_analysis_time = time.time()

            self.features_ready = True
            self.regime_ready = self.overall_regime not in ("INSUFFICIENT_DATA", "NOT_READY")

            tf_details = mtf_regime_res.get("timeframe_regimes", {})
            for tf, detail in tf_details.items():
                if isinstance(detail, dict):
                    self.tf_regimes[tf] = detail.get("regime", "NOT_READY")
        except Exception as err:
            self.error_count += 1
            logger.error(f"[WATCHER][{self.symbol}] Isolated intelligence update exception: {err}")

    def evaluate_health(self, is_ws_connected: bool = True, stale_threshold_sec: float = 30.0):
        """Evaluate watcher health state deterministically distinguishing HEALTHY vs HISTORY_ONLY."""
        try:
            if not is_ws_connected:
                self.state = WatcherState.DISCONNECTED
                self.live_stream_ready = False
                return

            if self.error_count > 5:
                self.state = WatcherState.ERROR
                return

            has_candles = any(v in ("READY", "WARMING_UP") for v in self.timeframes_ready.values())
            sec_since = self.seconds_since_last_tick

            if not self.last_live_tick_time:
                self.live_stream_ready = False
                if has_candles:
                    self.state = WatcherState.HISTORY_ONLY
                else:
                    self.state = WatcherState.NO_DATA
                return

            if sec_since > stale_threshold_sec:
                self.state = WatcherState.STALE
                self.live_stream_ready = False
                return

            if all(v == "READY" for v in self.timeframes_ready.values()):
                self.state = WatcherState.HEALTHY
            elif any(v in ("READY", "WARMING_UP") for v in self.timeframes_ready.values()):
                self.state = WatcherState.WARMING_UP
            else:
                self.state = WatcherState.HEALTHY
        except Exception as err:
            self.error_count += 1
            self.state = WatcherState.ERROR
            logger.error(f"[WATCHER][{self.symbol}] Isolated health evaluation exception: {err}")

    def get_summary(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "status": self.state.value,
            "price": self.current_price,
            "ticks": self.ticks_received,
            "rate_per_min": self.ticks_per_minute,
            "sec_since_last_tick": round(self.seconds_since_last_tick, 1),
            "1m_ready": self.timeframes_ready.get("1m", "UNKNOWN"),
            "5m_ready": self.timeframes_ready.get("5m", "UNKNOWN"),
            "15m_ready": self.timeframes_ready.get("15m", "UNKNOWN"),
            "30m_ready": self.timeframes_ready.get("30m", "UNKNOWN"),
            "1h_ready": self.timeframes_ready.get("1h", "UNKNOWN"),
            "4h_ready": self.timeframes_ready.get("4h", "UNKNOWN"),
            "candles_ready": self.candles_ready,
            "historical_ready": self.historical_ready,
            "live_stream_ready": self.live_stream_ready,
            "features_ready": self.features_ready,
            "regime_ready": self.regime_ready,
            "strategy_ready": self.strategy_ready,
            "consensus_ready": self.consensus_ready,
            "research_ready": self.research_ready,
            "live_ready": self.live_ready,
            "regime": self.overall_regime,
            "confidence": round(self.regime_confidence, 2),
            "trend": self.trend_direction,
            "trend_strength": round(self.trend_strength, 1),
            "momentum": self.momentum_state,
            "volatility": self.volatility_state,
            "alignment": round(self.timeframe_alignment, 1),
            "quality": round(self.market_quality_score, 1),
            "errors": self.error_count,
        }

    def get_health_status_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value if isinstance(self.state, Enum) else str(self.state),
            "seconds_since_last_tick": self.seconds_since_last_tick,
            "data_recency_sec": round(self.data_recency_sec, 1),
            "live_stream_freshness_sec": round(self.live_stream_freshness_sec, 1),
            "ticks_received": self.ticks_received,
            "candles_ready": self.candles_ready,
            "historical_ready": self.historical_ready,
            "live_stream_ready": self.live_stream_ready,
            "features_ready": self.features_ready,
            "regime_ready": self.regime_ready,
            "strategy_ready": self.strategy_ready,
            "consensus_ready": self.consensus_ready,
            "research_ready": self.research_ready,
            "live_ready": self.live_ready,
            "error_count": self.error_count,
        }

class GlobalHealthManager:
    """Aggregates system-wide health status and watcher metrics."""

    def __init__(self):
        self.start_time: float = time.time()

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time

    def format_uptime(self) -> str:
        secs = int(self.uptime_seconds)
        hours = secs // 3600
        minutes = (secs % 3600) // 60
        seconds = secs % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def get_health_report(
        self,
        ws_state: str,
        auth_state: str,
        watchers: Dict[str, CryptoWatcher]
    ) -> Dict[str, Any]:
        counts = {
            "HEALTHY": 0,
            "HISTORY_ONLY": 0,
            "SCANNING": 0,
            "WARMING_UP": 0,
            "STALE": 0,
            "NO_DATA": 0,
            "DISCONNECTED": 0,
            "ERROR": 0
        }

        total_ticks = 0
        for w in watchers.values():
            counts[w.state.value] = counts.get(w.state.value, 0) + 1
            total_ticks += w.ticks_received

        return {
            "ws_state": ws_state,
            "auth_state": auth_state,
            "discovered_markets": len(watchers),
            "watchers_healthy": counts["HEALTHY"],
            "watchers_history_only": counts["HISTORY_ONLY"],
            "watchers_warming": counts["WARMING_UP"],
            "watchers_stale": counts["STALE"],
            "watchers_no_data": counts["NO_DATA"],
            "watchers_error": counts["ERROR"],
            "total_ticks": total_ticks,
            "uptime": self.format_uptime(),
            "dry_run": config.dry_run,
            "live_trading": config.live_trading,
        }
