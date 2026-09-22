import pytest
import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock

from src.execution.paper_trade_engine import CryptoPaperTradeEngine
from src.execution.proposal_engine import DerivProposalEngine, ProposalResult, ContractEconomics
from src.analytics.probability_calibrator import ProbabilityCalibrator, ForwardObservationRecord
from src.execution.expected_value_engine import ExpectedValueEngine
from src.risk.crypto_risk_manager import CryptoRiskManager
from src.execution.trade_journal import CryptoTradeJournal


@pytest.fixture
def mock_proposal_engine():
    engine = MagicMock(spec=DerivProposalEngine)
    engine.request_proposal = AsyncMock()
    return engine


@pytest.fixture
def calibrator():
    cal = ProbabilityCalibrator()
    # Add 40 historical observations for 50-60 score band with 65% win rate
    for i in range(40):
        cal.add_observation(
            ForwardObservationRecord(opportunity_score=55.0, direction="BULLISH", win=(i < 26))
        )
    return cal


@pytest.fixture
def temp_journal(tmp_path):
    db_file = str(tmp_path / "test_journal.db")
    return CryptoTradeJournal(db_path=db_file)


@pytest.mark.asyncio
async def test_paper_trade_engine_rejection_when_not_live_ready(mock_proposal_engine, calibrator, temp_journal):
    ev_engine = ExpectedValueEngine()
    risk_manager = CryptoRiskManager(initial_balance=1000.0)
    engine = CryptoPaperTradeEngine(
        proposal_engine=mock_proposal_engine,
        calibrator=calibrator,
        ev_engine=ev_engine,
        risk_manager=risk_manager,
        trade_journal=temp_journal,
    )

    mock_opp = MagicMock()
    mock_opp.symbol = "cryBTCUSD"
    mock_opp.opportunity_score = 55.0
    mock_opp.consensus.direction = "BULLISH"
    mock_opp.regime = "UPTREND"
    mock_opp.timeframe = "1m"

    res = await engine.evaluate_and_execute(opportunity=mock_opp, live_ready=False)
    assert res is None
    summary = temp_journal.get_summary()
    assert summary["status_counts"].get("REJECTED", 0) == 1


@pytest.mark.asyncio
async def test_paper_trade_engine_successful_execution(mock_proposal_engine, calibrator, temp_journal):
    ev_engine = ExpectedValueEngine(ev_safety_margin=0.01, min_probability_edge=0.01)
    risk_manager = CryptoRiskManager(initial_balance=1000.0)
    engine = CryptoPaperTradeEngine(
        proposal_engine=mock_proposal_engine,
        calibrator=calibrator,
        ev_engine=ev_engine,
        risk_manager=risk_manager,
        trade_journal=temp_journal,
    )

    # Mock proposal pricing quote response (Ask $15, Payout $30 -> Breakeven 50%, Net profit $15)
    mock_proposal_engine.request_proposal.return_value = ProposalResult(
        proposal_id="prop_test_123",
        symbol="cryBTCUSD",
        contract_type="CALL",
        duration=1,
        duration_unit="m",
        currency="USD",
        economics=ContractEconomics(
            ask_price=15.0,
            payout=30.0,
            net_profit=15.0,
            max_loss=15.0,
            net_return_pct=100.0,
            breakeven_probability=0.50,
            spot_price=50000.0,
        ),
        is_valid=True,
    )

    mock_opp = MagicMock()
    mock_opp.symbol = "cryBTCUSD"
    mock_opp.opportunity_score = 55.0
    mock_opp.consensus.direction = "BULLISH"
    mock_opp.regime = "UPTREND"
    mock_opp.timeframe = "1m"

    res = await engine.evaluate_and_execute(
        opportunity=mock_opp,
        live_ready=True,
        available_contracts=["CALL", "PUT"]
    )

    assert res is not None
    assert res.status == "OPEN"
    assert res.symbol == "cryBTCUSD"
    assert res.contract_type == "CALL"
    assert res.stake == 15.0
    assert "cryBTCUSD" in risk_manager.open_positions


@pytest.mark.asyncio
async def test_paper_trade_settlement(mock_proposal_engine, calibrator, temp_journal):
    ev_engine = ExpectedValueEngine(ev_safety_margin=0.01, min_probability_edge=0.01)
    risk_manager = CryptoRiskManager(initial_balance=1000.0)
    engine = CryptoPaperTradeEngine(
        proposal_engine=mock_proposal_engine,
        calibrator=calibrator,
        ev_engine=ev_engine,
        risk_manager=risk_manager,
        trade_journal=temp_journal,
    )

    mock_proposal_engine.request_proposal.return_value = ProposalResult(
        proposal_id="prop_test_123",
        symbol="cryBTCUSD",
        contract_type="CALL",
        duration=1,
        duration_unit="m",
        currency="USD",
        economics=ContractEconomics(
            ask_price=15.0,
            payout=30.0,
            net_profit=15.0,
            max_loss=15.0,
            net_return_pct=100.0,
            breakeven_probability=0.50,
            spot_price=50000.0,
        ),
        is_valid=True,
    )

    mock_opp = MagicMock()
    mock_opp.symbol = "cryBTCUSD"
    mock_opp.opportunity_score = 55.0
    mock_opp.consensus.direction = "BULLISH"

    trade_rec = await engine.evaluate_and_execute(opportunity=mock_opp, live_ready=True)
    assert trade_rec is not None

    # Calculate exact duration seconds for the trade
    duration_sec = engine._parse_duration_seconds(trade_rec.duration, trade_rec.duration_unit)
    future_time = trade_rec.timestamp + duration_sec + 5.0

    settled = engine.check_and_settle_trades(
        current_spots={"cryBTCUSD": 50500.0},
        current_time=future_time,
    )

    assert len(settled) == 1
    assert settled[0].status == "WON"
    assert settled[0].pnl == 15.0
    assert risk_manager.balance == 1015.0
    assert "cryBTCUSD" not in risk_manager.open_positions
