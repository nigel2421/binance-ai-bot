"""
Expected Value (EV) Engine.

Calculates mathematical expected value:
EV = P_est * Payout - Stake

Enforces EV_SAFETY_MARGIN (P_est > P_breakeven + EV_SAFETY_MARGIN) and MIN_PROBABILITY_EDGE.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import logging

from src.execution.proposal_engine import ContractEconomics
from src.analytics.probability_calibrator import CalibrationResult

logger = logging.getLogger("ExpectedValueEngine")


class EVState(Enum):
    POSITIVE_STRONG = "POSITIVE_STRONG"
    POSITIVE = "POSITIVE"
    MARGINAL = "MARGINAL"
    NEGATIVE = "NEGATIVE"
    UNCALIBRATED = "UNCALIBRATED"


@dataclass
class EVResult:
    ev: float
    ev_pct: float
    probability_edge: float
    breakeven_probability: float
    estimated_probability: float
    ev_state: EVState
    is_tradable: bool
    rejection_reason: Optional[str] = None


class ExpectedValueEngine:
    """
    Evaluates expected monetary and percentage return for a contract proposal
    given calibrated win probability.
    """

    def __init__(
        self,
        ev_safety_margin: float = 0.03,  # Minimum 3% probability buffer above breakeven
        min_probability_edge: float = 0.03, # Minimum 3% edge
    ):
        self.ev_safety_margin = ev_safety_margin
        self.min_probability_edge = min_probability_edge

    def evaluate(
        self,
        economics: ContractEconomics,
        calibration: CalibrationResult,
    ) -> EVResult:
        if not calibration.calibrated or calibration.reliability == "INSUFFICIENT_SAMPLE":
            return EVResult(
                ev=0.0,
                ev_pct=0.0,
                probability_edge=0.0,
                breakeven_probability=economics.breakeven_probability,
                estimated_probability=calibration.estimated_probability,
                ev_state=EVState.UNCALIBRATED,
                is_tradable=False,
                rejection_reason=f"Insufficient calibration sample (reliability: {calibration.reliability})"
            )

        p_est = calibration.estimated_probability
        p_breakeven = economics.breakeven_probability
        stake = economics.ask_price
        payout = economics.payout

        # Expected Value formula: EV = P_est * Payout - Stake
        ev = (p_est * payout) - stake
        ev_pct = (ev / stake * 100.0) if stake > 0 else 0.0
        edge = p_est - p_breakeven

        # Check safety margins
        rejection_reason = None
        if ev <= 0:
            state = EVState.NEGATIVE
            is_tradable = False
            rejection_reason = f"Negative expected value (EV: {ev:.4f}, EV%: {ev_pct:.2f}%)"
        elif edge < self.min_probability_edge:
            state = EVState.MARGINAL
            is_tradable = False
            rejection_reason = f"Edge {edge:.4f} below min required edge {self.min_probability_edge:.4f}"
        elif p_est < (p_breakeven + self.ev_safety_margin):
            state = EVState.MARGINAL
            is_tradable = False
            rejection_reason = f"P_est {p_est:.4f} below breakeven + safety margin ({p_breakeven + self.ev_safety_margin:.4f})"
        else:
            is_tradable = True
            if edge >= 0.08 and p_est >= (p_breakeven + 0.05):
                state = EVState.POSITIVE_STRONG
            else:
                state = EVState.POSITIVE

        return EVResult(
            ev=ev,
            ev_pct=ev_pct,
            probability_edge=edge,
            breakeven_probability=p_breakeven,
            estimated_probability=p_est,
            ev_state=state,
            is_tradable=is_tradable,
            rejection_reason=rejection_reason,
        )
