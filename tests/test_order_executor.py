"""
Unit tests for Deriv Live Order Execution Engine (DerivOrderExecutor).
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.config import config
from src.api.deriv_client import DerivClient, ConnectionState
from src.execution.deriv_order_executor import DerivOrderExecutor, LiveOrderResult


@pytest.mark.asyncio
async def test_order_executor_dry_run_safety_veto():
    mock_client = MagicMock(spec=DerivClient)
    mock_client.state = ConnectionState.AUTHENTICATED
    executor = DerivOrderExecutor(client=mock_client, allow_live_execution=True)

    with patch.object(config, "dry_run", True), patch.object(config, "live_trading", False):
        res = await executor.execute_buy(proposal_id="prop_123", ask_price=15.0, symbol="cryBTCUSD")
        assert res.is_success is False
        assert "[SAFETY_VIOLATION]" in res.error_message


@pytest.mark.asyncio
async def test_order_executor_runtime_lock_veto():
    mock_client = MagicMock(spec=DerivClient)
    mock_client.state = ConnectionState.AUTHENTICATED
    executor = DerivOrderExecutor(client=mock_client, allow_live_execution=False)

    with patch.object(config, "dry_run", False), patch.object(config, "live_trading", True):
        res = await executor.execute_buy(proposal_id="prop_123", ask_price=15.0, symbol="cryBTCUSD")
        assert res.is_success is False
        assert "allow_live_execution flag is False" in res.error_message


@pytest.mark.asyncio
async def test_order_executor_kill_switch_veto():
    mock_client = MagicMock(spec=DerivClient)
    mock_client.state = ConnectionState.AUTHENTICATED
    executor = DerivOrderExecutor(client=mock_client, allow_live_execution=True)
    executor.trigger_kill_switch("Daily drawdown cap reached")

    with patch.object(config, "dry_run", False), patch.object(config, "live_trading", True):
        res = await executor.execute_buy(proposal_id="prop_123", ask_price=15.0, symbol="cryBTCUSD")
        assert res.is_success is False
        assert "[KILL_SWITCH_ACTIVE]" in res.error_message


@pytest.mark.asyncio
async def test_order_executor_max_stake_cap_veto():
    mock_client = MagicMock(spec=DerivClient)
    mock_client.state = ConnectionState.AUTHENTICATED
    executor = DerivOrderExecutor(client=mock_client, max_stake_cap=20.0, allow_live_execution=True)

    with patch.object(config, "dry_run", False), patch.object(config, "live_trading", True):
        res = await executor.execute_buy(proposal_id="prop_123", ask_price=50.0, symbol="cryBTCUSD")
        assert res.is_success is False
        assert "[STAKE_CAP_EXCEEDED]" in res.error_message


@pytest.mark.asyncio
async def test_order_executor_unauthenticated_veto():
    mock_client = MagicMock(spec=DerivClient)
    mock_client.state = ConnectionState.CONNECTED
    executor = DerivOrderExecutor(client=mock_client, allow_live_execution=True)

    with patch.object(config, "dry_run", False), patch.object(config, "live_trading", True):
        res = await executor.execute_buy(proposal_id="prop_123", ask_price=15.0, symbol="cryBTCUSD")
        assert res.is_success is False
        assert "[NOT_AUTHENTICATED]" in res.error_message


@pytest.mark.asyncio
async def test_order_executor_successful_buy():
    mock_client = MagicMock(spec=DerivClient)
    mock_client.state = ConnectionState.AUTHENTICATED
    mock_client.request = AsyncMock(return_value={
        "buy": {
            "contract_id": "123456789",
            "buy_price": 15.0,
            "balance_after": 985.0,
            "purchase_time": 1700000000,
        }
    })
    executor = DerivOrderExecutor(client=mock_client, max_stake_cap=50.0, allow_live_execution=True)

    with patch.object(config, "dry_run", False), patch.object(config, "live_trading", True):
        res = await executor.execute_buy(proposal_id="prop_123", ask_price=15.0, symbol="cryBTCUSD", payout=30.0)
        assert res.is_success is True
        assert res.contract_id == "123456789"
        assert res.buy_price == 15.0
        assert res.balance_after == 985.0
