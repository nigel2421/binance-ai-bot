import pytest
import time
from src.monitoring.watcher_health import CryptoWatcher, GlobalHealthManager, WatcherState

def test_watcher_health_state_transitions():
    watcher = CryptoWatcher("cryBTCUSD")
    assert watcher.state == WatcherState.NO_DATA

    # Update tick
    watcher.update_tick(50000.0, timestamp=time.time())
    watcher.evaluate_health(is_ws_connected=True)
    assert watcher.state in (WatcherState.HEALTHY, WatcherState.WARMING_UP)

    # Test Stale state when no tick received for 60s
    watcher.last_tick_time = time.time() - 60.0
    watcher.last_live_tick_time = time.time() - 60.0
    watcher.evaluate_health(is_ws_connected=True, stale_threshold_sec=30.0)
    assert watcher.state == WatcherState.STALE

    # Test Disconnected state
    watcher.evaluate_health(is_ws_connected=False)
    assert watcher.state == WatcherState.DISCONNECTED

def test_global_health_manager_report():
    mgr = GlobalHealthManager()
    w1 = CryptoWatcher("cryBTCUSD")
    w1.state = WatcherState.HEALTHY
    w1.ticks_received = 50

    w2 = CryptoWatcher("cryETHUSD")
    w2.state = WatcherState.WARMING_UP
    w2.ticks_received = 10

    watchers = {"cryBTCUSD": w1, "cryETHUSD": w2}
    report = mgr.get_health_report("CONNECTED", "AUTHENTICATED", watchers)

    assert report["ws_state"] == "CONNECTED"
    assert report["discovered_markets"] == 2
    assert report["watchers_healthy"] == 1
    assert report["watchers_warming"] == 1
    assert report["total_ticks"] == 60
