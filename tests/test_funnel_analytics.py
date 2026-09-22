import pytest
from src.execution.trade_journal import JournalRecord
from src.analytics.funnel_analytics import TradeFunnelAnalytics, TradeFunnelReport


def test_funnel_analytics_calculation():
    records = [
        JournalRecord(
            record_id="r1", record_type="REJECTION", timestamp=100.0, symbol="cryBTCUSD",
            direction="BULLISH", contract_type="NONE", duration=0, duration_unit="m",
            stake=0.0, ask_price=0.0, payout=0.0, spot_entry=0.0, status="REJECTED",
            rejection_stage="LOW_OPPORTUNITY_SCORE", rejection_reason="Score 45 below threshold 50"
        ),
        JournalRecord(
            record_id="r2", record_type="REJECTION", timestamp=110.0, symbol="cryBTCUSD",
            direction="BULLISH", contract_type="CALL", duration=1, duration_unit="m",
            stake=10.0, ask_price=10.0, payout=19.0, spot_entry=50000.0, status="REJECTED",
            rejection_stage="NEGATIVE_EV", rejection_reason="EV non-positive"
        ),
        JournalRecord(
            record_id="t1", record_type="PAPER_TRADE", timestamp=120.0, symbol="cryBTCUSD",
            direction="BULLISH", contract_type="CALL", duration=1, duration_unit="m",
            stake=10.0, ask_price=10.0, payout=20.0, spot_entry=50000.0, spot_exit=50500.0,
            opportunity_score=65.0, calibrated_probability=0.60, ev=2.0, status="WON", pnl=10.0
        ),
    ]

    report = TradeFunnelAnalytics.analyze_funnel(records)
    assert report.total_evaluations == 3
    assert report.total_rejections == 2
    assert len(report.rejection_gates) > 0
    # Top rejection gate should be LOW_OPPORTUNITY_SCORE or NEGATIVE_EV
    top_gate = report.rejection_gates[0].gate_name
    assert top_gate in ("LOW_OPPORTUNITY_SCORE", "NEGATIVE_EV")
