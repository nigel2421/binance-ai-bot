"""
Unit tests for Deriv Contract Settlement Tracker (DerivSettlementTracker).
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
import time

from src.api.deriv_client import DerivClient
from src.execution.trade_journal import CryptoTradeJournal, JournalRecord
from src.execution.settlement_tracker import DerivSettlementTracker


@pytest.fixture
def mock_client():
    client = MagicMock(spec=DerivClient)
    client.subscribe = AsyncMock(return_value="sub_123456")
    return client


@pytest.fixture
def temp_journal(tmp_path):
    db_file = str(tmp_path / "test_settlement_journal.db")
    journal = CryptoTradeJournal(db_path=db_file)
    rec = JournalRecord(
        record_id="rec_paper_1",
        record_type="PAPER_TRADE",
        timestamp=time.time(),
        symbol="cryBTCUSD",
        direction="BULLISH",
        contract_type="CALL",
        duration=1,
        duration_unit="m",
        stake=15.0,
        ask_price=15.0,
        payout=30.0,
        spot_entry=50000.0,
        opportunity_score=58.0,
        calibrated_probability=0.62,
        ev=3.60,
        status="OPEN",
    )
    journal.log_record(rec)
    return journal


@pytest.mark.asyncio
async def test_settlement_tracker_subscribe_contract(mock_client, temp_journal):
    tracker = DerivSettlementTracker(client=mock_client, trade_journal=temp_journal)
    success = await tracker.subscribe_contract(contract_id="123456789", record_id="rec_paper_1", symbol="cryBTCUSD")
    assert success is True
    assert "123456789" in tracker.tracked_contracts
    assert tracker.tracked_contracts["123456789"]["record_id"] == "rec_paper_1"


def test_settlement_tracker_on_poc_message_won(mock_client, temp_journal):
    tracker = DerivSettlementTracker(client=mock_client, trade_journal=temp_journal)
    tracker.tracked_contracts["123456789"] = {
        "record_id": "rec_paper_1",
        "symbol": "cryBTCUSD",
        "subscription_id": "sub_123",
        "subscribed_at": time.time(),
    }

    poc_msg = {
        "msg_type": "proposal_open_contract",
        "proposal_open_contract": {
            "contract_id": "123456789",
            "is_sold": 1,
            "is_expired": 1,
            "is_settled": 1,
            "status": "won",
            "profit": 15.0,
            "payout": 30.0,
            "exit_tick": 50150.0,
        }
    }

    tracker._on_poc_message(poc_msg, contract_id="123456789")
    assert "123456789" not in tracker.tracked_contracts
    assert "123456789" in tracker.settled_history
    assert tracker.settled_history["123456789"].status == "WON"
    assert tracker.settled_history["123456789"].profit == 15.0

    summary = temp_journal.get_summary()
    assert summary["status_counts"].get("WON", 0) == 1
    assert summary["total_paper_pnl"] == 15.0
