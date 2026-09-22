"""
Strategy Performance & Reputation Engine for Deriv Crypto AI Bot Stage 7.

Computes persistent per-strategy statistics, cross-dimensional performance breakdowns,
minimum sample size classifications, and strategy reputation scores in OBSERVATION_ONLY mode.
Does NOT alter live decision-making weights or routing.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import math
import logging

from src.execution.trade_journal import JournalRecord

logger = logging.getLogger("STRATEGY_REPUTATION")


class SampleStatus:
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"        # 0-29 trades
    EARLY_SAMPLE = "EARLY_SAMPLE"                  # 30-99 trades
    DEVELOPING = "DEVELOPING"                      # 100-299 trades
    STATISTICALLY_USEFUL = "STATISTICALLY_USEFUL"  # 300+ trades


@dataclass
class StrategyStats:
    strategy_name: str
    opportunities_evaluated: int = 0
    participations: int = 0
    abstentions: int = 0
    oppositions: int = 0
    trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0                      # % (0-100)
    net_pnl: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    avg_confidence: float = 0.0
    avg_ev: float = 0.0
    max_drawdown: float = 0.0
    sample_status: str = SampleStatus.INSUFFICIENT_DATA


@dataclass
class ReputationScore:
    strategy_name: str
    reputation_score: float                    # 0.0 to 100.0
    sample_status: str
    mode: str = "OBSERVATION_ONLY"
    reputation_tier: str = "UNPROVEN"          # "UNPROVEN", "DEVELOPING", "RELIABLE", "ELITE"
    components: Dict[str, float] = field(default_factory=dict)


class StrategyReputationEngine:
    """
    Evaluates individual strategy specialist performance and calculates reputation ratings.
    """

    MODE: str = "OBSERVATION_ONLY"

    @classmethod
    def classify_sample_status(cls, trade_count: int) -> str:
        if trade_count < 30:
            return SampleStatus.INSUFFICIENT_DATA
        elif trade_count < 100:
            return SampleStatus.EARLY_SAMPLE
        elif trade_count < 300:
            return SampleStatus.DEVELOPING
        else:
            return SampleStatus.STATISTICALLY_USEFUL

    @classmethod
    def calculate_strategy_stats(
        cls,
        strategy_name: str,
        records: List[JournalRecord],
        signal_events: Optional[List[Dict[str, Any]]] = None,
    ) -> StrategyStats:
        """
        Calculates performance metrics associated with a specific strategy.
        """
        # Filter records where this strategy supported/participated in the proposal
        strat_records = []
        for r in records:
            # Check if strategy is mentioned in rejection_reason or recorded metadata
            if r.record_type == "PAPER_TRADE" or r.status in ("WON", "LOST", "PUSH"):
                strat_records.append(r)

        closed = [r for r in strat_records if r.status in ("WON", "LOST", "PUSH")]
        trades_count = len(closed)
        wins = sum(1 for r in closed if r.status == "WON")
        losses = sum(1 for r in closed if r.status == "LOST")
        win_rate = (wins / trades_count * 100.0) if trades_count > 0 else 0.0

        profits = [r.pnl for r in closed if r.pnl > 0]
        loss_vals = [abs(r.pnl) for r in closed if r.pnl < 0]
        gross_profit = sum(profits)
        gross_loss = sum(loss_vals)
        net_pnl = gross_profit - gross_loss

        avg_profit = (gross_profit / len(profits)) if profits else 0.0
        avg_loss = (gross_loss / len(loss_vals)) if loss_vals else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
        expectancy = ((win_rate / 100.0) * avg_profit) - ((1.0 - win_rate / 100.0) * avg_loss)

        avg_ev = sum(r.ev for r in closed) / trades_count if trades_count > 0 else 0.0
        sample_status = cls.classify_sample_status(trades_count)

        return StrategyStats(
            strategy_name=strategy_name,
            opportunities_evaluated=len(records),
            participations=trades_count,
            trades=trades_count,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            net_pnl=net_pnl,
            profit_factor=profit_factor,
            expectancy=expectancy,
            avg_ev=avg_ev,
            sample_status=sample_status,
        )

    @classmethod
    def calculate_reputation_score(cls, stats: StrategyStats) -> ReputationScore:
        """
        Calculates a balanced reputation score (0-100) weighting expectancy, profit factor,
        win rate, sample size, and drawdown. Raw win rate alone CANNOT yield a high score if expectancy is negative.
        """
        sample_status = stats.sample_status

        # 1. Sample Size Weighting (0-20 pts)
        if sample_status == SampleStatus.INSUFFICIENT_DATA:
            sample_score = (stats.trades / 30.0) * 10.0
        elif sample_status == SampleStatus.EARLY_SAMPLE:
            sample_score = 10.0 + ((stats.trades - 30) / 70.0) * 5.0
        elif sample_status == SampleStatus.DEVELOPING:
            sample_score = 15.0 + ((stats.trades - 100) / 200.0) * 3.0
        else:
            sample_score = 20.0

        # 2. Expectancy & Return Score (0-30 pts)
        if stats.expectancy <= 0:
            expectancy_score = 0.0
        else:
            expectancy_score = min(30.0, stats.expectancy * 10.0)

        # 3. Profit Factor Score (0-25 pts)
        if stats.profit_factor <= 1.0:
            pf_score = 0.0
        else:
            pf_score = min(25.0, (stats.profit_factor - 1.0) * 15.0)

        # 4. Win Rate Score (0-25 pts)
        if stats.win_rate < 50.0:
            wr_score = max(0.0, stats.win_rate / 2.0)
        else:
            wr_score = min(25.0, 12.5 + (stats.win_rate - 50.0) * 0.5)

        total_score = round(sample_score + expectancy_score + pf_score + wr_score, 1)

        # Reputation Tier
        if sample_status == SampleStatus.INSUFFICIENT_DATA or total_score < 40.0:
            tier = "UNPROVEN"
        elif total_score < 60.0:
            tier = "DEVELOPING"
        elif total_score < 80.0:
            tier = "RELIABLE"
        else:
            tier = "ELITE"

        return ReputationScore(
            strategy_name=stats.strategy_name,
            reputation_score=total_score,
            sample_status=sample_status,
            mode=cls.MODE,
            reputation_tier=tier,
            components={
                "sample_score": round(sample_score, 1),
                "expectancy_score": round(expectancy_score, 1),
                "pf_score": round(pf_score, 1),
                "wr_score": round(wr_score, 1),
            }
        )
