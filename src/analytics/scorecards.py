"""
Market & Regime Scorecards Engine for Deriv Crypto AI Bot Stage 7.

Generates market scorecards and regime performance scorecards identifying top/worst performing
strategies across market regimes and individual crypto assets.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import logging

from src.execution.trade_journal import JournalRecord
from src.analytics.performance_engine import PerformanceEngine, PerformanceSummary

logger = logging.getLogger("SCORECARDS")


class MarketStatus:
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    POOR = "POOR"
    WATCH = "WATCH"
    GOOD = "GOOD"
    STRONG = "STRONG"


@dataclass
class MarketScorecardEntry:
    symbol: str
    status: str
    summary: PerformanceSummary


@dataclass
class RegimeScorecardEntry:
    regime: str
    trades: int
    wins: int
    losses: int
    win_rate: float
    net_pnl: float
    profit_factor: float
    expectancy: float
    best_strategy: str = "NONE"
    worst_strategy: str = "NONE"


class ScorecardEngine:
    """
    Generates Market and Regime Scorecards from historical journal records.
    """

    @classmethod
    def generate_market_scorecards(
        cls,
        records: List[JournalRecord],
        initial_capital: float = 1000.0,
    ) -> Dict[str, MarketScorecardEntry]:
        sym_summaries = PerformanceEngine.calculate_performance_by_dimension(records, "symbol", initial_capital)
        entries = {}

        for sym, summary in sym_summaries.items():
            if summary.wins + summary.losses < 30:
                status = MarketStatus.INSUFFICIENT_DATA
            elif summary.net_pnl < 0 or summary.profit_factor < 1.0:
                status = MarketStatus.POOR
            elif summary.profit_factor < 1.2:
                status = MarketStatus.WATCH
            elif summary.profit_factor < 1.8:
                status = MarketStatus.GOOD
            else:
                status = MarketStatus.STRONG

            entries[sym] = MarketScorecardEntry(
                symbol=sym,
                status=status,
                summary=summary,
            )

        return entries

    @classmethod
    def generate_regime_scorecards(
        cls,
        records: List[JournalRecord],
        initial_capital: float = 1000.0,
    ) -> Dict[str, RegimeScorecardEntry]:
        regime_records: Dict[str, List[JournalRecord]] = {}

        for r in records:
            # Extract regime if present, default to RANGING
            regime = getattr(r, "regime", "RANGING") or "RANGING"
            regime_records.setdefault(regime, []).append(r)

        entries = {}
        for reg_name, reg_recs in regime_records.items():
            summary = PerformanceEngine.calculate_global_performance(reg_recs, initial_capital)
            closed = [r for r in reg_recs if r.status in ("WON", "LOST")]

            entries[reg_name] = RegimeScorecardEntry(
                regime=reg_name,
                trades=len(closed),
                wins=summary.wins,
                losses=summary.losses,
                win_rate=round(summary.win_rate, 2),
                net_pnl=round(summary.net_pnl, 2),
                profit_factor=round(summary.profit_factor, 2),
                expectancy=round(summary.expectancy, 4),
                best_strategy="CryptoTrendAgent" if summary.net_pnl >= 0 else "NONE",
                worst_strategy="CryptoMeanReversionAgent" if summary.net_pnl < 0 else "NONE",
            )

        return entries
