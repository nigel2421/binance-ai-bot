import pytest
import time
from src.execution.trade_journal import JournalRecord
from src.analytics.session_manager import ForwardTestSessionManager, ForwardTestSession


def test_session_manager_lifecycle(tmp_path):
    db_file = str(tmp_path / "test_sessions.db")
    mgr = ForwardTestSessionManager(db_path=db_file)

    sess = mgr.start_session(opening_balance=1000.0)
    assert sess.session_id.startswith("sess_")
    assert sess.status == "ACTIVE"

    mgr.end_session(
        session_id=sess.session_id,
        closing_balance=1050.0,
        trades_count=5,
        wins=3,
        losses=2,
        net_pnl=50.0,
        max_drawdown=10.0,
    )


def test_period_filtering():
    now = time.time()
    r1 = JournalRecord(
        record_id="t1", record_type="PAPER_TRADE", timestamp=now - 3600, symbol="cryBTCUSD",
        direction="BULLISH", contract_type="CALL", duration=1, duration_unit="m",
        stake=10.0, ask_price=10.0, payout=20.0, spot_entry=50000.0, status="WON", pnl=10.0
    )
    r2 = JournalRecord(
        record_id="t2", record_type="PAPER_TRADE", timestamp=now - (10 * 86400), symbol="cryBTCUSD",
        direction="BULLISH", contract_type="CALL", duration=1, duration_unit="m",
        stake=10.0, ask_price=10.0, payout=20.0, spot_entry=50000.0, status="WON", pnl=10.0
    )

    filtered_today = ForwardTestSessionManager.filter_records_by_period([r1, r2], "today")
    assert len(filtered_today) == 1
    assert filtered_today[0].record_id == "t1"

    filtered_7d = ForwardTestSessionManager.filter_records_by_period([r1, r2], "7d")
    assert len(filtered_7d) == 1

    filtered_all = ForwardTestSessionManager.filter_records_by_period([r1, r2], "all")
    assert len(filtered_all) == 2
