"""
Crypto Risk Manager & Conservative Position Sizing for Deriv Crypto AI Bot Stage 6.

Enforces conservative fixed-fractional position sizing (1-2% paper balance risk per position),
correlation exposure caps, maximum concurrent position limits, daily loss limits, and drawdown halts.
VETO authority over trade proposals.
Strictly NO Kelly sizing, NO Martingale, NO doubling after losses.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import logging
import pandas as pd

logger = logging.getLogger("CRYPTO_RISK_MANAGER")


@dataclass
class RiskDecision:
    approved: bool
    position_size: float                       # Stake in USD
    risk_halt: bool = False
    rejection_reason: Optional[str] = None


class FixedFractionalPositionSizer:
    """
    Calculates conservative position stake as a fixed fraction of paper balance.
    """

    @staticmethod
    def calculate_stake(
        balance: float,
        risk_pct: float = 0.015,
        min_stake: float = 1.0,
        max_stake: float = 100.0,
    ) -> float:
        if balance <= 0:
            return 0.0
        stake = balance * risk_pct
        if stake < min_stake:
            stake = min_stake
        if stake > max_stake:
            stake = max_stake
        return round(stake, 2)


class CryptoRiskManager:
    """
    Risk manager with VETO authority enforcing paper trading exposure limits.
    """

    def __init__(
        self,
        initial_balance: float = 1000.0,
        max_risk_per_trade_pct: float = 0.015,   # 1.5% default risk
        max_open_positions: int = 3,
        max_correlated_positions: int = 2,
        correlation_threshold: float = 0.70,
        max_daily_loss_pct: float = 0.05,        # 5% daily loss halt
        max_drawdown_pct: float = 0.10,          # 10% peak-to-trough drawdown halt
        min_stake: float = 1.0,
        max_stake: float = 100.0,
    ):
        self.balance = initial_balance
        self.peak_balance = initial_balance
        self.daily_starting_balance = initial_balance
        self.realized_pnl_today = 0.0

        self.max_risk_per_trade_pct = max_risk_per_trade_pct
        self.max_open_positions = max_open_positions
        self.max_correlated_positions = max_correlated_positions
        self.correlation_threshold = correlation_threshold
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.min_stake = min_stake
        self.max_stake = max_stake

        self.open_positions: Dict[str, Dict[str, Any]] = {}
        self.risk_halt: bool = False
        self.halt_reason: Optional[str] = None

    def update_balance(self, new_balance: float) -> None:
        self.balance = new_balance
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
        self._check_halt_conditions()

    def record_pnl(self, pnl: float) -> None:
        self.balance += pnl
        self.realized_pnl_today += pnl
        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
        self._check_halt_conditions()

    def reset_daily_metrics(self) -> None:
        self.daily_starting_balance = self.balance
        self.realized_pnl_today = 0.0
        if not self.risk_halt or self.halt_reason == "DAILY_LOSS_LIMIT":
            self.risk_halt = False
            self.halt_reason = None

    def _check_halt_conditions(self) -> None:
        # Check daily loss limit
        if self.realized_pnl_today <= - (self.daily_starting_balance * self.max_daily_loss_pct):
            self.risk_halt = True
            self.halt_reason = f"DAILY_LOSS_LIMIT: Realized daily loss ${abs(self.realized_pnl_today):.2f} exceeded {self.max_daily_loss_pct*100}% limit"
            logger.warning(f"[RISK_MANAGER] {self.halt_reason}")

        # Check max drawdown limit
        drawdown_pct = (self.peak_balance - self.balance) / self.peak_balance if self.peak_balance > 0 else 0.0
        if drawdown_pct >= self.max_drawdown_pct:
            self.risk_halt = True
            self.halt_reason = f"MAX_DRAWDOWN_LIMIT: Drawdown {drawdown_pct*100:.2f}% exceeded {self.max_drawdown_pct*100}% limit"
            logger.warning(f"[RISK_MANAGER] {self.halt_reason}")

    def evaluate_trade_risk(
        self,
        symbol: str,
        correlation_matrix: Optional[pd.DataFrame] = None,
    ) -> RiskDecision:
        """
        Evaluates whether a trade proposal should be approved or vetoed.
        """
        self._check_halt_conditions()

        if self.risk_halt:
            return RiskDecision(
                approved=False,
                position_size=0.0,
                risk_halt=True,
                rejection_reason=f"PAPER_RISK_HALT active: {self.halt_reason}",
            )

        # 1. Check max open positions
        if len(self.open_positions) >= self.max_open_positions:
            return RiskDecision(
                approved=False,
                position_size=0.0,
                rejection_reason=f"Max open positions reached ({len(self.open_positions)}/{self.max_open_positions})",
            )

        # 2. Check position already open on symbol
        if symbol in self.open_positions:
            return RiskDecision(
                approved=False,
                position_size=0.0,
                rejection_reason=f"Position already active on {symbol}",
            )

        # 3. Check correlation exposure
        if correlation_matrix is not None and not correlation_matrix.empty and symbol in correlation_matrix.columns:
            correlated_count = 0
            for open_sym in self.open_positions:
                if open_sym in correlation_matrix.columns:
                    corr_val = float(correlation_matrix.loc[symbol, open_sym])
                    if abs(corr_val) >= self.correlation_threshold:
                        correlated_count += 1
            if correlated_count >= self.max_correlated_positions:
                return RiskDecision(
                    approved=False,
                    position_size=0.0,
                    rejection_reason=f"Correlation exposure limit reached for {symbol} ({correlated_count} correlated open positions >= threshold {self.correlation_threshold})",
                )

        # 4. Calculate fixed fractional position stake
        stake = FixedFractionalPositionSizer.calculate_stake(
            balance=self.balance,
            risk_pct=self.max_risk_per_trade_pct,
            min_stake=self.min_stake,
            max_stake=self.max_stake,
        )

        if stake <= 0.0 or stake > self.balance:
            return RiskDecision(
                approved=False,
                position_size=0.0,
                rejection_reason=f"Invalid calculated stake (${stake:.2f} for balance ${self.balance:.2f})",
            )

        return RiskDecision(
            approved=True,
            position_size=stake,
            risk_halt=False,
        )
