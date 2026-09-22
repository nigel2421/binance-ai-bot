"""
Model Validation Engine for Deriv Crypto AI Bot Stage 7.

Provides empirical validation reports for:
1. Probability Calibration (Predicted P(win) vs Actual Win Rate by bands, Brier Score & Error)
2. Opportunity Score Validation (Score Bands vs Win Rate, PnL, Profit Factor)
3. Expected Value Validation (EV Bands vs Realized Return & Win Rate)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import math
import logging

from src.execution.trade_journal import JournalRecord

logger = logging.getLogger("MODEL_VALIDATION")


@dataclass
class ProbabilityCalibrationReport:
    total_samples: int = 0
    overall_brier_score: float = 0.25
    overall_calibration_error: float = 0.0
    is_calibrated: bool = False
    probability_bands: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class OpportunityScoreValidationReport:
    total_samples: int = 0
    is_monotonic: bool = False
    score_bands: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class ExpectedValueValidationReport:
    total_samples: int = 0
    is_predictive: bool = False
    ev_bands: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class ProbabilityCalibrationValidator:
    """Validates predicted win probability accuracy against actual outcome frequency."""

    PROB_BANDS = [
        ("50-54%", 0.50, 0.55),
        ("55-59%", 0.55, 0.60),
        ("60-64%", 0.60, 0.65),
        ("65-69%", 0.65, 0.70),
        ("70%+", 0.70, 1.01),
    ]

    @classmethod
    def validate(cls, records: List[JournalRecord]) -> ProbabilityCalibrationReport:
        closed = [r for r in records if r.status in ("WON", "LOST")]
        if not closed:
            return ProbabilityCalibrationReport()

        total = len(closed)
        brier_sum = 0.0
        error_sum = 0.0
        bands_data = {}

        for band_label, p_min, p_max in cls.PROB_BANDS:
            band_recs = [r for r in closed if p_min <= r.calibrated_probability < p_max]
            b_count = len(band_recs)
            if b_count > 0:
                wins = sum(1 for r in band_recs if r.status == "WON")
                actual_wr = wins / b_count
                avg_pred = sum(r.calibrated_probability for r in band_recs) / b_count
                calib_err = abs(actual_wr - avg_pred)
                b_score = sum((r.calibrated_probability - (1.0 if r.status == "WON" else 0.0)) ** 2 for r in band_recs) / b_count

                bands_data[band_label] = {
                    "count": b_count,
                    "avg_predicted_prob": round(avg_pred, 4),
                    "actual_win_rate": round(actual_wr, 4),
                    "calibration_error": round(calib_err, 4),
                    "brier_score": round(b_score, 4),
                }
            else:
                bands_data[band_label] = {
                    "count": 0,
                    "avg_predicted_prob": 0.0,
                    "actual_win_rate": 0.0,
                    "calibration_error": 0.0,
                    "brier_score": 0.0,
                }

        # Overall metrics
        for r in closed:
            actual = 1.0 if r.status == "WON" else 0.0
            pred = r.calibrated_probability
            brier_sum += (pred - actual) ** 2
            error_sum += abs(pred - actual)

        overall_brier = brier_sum / total
        overall_error = error_sum / total

        return ProbabilityCalibrationReport(
            total_samples=total,
            overall_brier_score=round(overall_brier, 4),
            overall_calibration_error=round(overall_error, 4),
            is_calibrated=(overall_brier < 0.25 and overall_error < 0.15),
            probability_bands=bands_data,
        )


class OpportunityScoreValidator:
    """Validates whether higher Opportunity Scores produce superior win rates and EV."""

    SCORE_BANDS = [
        ("<50", 0.0, 50.0),
        ("50-59", 50.0, 60.0),
        ("60-69", 60.0, 70.0),
        ("70-79", 70.0, 80.0),
        ("80-89", 80.0, 90.0),
        ("90-100", 90.0, 100.1),
    ]

    @classmethod
    def validate(cls, records: List[JournalRecord]) -> OpportunityScoreValidationReport:
        closed = [r for r in records if r.status in ("WON", "LOST")]
        if not closed:
            return OpportunityScoreValidationReport()

        total = len(closed)
        bands_data = {}
        prev_wr = -1.0
        is_monotonic = True

        for band_label, s_min, s_max in cls.SCORE_BANDS:
            band_recs = [r for r in closed if s_min <= r.opportunity_score < s_max]
            b_count = len(band_recs)
            if b_count > 0:
                wins = sum(1 for r in band_recs if r.status == "WON")
                actual_wr = wins / b_count
                avg_ev = sum(r.ev for r in band_recs) / b_count
                net_pnl = sum(r.pnl for r in band_recs)
                profits = sum(r.pnl for r in band_recs if r.pnl > 0)
                losses = sum(abs(r.pnl) for r in band_recs if r.pnl < 0)
                pf = (profits / losses) if losses > 0 else (999.0 if profits > 0 else 0.0)

                bands_data[band_label] = {
                    "count": b_count,
                    "win_rate": round(actual_wr * 100.0, 2),
                    "avg_ev": round(avg_ev, 2),
                    "net_pnl": round(net_pnl, 2),
                    "profit_factor": round(pf, 2),
                }

                if prev_wr >= 0 and actual_wr < prev_wr:
                    is_monotonic = False
                prev_wr = actual_wr
            else:
                bands_data[band_label] = {
                    "count": 0,
                    "win_rate": 0.0,
                    "avg_ev": 0.0,
                    "net_pnl": 0.0,
                    "profit_factor": 0.0,
                }

        return OpportunityScoreValidationReport(
            total_samples=total,
            is_monotonic=is_monotonic,
            score_bands=bands_data,
        )


class ExpectedValueValidator:
    """Validates whether entry expected value (EV) predicts realized trade returns."""

    EV_BANDS = [
        ("<0%", -999.0, 0.0),
        ("0-2%", 0.0, 0.20),
        ("2-5%", 0.20, 0.50),
        ("5-10%", 0.50, 1.00),
        ("10%+", 1.00, 999.0),
    ]

    @classmethod
    def validate(cls, records: List[JournalRecord]) -> ExpectedValueValidationReport:
        closed = [r for r in records if r.status in ("WON", "LOST")]
        if not closed:
            return ExpectedValueValidationReport()

        total = len(closed)
        bands_data = {}
        positive_ev_recs = [r for r in closed if r.ev > 0]
        pos_pnl = sum(r.pnl for r in positive_ev_recs) if positive_ev_recs else 0.0
        is_predictive = (pos_pnl > 0)

        for band_label, ev_min, ev_max in cls.EV_BANDS:
            band_recs = [r for r in closed if ev_min <= r.ev < ev_max]
            b_count = len(band_recs)
            if b_count > 0:
                wins = sum(1 for r in band_recs if r.status == "WON")
                actual_wr = wins / b_count
                avg_ev = sum(r.ev for r in band_recs) / b_count
                actual_ret = sum(r.pnl for r in band_recs) / b_count
                profits = sum(r.pnl for r in band_recs if r.pnl > 0)
                losses = sum(abs(r.pnl) for r in band_recs if r.pnl < 0)
                pf = (profits / losses) if losses > 0 else (999.0 if profits > 0 else 0.0)

                bands_data[band_label] = {
                    "count": b_count,
                    "avg_predicted_ev": round(avg_ev, 2),
                    "actual_avg_return": round(actual_ret, 2),
                    "win_rate": round(actual_wr * 100.0, 2),
                    "profit_factor": round(pf, 2),
                }
            else:
                bands_data[band_label] = {
                    "count": 0,
                    "avg_predicted_ev": 0.0,
                    "actual_avg_return": 0.0,
                    "win_rate": 0.0,
                    "profit_factor": 0.0,
                }

        return ExpectedValueValidationReport(
            total_samples=total,
            is_predictive=is_predictive,
            ev_bands=bands_data,
        )
