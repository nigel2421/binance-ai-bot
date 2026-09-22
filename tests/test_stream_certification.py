import time
import pytest
from src.monitoring.stream_certifier import LiveStreamCertifier, StreamCertificationState, StreamTelemetry


def test_stream_telemetry_state_transitions():
    t = StreamTelemetry(symbol="cryBTCUSD")
    t.subscription_requested_at = time.time() - 5.0
    t.subscription_id = "sub_12345"
    t.subscription_active = True

    # Initial state (sub requested 5s ago, 0 ticks received)
    state = t.evaluate_state(min_live_ticks=5, max_seconds_since_tick=15.0, min_observation_window_sec=30.0)
    assert state == StreamCertificationState.SUBSCRIBED

    # Receive 3 ticks (RECEIVING)
    now = time.time()
    for _ in range(3):
        t.update_tick(now)
    state = t.evaluate_state(min_live_ticks=5, max_seconds_since_tick=15.0, min_observation_window_sec=30.0)
    assert state == StreamCertificationState.RECEIVING

    # Set requested at to 35s ago and receive 3 more ticks (total 6 ticks over 35s -> CERTIFIED)
    t.subscription_requested_at = now - 35.0
    for _ in range(3):
        t.update_tick(now)
    state = t.evaluate_state(min_live_ticks=5, max_seconds_since_tick=15.0, min_observation_window_sec=30.0)
    assert state == StreamCertificationState.CERTIFIED

    # Simulate stale tick (>15s since last tick)
    future_time = now + 20.0
    state = t.evaluate_state(min_live_ticks=5, max_seconds_since_tick=15.0, min_observation_window_sec=30.0, current_time=future_time)
    assert state == StreamCertificationState.STALE


def test_livestream_certifier_report():
    certifier = LiveStreamCertifier(min_live_ticks=2, max_seconds_since_tick=10.0, min_observation_window_sec=5.0)
    certifier.record_subscription_request("cryETHUSD")
    certifier.record_subscription_response("cryETHUSD", {"subscription": {"id": "sub_eth_1"}})
    
    # Backdate subscription_requested_at to 10s ago so observation window requirement is met
    certifier.telemetry["cryETHUSD"].subscription_requested_at = time.time() - 10.0

    t0 = time.time() - 4.0
    certifier.record_live_tick("cryETHUSD", timestamp=t0)
    certifier.record_live_tick("cryETHUSD", timestamp=t0 + 2.0)

    report = certifier.generate_certification_report()
    assert report["total_monitored"] == 1
    assert report["certified"] == 1
    assert report["streams"]["cryETHUSD"]["subscription_id"] == "sub_eth_1"
