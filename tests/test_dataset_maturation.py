"""
Unit tests for Dataset Maturation Engine (DatasetMaturationEngine).
"""

import os
import pytest
from src.execution.trade_journal import CryptoTradeJournal
from src.analytics.dataset_maturation import DatasetMaturationEngine
from src.analytics.strategy_reputation import StrategyReputationEngine


def test_dataset_maturation_seeding(tmp_path):
    db_file = str(tmp_path / "test_maturation_journal.db")
    seeded_count = DatasetMaturationEngine.seed_synthetic_journal(db_path=db_file, count=300)
    assert seeded_count == 300

    journal = CryptoTradeJournal(db_path=db_file)
    summary = journal.get_summary()
    assert summary["total_records"] == 300
    assert summary["status_counts"]["WON"] + summary["status_counts"]["LOST"] == 300


def test_dataset_maturation_strategy_reputation_transition(tmp_path):
    db_file = str(tmp_path / "test_maturation_reputation.db")
    DatasetMaturationEngine.seed_synthetic_journal(db_path=db_file, count=300)

    import sqlite3
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM journal_records")
        rows = cursor.fetchall()
        from src.execution.trade_journal import JournalRecord
        all_recs = [
            JournalRecord(
                record_id=r[0], record_type=r[1], timestamp=r[2], symbol=r[3],
                direction=r[4], contract_type=r[5], duration=r[6], duration_unit=r[7],
                stake=r[8], ask_price=r[9], payout=r[10], spot_entry=r[11],
                spot_exit=r[12], opportunity_score=r[13], calibrated_probability=r[14],
                ev=r[15], status=r[16], rejection_stage=r[17], rejection_reason=r[18],
                pnl=r[19], settled_at=r[20]
            ) for r in rows
        ]

    # Verify at least one strategy has enough trades to leave INSUFFICIENT_DATA
    for strat in DatasetMaturationEngine.STRATEGIES:
        stats = StrategyReputationEngine.calculate_strategy_stats(strat, all_recs)
        assert stats.trades > 0
        assert stats.sample_status in ("EARLY_SAMPLE", "DEVELOPING", "STATISTICALLY_USEFUL")
