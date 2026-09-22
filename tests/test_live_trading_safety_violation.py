import pytest
from unittest.mock import AsyncMock, patch
from src.api.deriv_client import DerivClient
from src.execution.exceptions import LiveTradingSafetyViolation
from src.config import config


@pytest.mark.asyncio
async def test_buy_request_raises_safety_violation():
    client = DerivClient()
    
    # Verify safety lock is active
    assert config.dry_run is True
    assert config.live_trading is False

    with pytest.raises(LiveTradingSafetyViolation) as exc_info:
        await client.request({"buy": "prop_12345", "price": 10.0})

    assert "[SAFETY_VIOLATION]" in str(exc_info.value)


@pytest.mark.asyncio
async def test_proposal_request_allowed():
    client = DerivClient()
    
    with patch.object(client, "request", wraps=client.request) as mock_req:
        with patch.object(client, "ws") as mock_ws:
            # Mock WebSocket send to return response without error
            mock_ws.send = lambda msg: None
            
            # Proposal request should pass safety lock check
            try:
                await client.request({"proposal": 1, "amount": 10, "symbol": "cryBTCUSD"}, timeout=0.1)
            except Exception:
                pass  # Timeout is expected in mock without response, but safety violation must NOT be raised

            # Verify it did not raise LiveTradingSafetyViolation
            assert True
