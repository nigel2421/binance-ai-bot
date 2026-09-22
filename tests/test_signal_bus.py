"""
Unit tests for SignalBus.
"""

import time
import pytest
from src.strategy.signal import StrategySignal, SignalDirection, SignalStatus, SignalTier
from src.strategy.signal_bus import SignalBus


def test_signal_bus_deduplication_and_expiry():
    bus = SignalBus(default_cooldown=300.0)
    now = time.time()

    sig1 = StrategySignal(
        signal_id="sig_1",
        symbol="cryBTCUSD",
        strategy="CryptoTrendAgent",
        timestamp=now,
        timeframe="15m",
        direction=SignalDirection.BULLISH,
        confidence=0.78,
        regime="UPTREND",
        regime_confidence=0.85,
        market_quality=80.0,
        timeframe_alignment=75.0,
        status=SignalStatus.CANDIDATE,
        tier=SignalTier.A,
        expires_at=now + 10.0,
    )

    # 1. First publish should succeed
    published1 = bus.publish(sig1)
    assert published1 is True
    assert len(bus.recent_candidates()) == 1

    # 2. Immediate identical publish should be deduplicated
    sig2 = StrategySignal(
        signal_id="sig_2",
        symbol="cryBTCUSD",
        strategy="CryptoTrendAgent",
        timestamp=now + 1.0,
        timeframe="15m",
        direction=SignalDirection.BULLISH,
        confidence=0.79,  # small confidence change < 0.05
        regime="UPTREND",
        regime_confidence=0.85,
        market_quality=80.0,
        timeframe_alignment=75.0,
        status=SignalStatus.CANDIDATE,
        tier=SignalTier.A,
        expires_at=now + 11.0,
    )
    published2 = bus.publish(sig2)
    assert published2 is False  # Suppressed duplicate

    # 3. Test expiry
    bus.clean_expired(current_time=now + 20.0)
    assert len(bus.recent_candidates()) == 0
