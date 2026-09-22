import pytest
from src.execution.trade_journal import JournalRecord
from src.analytics.model_validation import (
    ProbabilityCalibrationValidator,
    OpportunityScoreValidator,
    ExpectedValueValidator,
)


def test_probability_calibration_validation():
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

    report = ProbabilityCalibrationValidator.validate(records)
    assert report.total_samples == 2
    assert "60-64%" in report.probability_bands
    assert report.probability_bands["60-64%"]["count"] == 1
    assert report.probability_bands["60-64%"]["actual_win_rate"] == 1.0


def test_opportunity_score_and_ev_validation():
    records = [
        JournalRecord(
            record_id="t1", record_type="PAPER_TRADE", timestamp=100.0, symbol="cryBTCUSD",
            direction="BULLISH", contract_type="CALL", duration=1, duration_unit="m",
            stake=10.0, ask_price=10.0, payout=20.0, spot_entry=50000.0, spot_exit=50500.0,
            opportunity_score=65.0, calibrated_probability=0.60, ev=2.0, status="WON", pnl=10.0
        ),
    ]

    score_report = OpportunityScoreValidator.validate(records)
    assert score_report.total_samples == 1
    assert score_report.score_bands["60-69"]["count"] == 1

    ev_report = ExpectedValueValidator.validate(records)
    assert ev_report.total_samples == 1
    assert ev_report.is_predictive is True
