import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
from src.api.deriv_client import DerivClient, ConnectionState

@pytest.mark.asyncio
async def test_deriv_client_initialization():
    client = DerivClient(app_id="1089")
    assert client.app_id == "1089"
    assert client.state == ConnectionState.DISCONNECTED
    assert client.reconnect_attempts == 0

@pytest.mark.asyncio
async def test_req_id_counter_increment():
    client = DerivClient()
    id1 = client._next_req_id()
    id2 = client._next_req_id()
    assert id2 == id1 + 1

@pytest.mark.asyncio
async def test_deriv_client_request_correlation():
    client = DerivClient()
    mock_ws = MagicMock()
    client.ws = mock_ws
    client.state = ConnectionState.CONNECTED

    def mock_send(data_str):
        data = json.loads(data_str)
        req_id = data["req_id"]
        if req_id in client.pending_requests:
            fut = client.pending_requests[req_id]
            fut.set_result({"req_id": req_id, "ping": "pong"})

    mock_ws.send = mock_send

    res = await client.request({"ping": 1})
    assert res["ping"] == "pong"
    assert "req_id" in res
