"""
Live Stream Certifier for Deriv Crypto AI Bot Stage 5.5.

Certifies whether continuous live tick stream subscriptions are active, healthy, and delivering ticks
in real-time, distinguishing certified live streams from historical data.
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
import time
from typing import Dict, Any, List, Optional

logger = logging.getLogger("STREAM_CERTIFIER")


class StreamCertificationState(str, Enum):
    NOT_TESTED = "NOT_TESTED"
    CONNECTING = "CONNECTING"
    SUBSCRIBED = "SUBSCRIBED"
    RECEIVING = "RECEIVING"
    CERTIFIED = "CERTIFIED"
    STALE = "STALE"
    FAILED = "FAILED"
    HISTORY_ONLY = "HISTORY_ONLY"


@dataclass
class StreamTelemetry:
    symbol: str
    certification_state: StreamCertificationState = StreamCertificationState.NOT_TESTED
    subscription_requested_at: float = 0.0
    subscription_response: Dict[str, Any] = field(default_factory=dict)
    subscription_id: Optional[str] = None
    subscription_active: bool = False
    messages_received: int = 0
    ticks_received: int = 0
    first_live_tick_at: float = 0.0
    last_live_tick_at: float = 0.0
    seconds_since_live_tick: float = 99999.0
    stream_age_sec: float = 0.0
    ticks_per_minute: float = 0.0
    disconnect_count: int = 0
    reconnect_count: int = 0
    restoration_count: int = 0

    def update_tick(self, timestamp: Optional[float] = None):
        ts = timestamp or time.time()
        if not self.first_live_tick_at:
            self.first_live_tick_at = ts
        self.last_live_tick_at = ts
        self.ticks_received += 1
        self.messages_received += 1
        self.seconds_since_live_tick = 0.0
        if self.subscription_requested_at:
            self.stream_age_sec = ts - self.subscription_requested_at
        if self.stream_age_sec > 0:
            self.ticks_per_minute = (self.ticks_received / self.stream_age_sec) * 60.0

    def evaluate_state(
        self,
        min_live_ticks: int = 5,
        max_seconds_since_tick: float = 15.0,
        min_observation_window_sec: float = 30.0,
        current_time: Optional[float] = None,
    ) -> StreamCertificationState:
        now = current_time or time.time()

        if self.subscription_requested_at:
            self.stream_age_sec = now - self.subscription_requested_at

        if self.last_live_tick_at:
            self.seconds_since_live_tick = max(0.0, now - self.last_live_tick_at)
        else:
            self.seconds_since_live_tick = 99999.0

        if not self.subscription_active and self.ticks_received == 0:
            self.certification_state = StreamCertificationState.HISTORY_ONLY
            return self.certification_state

        if self.ticks_received == 0:
            if self.stream_age_sec > 20.0:
                self.certification_state = StreamCertificationState.FAILED
            else:
                self.certification_state = StreamCertificationState.SUBSCRIBED
            return self.certification_state

        if self.seconds_since_live_tick > max_seconds_since_tick:
            self.certification_state = StreamCertificationState.STALE
            return self.certification_state

        if self.ticks_received >= min_live_ticks and self.stream_age_sec >= min_observation_window_sec:
            self.certification_state = StreamCertificationState.CERTIFIED
        else:
            self.certification_state = StreamCertificationState.RECEIVING

        return self.certification_state

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "certification": self.certification_state.value if isinstance(self.certification_state, Enum) else str(self.certification_state),
            "subscription_id": self.subscription_id or "NONE",
            "subscription_active": self.subscription_active,
            "messages_received": self.messages_received,
            "ticks_received": self.ticks_received,
            "ticks_per_min": round(self.ticks_per_minute, 1),
            "seconds_since_live_tick": round(self.seconds_since_live_tick, 1),
            "stream_age_sec": round(self.stream_age_sec, 1),
            "reconnects": self.reconnect_count,
        }


class LiveStreamCertifier:
    """
    Manages live stream certification telemetry across all active crypto watcher markets.
    """

    def __init__(
        self,
        min_live_ticks: int = 5,
        max_seconds_since_tick: float = 15.0,
        min_observation_window_sec: float = 30.0,
    ):
        self.min_live_ticks = min_live_ticks
        self.max_seconds_since_tick = max_seconds_since_tick
        self.min_observation_window_sec = min_observation_window_sec
        self.telemetry: Dict[str, StreamTelemetry] = {}

    def register_symbol(self, symbol: str):
        if symbol not in self.telemetry:
            self.telemetry[symbol] = StreamTelemetry(symbol=symbol)

    def record_subscription_request(self, symbol: str):
        self.register_symbol(symbol)
        t = self.telemetry[symbol]
        t.subscription_requested_at = time.time()
        t.certification_state = StreamCertificationState.CONNECTING

    def record_subscription_response(self, symbol: str, response: Dict[str, Any]):
        self.register_symbol(symbol)
        t = self.telemetry[symbol]
        t.subscription_response = response
        if "subscription" in response and "id" in response["subscription"]:
            t.subscription_id = str(response["subscription"]["id"])
            t.subscription_active = True
            t.certification_state = StreamCertificationState.SUBSCRIBED
        elif "error" in response:
            t.subscription_active = False
            t.certification_state = StreamCertificationState.FAILED
            logger.warning(f"[STREAM_CERTIFIER][{symbol}] Subscription rejected: {response['error'].get('message')}")

    def record_live_tick(self, symbol: str, timestamp: Optional[float] = None):
        self.register_symbol(symbol)
        t = self.telemetry[symbol]
        t.update_tick(timestamp)
        t.evaluate_state(
            min_live_ticks=self.min_live_ticks,
            max_seconds_since_tick=self.max_seconds_since_tick,
            min_observation_window_sec=self.min_observation_window_sec,
        )

    def evaluate_all(self, current_time: Optional[float] = None) -> Dict[str, StreamTelemetry]:
        for t in self.telemetry.values():
            t.evaluate_state(
                min_live_ticks=self.min_live_ticks,
                max_seconds_since_tick=self.max_seconds_since_tick,
                min_observation_window_sec=self.min_observation_window_sec,
                current_time=current_time,
            )
        return self.telemetry

    def generate_certification_report(self) -> Dict[str, Any]:
        self.evaluate_all()
        certified_count = sum(1 for t in self.telemetry.values() if t.certification_state == StreamCertificationState.CERTIFIED)
        receiving_count = sum(1 for t in self.telemetry.values() if t.certification_state == StreamCertificationState.RECEIVING)
        history_only_count = sum(1 for t in self.telemetry.values() if t.certification_state == StreamCertificationState.HISTORY_ONLY)
        failed_count = sum(1 for t in self.telemetry.values() if t.certification_state in (StreamCertificationState.FAILED, StreamCertificationState.STALE))

        return {
            "total_monitored": len(self.telemetry),
            "certified": certified_count,
            "receiving": receiving_count,
            "history_only": history_only_count,
            "failed_or_stale": failed_count,
            "streams": {sym: t.to_dict() for sym, t in self.telemetry.items()},
        }
