"""
Empirical Probability Calibration Engine.

Maps opportunity scores, market regimes, and strategy combinations to
empirical win rates from historical observation outcomes (N >= 30).
Opportunity Score is NOT equal to P(win). P(win) is calibrated empirically.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import math
import logging

logger = logging.getLogger("ProbabilityCalibrator")


@dataclass
class CalibrationResult:
    estimated_probability: float
    sample_size: int
    uncertainty: float
    reliability: str  # "HIGH", "MODERATE", "LOW", "INSUFFICIENT_SAMPLE"
    brier_score: float
    calibrated: bool
    score_band: str
    regime: Optional[str] = None


@dataclass
class ForwardObservationRecord:
    opportunity_score: float
    direction: str
    win: bool
    regime: Optional[str] = None
    predicted_prob: float = 0.5


class ProbabilityCalibrator:
    """
    Calibrates directional win probability from empirical historical forward observations.
    Requires N >= 30 observations per bucket to consider calibration valid.
    """

    MIN_SAMPLE_SIZE: int = 30

    def __init__(self, observations: Optional[List[ForwardObservationRecord]] = None):
        self.observations: List[ForwardObservationRecord] = observations or []

    def add_observation(self, obs: ForwardObservationRecord) -> None:
        self.observations.append(obs)

    def add_observations(self, obs_list: List[ForwardObservationRecord]) -> None:
        self.observations.extend(obs_list)

    def _get_score_band(self, score: float) -> str:
        if score < 50.0:
            return "<50"
        elif score < 60.0:
            return "50-60"
        elif score < 70.0:
            return "60-70"
        elif score < 80.0:
            return "70-80"
        else:
            return "80+"

    def calibrate(self, opportunity_score: float, regime: Optional[str] = None) -> CalibrationResult:
        """
        Calculates empirical win rate for a given opportunity score and optional regime.
        Falls back to score-only band if score+regime has N < 30.
        Returns INSUFFICIENT_SAMPLE if score band also has N < 30.
        """
        target_band = self._get_score_band(opportunity_score)

        # 1. Try score_band + regime matching if regime provided
        matching_obs = []
        used_regime = None
        if regime:
            regime_obs = [
                obs for obs in self.observations
                if self._get_score_band(obs.opportunity_score) == target_band and obs.regime == regime
            ]
            if len(regime_obs) >= self.MIN_SAMPLE_SIZE:
                matching_obs = regime_obs
                used_regime = regime

        # 2. Hierarchical fallback to score_band alone if sample < MIN_SAMPLE_SIZE
        if len(matching_obs) < self.MIN_SAMPLE_SIZE:
            matching_obs = [
                obs for obs in self.observations
                if self._get_score_band(obs.opportunity_score) == target_band
            ]
            used_regime = None
        
        if len(matching_obs) < self.MIN_SAMPLE_SIZE:
            # Check if all observations combined meet MIN_SAMPLE_SIZE
            if len(self.observations) >= self.MIN_SAMPLE_SIZE:
                matching_obs = self.observations
                target_band = "ALL"
            else:
                # Total observations insufficient
                return CalibrationResult(
                    estimated_probability=0.50,
                    sample_size=len(matching_obs),
                    uncertainty=1.0,
                    reliability="INSUFFICIENT_SAMPLE",
                    brier_score=0.25,
                    calibrated=False,
                    score_band=target_band,
                    regime=used_regime,
                )

        sample_size = len(matching_obs)
        wins = sum(1 for obs in matching_obs if obs.win)
        p_est = wins / sample_size

        # Standard error SE = sqrt(p * (1-p) / N)
        se = math.sqrt(p_est * (1.0 - p_est) / sample_size) if sample_size > 0 else 0.5

        # Calculate Brier Score = (1/N) * sum((f_i - o_i)^2)
        brier_sum = 0.0
        for obs in matching_obs:
            actual = 1.0 if obs.win else 0.0
            pred = obs.predicted_prob if obs.predicted_prob is not None else p_est
            brier_sum += (pred - actual) ** 2
        brier_score = brier_sum / sample_size if sample_size > 0 else 0.25

        # Determine reliability tag
        if sample_size >= 100 and se <= 0.05:
            reliability = "HIGH"
        elif sample_size >= 50:
            reliability = "MODERATE"
        elif sample_size >= 30:
            reliability = "LOW"
        else:
            reliability = "INSUFFICIENT_SAMPLE"

        return CalibrationResult(
            estimated_probability=p_est,
            sample_size=sample_size,
            uncertainty=se,
            reliability=reliability,
            brier_score=brier_score,
            calibrated=True,
            score_band=target_band,
            regime=used_regime,
        )
