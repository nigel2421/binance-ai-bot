import pytest
import pandas as pd
from src.risk.crypto_risk_manager import (
    CryptoRiskManager,
    FixedFractionalPositionSizer,
    RiskDecision,
)


def test_fixed_fractional_position_sizer():
    # 1.5% of 1000 = 15.0
    stake = FixedFractionalPositionSizer.calculate_stake(1000.0, risk_pct=0.015)
    assert stake == 15.0

    # Max stake cap
    stake_capped = FixedFractionalPositionSizer.calculate_stake(10000.0, risk_pct=0.015, max_stake=100.0)
    assert stake_capped == 100.0


def test_risk_manager_trade_approval_and_veto():
    manager = CryptoRiskManager(initial_balance=1000.0, max_open_positions=2)

    # First trade on cryBTCUSD should be approved
    dec1 = manager.evaluate_trade_risk("cryBTCUSD")
    assert dec1.approved is True
    assert dec1.position_size == 15.0

    # Add open positions
    manager.open_positions["cryBTCUSD"] = {"stake": 15.0}
    dec2 = manager.evaluate_trade_risk("cryETHUSD")
    assert dec2.approved is True

    manager.open_positions["cryETHUSD"] = {"stake": 15.0}

    # Third trade should be vetoed due to max_open_positions=2
    dec3 = manager.evaluate_trade_risk("crySOLUSD")
    assert dec3.approved is False
    assert "Max open positions reached" in dec3.rejection_reason


def test_risk_manager_daily_loss_halt():
    manager = CryptoRiskManager(initial_balance=1000.0, max_daily_loss_pct=0.05)  # 5% = $50
    manager.record_pnl(-55.0)

    dec = manager.evaluate_trade_risk("cryBTCUSD")
    assert dec.approved is False
    assert dec.risk_halt is True
    assert "PAPER_RISK_HALT active" in dec.rejection_reason


def test_risk_manager_correlation_cap():
    manager = CryptoRiskManager(initial_balance=1000.0, max_correlated_positions=1, correlation_threshold=0.70)
    manager.open_positions["cryBTCUSD"] = {"stake": 15.0}

    # Create dummy correlation matrix: BTC & ETH correlated 0.85
    corr_df = pd.DataFrame(
        [[1.0, 0.85], [0.85, 1.0]],
        index=["cryBTCUSD", "cryETHUSD"],
        columns=["cryBTCUSD", "cryETHUSD"]
    )

    dec = manager.evaluate_trade_risk("cryETHUSD", correlation_matrix=corr_df)
    assert dec.approved is False
    assert "Correlation exposure limit" in dec.rejection_reason
