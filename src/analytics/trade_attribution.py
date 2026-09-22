"""
Trade Attribution, Loss/Win Analysis & Drawdown Tracker for Deriv Crypto AI Bot Stage 7.

Provides detailed loss attribution, winning trade characteristics analysis, losing streak clustering,
and equity curve drawdown episode tracking.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import time
import logging

from src.execution.trade_journal import JournalRecord

logger = logging.getLogger("TRADE_ATTRIBUTION")


@dataclass
class TradeAttributionRecord:
    record_id: str
    symbol: str
    status: str
    pnl: float
    cause_classification: str                   # "SIGNAL_FAILURE", "REGIME_CHANGE", etc.
    explanation: str


@dataclass
class DrawdownEpisode:
    episode_id: int
    start_time: float
    trough_time: float
    recovery_time: Optional[float]
    loss_amount: float
    loss_pct: float
    is_recovered: bool


class LossCause:
    SIGNAL_FAILURE = "SIGNAL_FAILURE"
    TIMING_FAILURE = "TIMING_FAILURE"
    REGIME_CHANGE = "REGIME_CHANGE"
    FALSE_BREAKOUT = "FALSE_BREAKOUT"
    TREND_REVERSAL = "TREND_REVERSAL"
    VOLATILITY_SPIKE = "VOLATILITY_SPIKE"
    MODEL_OVERCONFIDENCE = "MODEL_OVERCONFIDENCE"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class TradeAttributionEngine:
    """
    Analyzes winning and losing trade records to attribute outcome factors.
    """

    @classmethod
    def analyze_losses(cls, records: List[JournalRecord]) -> List[TradeAttributionRecord]:
        losing = [r for r in records if r.status == "LOST"]
        attributions = []

        for r in losing:
            # Classify cause based on empirical trade attributes
            if r.opportunity_score >= 80.0 and r.calibrated_probability >= 0.65:
                cause = LossCause.MODEL_OVERCONFIDENCE
                expl = f"High score ({r.opportunity_score:.1f}) and high prob ({r.calibrated_probability:.2f}) trade failed"
            elif r.contract_type in ("MULTUP", "MULTDOWN"):
                cause = LossCause.VOLATILITY_SPIKE
                expl = "Multiplier trade stopped out due to adverse price volatility move"
            elif r.opportunity_score < 55.0:
                cause = LossCause.SIGNAL_FAILURE
                expl = f"Low setup score ({r.opportunity_score:.1f}) failed"
            else:
                cause = LossCause.UNKNOWN
                expl = "Insufficient secondary telemetry data to isolate root failure cause"

            attributions.append(TradeAttributionRecord(
                record_id=r.record_id,
                symbol=r.symbol,
                status=r.status,
                pnl=r.pnl,
                cause_classification=cause,
                explanation=expl,
            ))

        return attributions

    @classmethod
    def analyze_drawdown_episodes(
        cls,
        records: List[JournalRecord],
        initial_capital: float = 1000.0,
    ) -> List[DrawdownEpisode]:
        closed = [r for r in records if r.status in ("WON", "LOST", "PUSH")]
        if not closed:
            return []

        episodes: List[DrawdownEpisode] = []
        running_balance = initial_capital
        peak_balance = initial_capital
        peak_time = closed[0].timestamp

        in_drawdown = False
        current_episode_start = peak_time
        trough_balance = peak_balance
        trough_time = peak_time
        episode_counter = 0

        for r in closed:
            running_balance += r.pnl
            t = r.timestamp

            if running_balance >= peak_balance:
                if in_drawdown:
                    # Episode recovered
                    episode_counter += 1
                    loss_amt = peak_balance - trough_balance
                    loss_pct = (loss_amt / peak_balance * 100.0) if peak_balance > 0 else 0.0
                    episodes.append(DrawdownEpisode(
                        episode_id=episode_counter,
                        start_time=current_episode_start,
                        trough_time=trough_time,
                        recovery_time=t,
                        loss_amount=round(loss_amt, 2),
                        loss_pct=round(loss_pct, 2),
                        is_recovered=True,
                    ))
                    in_drawdown = False

                peak_balance = running_balance
                peak_time = t
                trough_balance = peak_balance
                trough_time = peak_time
            else:
                if not in_drawdown:
                    in_drawdown = True
                    current_episode_start = peak_time
                    trough_balance = running_balance
                    trough_time = t
                else:
                    if running_balance < trough_balance:
                        trough_balance = running_balance
                        trough_time = t

        if in_drawdown:
            episode_counter += 1
            loss_amt = peak_balance - trough_balance
            loss_pct = (loss_amt / peak_balance * 100.0) if peak_balance > 0 else 0.0
            episodes.append(DrawdownEpisode(
                episode_id=episode_counter,
                start_time=current_episode_start,
                trough_time=trough_time,
                recovery_time=None,
                loss_amount=round(loss_amt, 2),
                loss_pct=round(loss_pct, 2),
                is_recovered=False,
            ))

        return episodes
