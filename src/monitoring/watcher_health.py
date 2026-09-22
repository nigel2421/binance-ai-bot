import time
import logging
from enum import Enum
from typing import Dict, Any, Optional

logger = logging.getLogger("CryptoWatcher")

class WatcherState(str, Enum):
    HEALTHY = "HEALTHY"
    SCANNING = "SCANNING"
    CANDIDATE = "CANDIDATE"
    SIGNAL = "SIGNAL"
    FILTERED = "FILTERED"
    STALE = "STALE"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"

class CryptoWatcher:
    """
    Sub-agent watcher maintaining health status, market metrics, regime,
    and signal state for a single crypto market symbol.
    """

    def __init__(self, symbol: str):
        self.symbol = symbol
        self.state: WatcherState = WatcherState.SCANNING
        self.current_price: float = 0.0
        self.last_price: float = 0.0
        self.tick_count: int = 0
        self.last_tick_time: float = 0.0

        # Market & Agent context
        self.current_regime: str = "UNCERTAIN"
        self.trend_direction: str = "NEUTRAL"
        self.volatility: float = 0.0
        self.active_strategy: Optional[str] = None
        
        # Diagnostic & Signal counters
        self.signal_count: int = 0
        self.qualified_signal_count: int = 0
        self.last_signal: Optional[str] = None
        self.last_confidence: float = 0.0
        self.last_rejection_reason: Optional[str] = None
        self.last_trade_time: Optional[float] = None

    def update_tick(self, price: float, timestamp: float = 0.0):
        self.last_price = self.current_price or price
        self.current_price = price
        self.tick_count += 1
        self.last_tick_time = timestamp or time.time()
        
        if self.state in (WatcherState.STALE, WatcherState.DISCONNECTED):
            self.state = WatcherState.HEALTHY

    def update_state(self, new_state: WatcherState, rejection_reason: Optional[str] = None):
        self.state = new_state
        if rejection_reason:
            self.last_rejection_reason = rejection_reason

    def check_health(self, max_stale_seconds: float = 30.0):
        if self.last_tick_time and (time.time() - self.last_tick_time) > max_stale_seconds:
            self.state = WatcherState.STALE

    def get_summary(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "state": self.state.value,
            "current_price": self.current_price,
            "regime": self.current_regime,
            "trend": self.trend_direction,
            "tick_count": self.tick_count,
            "signals": self.signal_count,
            "qualified_signals": self.qualified_signal_count,
            "last_rejection": self.last_rejection_reason,
        }
