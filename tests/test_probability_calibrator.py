import pytest
from src.analytics.probability_calibrator import (
    ProbabilityCalibrator,
    ForwardObservationRecord,
    CalibrationResult,
)


def test_insufficient_sample_gating():
    calibrator = ProbabilityCalibrator()
    # Add only 10 observations (less than MIN_SAMPLE_SIZE = 30)
    for i in range(10):
        calibrator.add_observation(
            ForwardObservationRecord(opportunity_score=55.0, direction="BULLISH", win=True)
        )

    res = calibrator.calibrate(opportunity_score=55.0)
    assert res.calibrated is False
    assert res.reliability == "INSUFFICIENT_SAMPLE"
    assert res.estimated_probability == 0.50


def test_sufficient_sample_calibration():
    calibrator = ProbabilityCalibrator()
    # Add 40 observations for 50-60 band, 24 wins (60% win rate)
    for i in range(40):
        win = (i < 24)
        calibrator.add_observation(
            ForwardObservationRecord(opportunity_score=55.0, direction="BULLISH", win=win, predicted_prob=0.6)
        )

    res = calibrator.calibrate(opportunity_score=55.0)
    assert res.calibrated is True
    assert res.sample_size == 40
    assert res.estimated_probability == 0.60
    assert res.reliability == "LOW"  # 30 <= N < 50
    assert res.brier_score < 0.30


def test_regime_hierarchical_fallback():
    calibrator = ProbabilityCalibrator()
    # Add 35 observations for score 55.0 with regime RANGING
    for i in range(35):
        calibrator.add_observation(
            ForwardObservationRecord(opportunity_score=55.0, direction="BULLISH", win=(i % 2 == 0), regime="RANGING")
        )
    # Add 5 observations for score 55.0 with regime UPTREND
    for i in range(5):
        calibrator.add_observation(
            ForwardObservationRecord(opportunity_score=55.0, direction="BULLISH", win=True, regime="UPTREND")
        )

    # Request UPTREND: should fall back to score band 50-60 overall (N=40) since UPTREND alone has N=5
    res = calibrator.calibrate(opportunity_score=55.0, regime="UPTREND")
    assert res.calibrated is True
    assert res.sample_size == 40
    assert res.regime is None  # Fallback cleared specific regime
