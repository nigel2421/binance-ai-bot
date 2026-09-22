import pytest
from src.execution.trade_journal import JournalRecord
from src.analytics.scorecards import ScorecardEngine, MarketStatus
from src.analytics.trade_attribution import TradeAttributionEngine, LossCause


def test_market_and_regime_scorecards():
    records = [
        JournalRecord(
            record_id="t1", record_type="PAPER_TRADE", timestamp=100.0, symbol="cryBTCUSD",
            direction="BULLISH", contract_type="CALL", duration=1, duration_unit="m",
            stake=10.0, ask_price=10.0, payout=20.0, spot_entry=50000.0, spot_exit=50500.0,
            opportunity_score=65.0, calibrated_probability=0.60, ev=2.0, status="WON", pnl=10.0
        ),
    ]

    mkt_cards = ScorecardEngine.generate_market_scorecards(records)
    assert "cryBTCUSD" in mkt_cards
    # Since <30 trades, status is INSUFFICIENT_DATA
    assert mkt_cards["cryBTCUSD"].status == MarketStatus.INSUFFICIENT_DATA

    reg_cards = ScorecardEngine.generate_regime_scorecards(records)
    assert "RANGING" in reg_cards
    assert reg_cards["RANGING"].trades == 1


def test_loss_attribution_and_drawdown_episodes():
    records = [
        JournalRecord(
            record_id="t1", record_type="PAPER_TRADE", timestamp=100.0, symbol="cryBTCUSD",
            direction="BULLISH", contract_type="CALL", duration=1, duration_unit="m",
            stake=10.0, ask_price=10.0, payout=20.0, spot_entry=50000.0, spot_exit=49500.0,
            opportunity_score=85.0, calibrated_probability=0.70, ev=4.0, status="LOST", pnl=-10.0
        ),
        JournalRecord(
            record_id="t2", record_type="PAPER_TRADE", timestamp=110.0, symbol="cryBTCUSD",
            direction="BULLISH", contract_type="CALL", duration=1, duration_unit="m",
            stake=10.0, ask_price=10.0, payout=20.0, spot_entry=49500.0, spot_exit=50000.0,
            opportunity_score=65.0, calibrated_probability=0.60, ev=2.0, status="WON", pnl=10.0
        ),
    ]

    losses = TradeAttributionEngine.analyze_losses(records)
    assert len(losses) == 1
    assert losses[0].cause_classification == LossCause.MODEL_OVERCONFIDENCE

    episodes = TradeAttributionEngine.analyze_drawdown_episodes(records, initial_capital=1000.0)
    assert len(episodes) == 1
    assert episodes[0].is_recovered is True
    assert episodes[0].loss_amount == 10.0
