import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.api.deriv_client import DerivClient, ConnectionState
from src.monitoring.watcher_health import CryptoWatcher, WatcherState

@pytest.mark.asyncio
async def test_reconnect_flow_subscription_restoration():
    client = DerivClient(app_id="1089", api_token="test_token")
    client._loop = asyncio.get_running_loop()
    client._running = True

    # Mock request method to simulate auth and sub responses
    async def mock_request(payload, timeout=10.0):
        req_id = payload.get("req_id", 1)
        if "authorize" in payload:
            return {"req_id": req_id, "authorize": {"email": "test@example.com"}}
        elif "subscribe" in payload:
            sym = payload.get("ticks", "cryBTCUSD")
            return {"req_id": req_id, "subscription": {"id": f"sub_{sym}"}}
        elif "forget" in payload:
            return {"req_id": req_id, "forget": payload.get("forget")}
        return {"req_id": req_id, "ping": "pong"}

    async def mock_connect():
        client.state = ConnectionState.CONNECTED

    client.request = AsyncMock(side_effect=mock_request)
    client.connect = AsyncMock(side_effect=mock_connect)

    # Setup subscription
    cb_calls = []
    def dummy_cb(msg):
        cb_calls.append(msg)

    sub_id = await client.subscribe({"ticks": "cryBTCUSD"}, dummy_cb)
    assert sub_id == "sub_cryBTCUSD"
    assert len(client.active_subscriptions) == 1

    # Simulate disconnect
    client.state = ConnectionState.DISCONNECTED
    watcher = CryptoWatcher("cryBTCUSD")
    watcher.evaluate_health(is_ws_connected=False)
    assert watcher.state == WatcherState.DISCONNECTED

    # Trigger reconnect
    with patch("asyncio.sleep", AsyncMock()):
        await client.reconnect()

    # Verify reconnect state and subscription restoration
    assert client.connect.called
    assert client.request.called
    assert len(client.active_subscriptions) == 1
    assert "sub_cryBTCUSD" in client.active_subscriptions

    # Watcher receives tick and recovers to HEALTHY
    watcher.update_tick(50000.0)
    watcher.evaluate_health(is_ws_connected=True)
    assert watcher.state in (WatcherState.HEALTHY, WatcherState.WARMING_UP)

@pytest.mark.asyncio
async def test_no_duplicate_subscriptions_on_reconnect():
    client = DerivClient()
    client._loop = asyncio.get_running_loop()
    client._running = True

    sub_counter = 0
    async def mock_request(payload, timeout=10.0):
        nonlocal sub_counter
        sub_counter += 1
        return {"subscription": {"id": f"sub_id_{sub_counter}"}}

    async def mock_connect():
        client.state = ConnectionState.CONNECTED

    client.request = AsyncMock(side_effect=mock_request)
    client.connect = AsyncMock(side_effect=mock_connect)

    def cb(msg):
        pass

    s1 = await client.subscribe({"ticks": "cryBTCUSD"}, cb)
    assert len(client.active_subscriptions) == 1

    with patch("asyncio.sleep", AsyncMock()):
        await client.reconnect()

    # Verify that total active subscriptions count remains 1 (no duplicates created)
    assert len(client.active_subscriptions) == 1
