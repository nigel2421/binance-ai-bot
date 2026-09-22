import pytest
from src.execution.proposal_engine import ContractEconomics
from src.analytics.probability_calibrator import CalibrationResult
from src.execution.expected_value_engine import (
    ExpectedValueEngine,
    EVState,
    EVResult,
)


def test_ev_uncalibrated_rejection():
    engine = ExpectedValueEngine()
    econ = ContractEconomics(
        ask_price=10.0,
        payout=19.50,
        net_profit=9.50,
        max_loss=10.0,
        net_return_pct=95.0,
        breakeven_probability=10.0 / 19.50, # ~0.5128
        spot_price=50000.0
    )
    uncal = CalibrationResult(
        estimated_probability=0.60,
        sample_size=15,
        uncertainty=0.1,
        reliability="INSUFFICIENT_SAMPLE",
        brier_score=0.25,
        calibrated=False,
        score_band="50-60"
    )

    res = engine.evaluate(econ, uncal)
    assert res.is_tradable is False
    assert res.ev_state == EVState.UNCALIBRATED
    assert "Insufficient calibration sample" in res.rejection_reason


def test_ev_positive_strong():
    engine = ExpectedValueEngine(ev_safety_margin=0.03, min_probability_edge=0.03)
    econ = ContractEconomics(
        ask_price=10.0,
        payout=20.00,
        net_profit=10.0,
        max_loss=10.0,
        net_return_pct=100.0,
        breakeven_probability=0.50,
        spot_price=50000.0
    )
    cal = CalibrationResult(
        estimated_probability=0.62,  # P_est = 0.62, edge = 0.12, breakeven + 0.05 = 0.55
        sample_size=100,
        uncertainty=0.04,
        reliability="HIGH",
        brier_score=0.20,
        calibrated=True,
        score_band="60-70"
    )

    res = engine.evaluate(econ, cal)
    assert res.is_tradable is True
    assert res.ev_state == EVState.POSITIVE_STRONG
    assert res.ev == pytest.approx(0.62 * 20.0 - 10.0)  # 12.4 - 10 = 2.40
    assert res.probability_edge == pytest.approx(0.12)


def test_ev_negative_or_marginal_rejection():
    engine = ExpectedValueEngine(ev_safety_margin=0.05, min_probability_edge=0.05)
    econ = ContractEconomics(
        ask_price=10.0,
        payout=18.00,
        net_profit=8.0,
        max_loss=10.0,
        net_return_pct=80.0,
        breakeven_probability=10.0 / 18.00, # ~0.5556
        spot_price=50000.0
    )
    # Calibrated P_est = 0.57. Edge = 0.57 - 0.5556 = 0.0144 < 0.05
    cal = CalibrationResult(
        estimated_probability=0.57,
        sample_size=60,
        uncertainty=0.05,
        reliability="MODERATE",
        brier_score=0.22,
        calibrated=True,
        score_band="50-60"
    )

    res = engine.evaluate(econ, cal)
    assert res.is_tradable is False
    assert res.ev_state == EVState.MARGINAL
    assert "below min required edge" in res.rejection_reason
