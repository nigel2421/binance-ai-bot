import pytest
from src.execution.trade_journal import JournalRecord
from src.analytics.performance_engine import PerformanceEngine, PerformanceSummary


def test_performance_engine_empty_records():
    summary = PerformanceEngine.calculate_global_performance([])
    assert summary.total_records == 0
    assert summary.win_rate == 0.0
    assert summary.net_pnl == 0.0


def test_performance_engine_global_calculation():
    records = [
        JournalRecord(
            record_id="t1", record_type="PAPER_TRADE", timestamp=100.0, symbol="cryBTCUSD",
            direction="BULLISH", contract_type="CALL", duration=1, duration_unit="m",
            stake=10.0, ask_price=10.0, payout=20.0, spot_entry=50000.0, spot_exit=50500.0,
            opportunity_score=65.0, calibrated_probability=0.60, ev=2.0, status="WON", pnl=10.0
        ),
        JournalRecord(
            record_id="t2", record_type="PAPER_TRADE", timestamp=110.0, symbol="cryBTCUSD",
            direction="BULLISH", contract_type="CALL", duration=1, duration_unit="m",
            stake=10.0, ask_price=10.0, payout=20.0, spot_entry=50000.0, spot_exit=49500.0,
            opportunity_score=55.0, calibrated_probability=0.55, ev=1.0, status="LOST", pnl=-10.0
        ),
        JournalRecord(
            record_id="t3", record_type="PAPER_TRADE", timestamp=120.0, symbol="cryETHUSD",
            direction="BEARISH", contract_type="PUT", duration=1, duration_unit="m",
            stake=10.0, ask_price=10.0, payout=20.0, spot_entry=3000.0, spot_exit=2950.0,
            opportunity_score=75.0, calibrated_probability=0.65, ev=3.0, status="WON", pnl=10.0
        ),
    ]

    summary = PerformanceEngine.calculate_global_performance(records, initial_capital=1000.0)
    assert summary.total_records == 3
    assert summary.paper_trades == 3
    assert summary.wins == 2
    assert summary.losses == 1
    assert summary.win_rate == pytest.approx(66.6666, abs=0.01)
    assert summary.gross_profit == 20.0
    assert summary.gross_loss == 10.0
    assert summary.net_pnl == 10.0
    assert summary.profit_factor == 2.0
    assert summary.avg_profit == 10.0
    assert summary.avg_loss == 10.0
    # Expectancy: (0.6667 * 10) - (0.3333 * 10) = 3.3333
    assert summary.expectancy == pytest.approx(3.3333, abs=0.01)


def test_performance_engine_dimensional_breakdown():
    records = [
        JournalRecord(
            record_id="t1", record_type="PAPER_TRADE", timestamp=100.0, symbol="cryBTCUSD",
            direction="BULLISH", contract_type="CALL", duration=1, duration_unit="m",
            stake=10.0, ask_price=10.0, payout=20.0, spot_entry=50000.0, spot_exit=50500.0,
            opportunity_score=65.0, calibrated_probability=0.60, ev=2.0, status="WON", pnl=10.0
        ),
        JournalRecord(
            record_id="t2", record_type="PAPER_TRADE", timestamp=110.0, symbol="cryETHUSD",
            direction="BEARISH", contract_type="PUT", duration=1, duration_unit="m",
            stake=10.0, ask_price=10.0, payout=20.0, spot_entry=3000.0, spot_exit=3050.0,
            opportunity_score=55.0, calibrated_probability=0.55, ev=1.0, status="LOST", pnl=-10.0
        ),
    ]

    by_sym = PerformanceEngine.calculate_performance_by_dimension(records, "symbol")
    assert "cryBTCUSD" in by_sym
    assert "cryETHUSD" in by_sym
    assert by_sym["cryBTCUSD"].wins == 1
    assert by_sym["cryETHUSD"].losses == 1
