"""
Performance Analytics Engine for Deriv Crypto AI Bot Stage 7.

Computes comprehensive global and multi-dimensional trading performance metrics from trade journal records:
win rate, gross profit/loss, net PnL, profit factor, expectancy per trade, max drawdown, streak metrics,
and multi-factor metrics (avg predicted probability, actual win rate, avg EV, avg score).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import math
import logging

from src.execution.trade_journal import JournalRecord

logger = logging.getLogger("PERFORMANCE_ENGINE")


@dataclass
class PerformanceSummary:
    total_records: int = 0
    total_opportunities: int = 0
    total_qualified: int = 0
    paper_trades: int = 0
    wins: int = 0
    losses: int = 0
    pushes: int = 0
    win_rate: float = 0.0                      # 0.0 to 100.0 %
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_pnl: float = 0.0
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    avg_pnl_per_trade: float = 0.0
    profit_factor: float = 0.0                 # gross_profit / gross_loss (inf -> float)
    expectancy: float = 0.0                    # (win_rate * avg_profit) - ((1 - win_rate) * avg_loss)
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    avg_stake: float = 0.0
    return_on_capital: float = 0.0             # (net_pnl / initial_capital) * 100
    avg_predicted_probability: float = 0.0
    actual_observed_win_rate: float = 0.0
    avg_opportunity_score: float = 0.0
    avg_ev_at_entry: float = 0.0


class PerformanceEngine:
    """
    Computes performance statistics across all trades or filtered by dimensions.
    """

    @staticmethod
    def calculate_global_performance(
        records: List[JournalRecord],
        initial_capital: float = 1000.0,
    ) -> PerformanceSummary:
        if not records:
            return PerformanceSummary()

        total_records = len(records)
        paper_trades_records = [r for r in records if r.record_type == "PAPER_TRADE"]
        rejection_records = [r for r in records if r.record_type == "REJECTION"]

        total_opportunities = total_records
        total_qualified = len(paper_trades_records)
        paper_trades_count = len(paper_trades_records)

        # Closed paper trades
        closed_trades = [r for r in paper_trades_records if r.status in ("WON", "LOST", "PUSH")]
        if not closed_trades:
            # All trades open or rejected
            avg_score = sum(r.opportunity_score for r in records) / total_records if total_records > 0 else 0.0
            avg_prob = sum(r.calibrated_probability for r in records) / total_records if total_records > 0 else 0.0
            avg_ev = sum(r.ev for r in records) / total_records if total_records > 0 else 0.0
            return PerformanceSummary(
                total_records=total_records,
                total_opportunities=total_opportunities,
                total_qualified=total_qualified,
                paper_trades=paper_trades_count,
                avg_opportunity_score=avg_score,
                avg_predicted_probability=avg_prob,
                avg_ev_at_entry=avg_ev,
            )

        wins = sum(1 for r in closed_trades if r.status == "WON")
        losses = sum(1 for r in closed_trades if r.status == "LOST")
        pushes = sum(1 for r in closed_trades if r.status == "PUSH")
        closed_count = len(closed_trades)

        win_rate = (wins / closed_count * 100.0) if closed_count > 0 else 0.0

        profits = [r.pnl for r in closed_trades if r.pnl > 0]
        loss_vals = [abs(r.pnl) for r in closed_trades if r.pnl < 0]

        gross_profit = sum(profits)
        gross_loss = sum(loss_vals)
        net_pnl = gross_profit - gross_loss

        avg_profit = (gross_profit / len(profits)) if profits else 0.0
        avg_loss = (gross_loss / len(loss_vals)) if loss_vals else 0.0
        avg_pnl_per_trade = net_pnl / closed_count if closed_count > 0 else 0.0

        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
        expectancy = ((win_rate / 100.0) * avg_profit) - ((1.0 - win_rate / 100.0) * avg_loss)

        # Streaks & Peak Drawdown
        current_win_streak = 0
        max_consecutive_wins = 0
        current_loss_streak = 0
        max_consecutive_losses = 0

        running_balance = initial_capital
        peak_balance = initial_capital
        max_drawdown = 0.0
        max_drawdown_pct = 0.0

        for r in closed_trades:
            if r.status == "WON":
                current_win_streak += 1
                current_loss_streak = 0
                if current_win_streak > max_consecutive_wins:
                    max_consecutive_wins = current_win_streak
            elif r.status == "LOST":
                current_loss_streak += 1
                current_win_streak = 0
                if current_loss_streak > max_consecutive_losses:
                    max_consecutive_losses = current_loss_streak

            running_balance += r.pnl
            if running_balance > peak_balance:
                peak_balance = running_balance
            dd = peak_balance - running_balance
            dd_pct = (dd / peak_balance * 100.0) if peak_balance > 0 else 0.0

            if dd > max_drawdown:
                max_drawdown = dd
            if dd_pct > max_drawdown_pct:
                max_drawdown_pct = dd_pct

        avg_stake = sum(r.stake for r in paper_trades_records) / paper_trades_count if paper_trades_count > 0 else 0.0
        return_on_capital = (net_pnl / initial_capital * 100.0) if initial_capital > 0 else 0.0

        avg_prob = sum(r.calibrated_probability for r in closed_trades) / closed_count if closed_count > 0 else 0.0
        avg_score = sum(r.opportunity_score for r in closed_trades) / closed_count if closed_count > 0 else 0.0
        avg_ev = sum(r.ev for r in closed_trades) / closed_count if closed_count > 0 else 0.0

        return PerformanceSummary(
            total_records=total_records,
            total_opportunities=total_opportunities,
            total_qualified=total_qualified,
            paper_trades=paper_trades_count,
            wins=wins,
            losses=losses,
            pushes=pushes,
            win_rate=win_rate,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            net_pnl=net_pnl,
            avg_profit=avg_profit,
            avg_loss=avg_loss,
            avg_pnl_per_trade=avg_pnl_per_trade,
            profit_factor=profit_factor,
            expectancy=expectancy,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            max_consecutive_wins=max_consecutive_wins,
            max_consecutive_losses=max_consecutive_losses,
            avg_stake=avg_stake,
            return_on_capital=return_on_capital,
            avg_predicted_probability=avg_prob,
            actual_observed_win_rate=win_rate / 100.0,
            avg_opportunity_score=avg_score,
            avg_ev_at_entry=avg_ev,
        )

    @classmethod
    def calculate_performance_by_dimension(
        cls,
        records: List[JournalRecord],
        dimension: str,
        initial_capital: float = 1000.0,
    ) -> Dict[str, PerformanceSummary]:
        """
        Group records by key dimension (e.g. 'symbol', 'regime', 'contract_type', 'direction', 'score_band', 'ev_band', 'prob_band')
        and compute PerformanceSummary per key.
        """
        grouped: Dict[str, List[JournalRecord]] = {}

        for r in records:
            key = cls._extract_dimension_key(r, dimension)
            grouped.setdefault(key, []).append(r)

        summaries: Dict[str, PerformanceSummary] = {}
        for key, rec_group in grouped.items():
            summaries[key] = cls.calculate_global_performance(rec_group, initial_capital)

        return summaries

    @staticmethod
    def _extract_dimension_key(r: JournalRecord, dimension: str) -> str:
        d_lower = dimension.lower()
        if d_lower == "symbol":
            return r.symbol
        elif d_lower == "contract_type":
            return r.contract_type
        elif d_lower == "direction":
            return r.direction
        elif d_lower == "score_band":
            score = r.opportunity_score
            if score < 50: return "50-59" if score >= 50 else "<50"
            elif score < 60: return "50-59"
            elif score < 70: return "60-69"
            elif score < 80: return "70-79"
            elif score < 90: return "80-89"
            else: return "90-100"
        elif d_lower == "ev_band":
            ev = r.ev
            if ev <= 0: return "<0%"
            elif ev < 0.20: return "0-2%"
            elif ev < 0.50: return "2-5%"
            elif ev < 1.00: return "5-10%"
            else: return "10%+"
        elif d_lower == "prob_band":
            p = r.calibrated_probability
            if p < 0.55: return "0.50-0.54"
            elif p < 0.60: return "0.55-0.59"
            elif p < 0.65: return "0.60-0.64"
            elif p < 0.70: return "0.65-0.69"
            else: return "0.70+"
        return getattr(r, dimension, "UNKNOWN")
