import pytest
from src.execution.trade_journal import JournalRecord
from src.analytics.strategy_reputation import (
    StrategyReputationEngine,
    StrategyStats,
    ReputationScore,
    SampleStatus,
)


def test_sample_status_classification():
    assert StrategyReputationEngine.classify_sample_status(10) == SampleStatus.INSUFFICIENT_DATA
    assert StrategyReputationEngine.classify_sample_status(45) == SampleStatus.EARLY_SAMPLE
    assert StrategyReputationEngine.classify_sample_status(150) == SampleStatus.DEVELOPING
    assert StrategyReputationEngine.classify_sample_status(350) == SampleStatus.STATISTICALLY_USEFUL


def test_reputation_score_penalizes_negative_expectancy():
    # Strategy with 80% win rate but negative expectancy (small wins, massive loss)
    stats_bad = StrategyStats(
        strategy_name="HighWinRateLossMaker",
        trades=50,
        wins=40,
        losses=10,
        win_rate=80.0,
        net_pnl=-50.0,
        profit_factor=0.5,
        expectancy=-1.0,
        sample_status=SampleStatus.EARLY_SAMPLE,
    )

    rep = StrategyReputationEngine.calculate_reputation_score(stats_bad)
    # Expectancy score and profit factor score should be 0.0
    assert rep.components["expectancy_score"] == 0.0
    assert rep.components["pf_score"] == 0.0
    assert rep.reputation_tier in ("UNPROVEN", "DEVELOPING")


def test_reputation_score_reward_positive_expectancy():
    stats_good = StrategyStats(
        strategy_name="CryptoTrendAgent",
        trades=120,
        wins=72,
        losses=48,
        win_rate=60.0,
        net_pnl=240.0,
        profit_factor=1.8,
        expectancy=2.0,
        sample_status=SampleStatus.DEVELOPING,
    )

    rep = StrategyReputationEngine.calculate_reputation_score(stats_good)
    assert rep.reputation_score > 50.0
    assert rep.components["expectancy_score"] > 0.0
    assert rep.reputation_tier in ("RELIABLE", "ELITE")
