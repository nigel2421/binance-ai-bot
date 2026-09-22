"""
Crypto Trade Journal for Deriv Crypto AI Bot Stage 6.

Provides persistent recording of open paper trades, closed settlements, and full rejection audit logs
using SQLite (config/trade_journal.db) or JSON fallback.
"""

from dataclasses import dataclass, asdict
import sqlite3
import json
import os
import time
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger("TRADE_JOURNAL")


@dataclass
class JournalRecord:
    record_id: str
    record_type: str                            # "PAPER_TRADE" or "REJECTION"
    timestamp: float
    symbol: str
    direction: str                              # "BULLISH", "BEARISH", or "NEUTRAL"
    contract_type: str                          # "CALL", "PUT", "MULTUP", etc.
    duration: int
    duration_unit: str
    stake: float
    ask_price: float
    payout: float
    spot_entry: float
    spot_exit: Optional[float] = None
    opportunity_score: float = 0.0
    calibrated_probability: float = 0.0
    ev: float = 0.0
    status: str = "OPEN"                        # "OPEN", "WON", "LOST", "EXPIRED", "REJECTED"
    rejection_stage: Optional[str] = None       # Stage at which trade was rejected
    rejection_reason: Optional[str] = None
    pnl: float = 0.0
    settled_at: Optional[float] = None


class CryptoTradeJournal:
    """
    SQLite-backed journal recording paper trades and rejection reasons.
    """

    def __init__(self, db_path: str = "config/trade_journal.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS journal_records (
                        record_id TEXT PRIMARY KEY,
                        record_type TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        symbol TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        contract_type TEXT NOT NULL,
                        duration INTEGER NOT NULL,
                        duration_unit TEXT NOT NULL,
                        stake REAL NOT NULL,
                        ask_price REAL NOT NULL,
                        payout REAL NOT NULL,
                        spot_entry REAL NOT NULL,
                        spot_exit REAL,
                        opportunity_score REAL NOT NULL,
                        calibrated_probability REAL NOT NULL,
                        ev REAL NOT NULL,
                        status TEXT NOT NULL,
                        rejection_stage TEXT,
                        rejection_reason TEXT,
                        pnl REAL NOT NULL,
                        settled_at REAL
                    )
                """)
                conn.commit()
        except Exception as err:
            logger.error(f"[TRADE_JOURNAL] Database init error: {err}")

    def log_record(self, record: JournalRecord) -> None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO journal_records (
                        record_id, record_type, timestamp, symbol, direction,
                        contract_type, duration, duration_unit, stake, ask_price,
                        payout, spot_entry, spot_exit, opportunity_score,
                        calibrated_probability, ev, status, rejection_stage,
                        rejection_reason, pnl, settled_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.record_id, record.record_type, record.timestamp, record.symbol,
                    record.direction, record.contract_type, record.duration, record.duration_unit,
                    record.stake, record.ask_price, record.payout, record.spot_entry,
                    record.spot_exit, record.opportunity_score, record.calibrated_probability,
                    record.ev, record.status, record.rejection_stage, record.rejection_reason,
                    record.pnl, record.settled_at
                ))
                conn.commit()
        except Exception as err:
            logger.error(f"[TRADE_JOURNAL] Error writing record {record.record_id}: {err}")

    def update_settlement(self, record_id: str, status: str, spot_exit: float, pnl: float) -> None:
        settled_at = time.time()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE journal_records
                    SET status = ?, spot_exit = ?, pnl = ?, settled_at = ?
                    WHERE record_id = ?
                """, (status, spot_exit, pnl, settled_at, record_id))
                conn.commit()
        except Exception as err:
            logger.error(f"[TRADE_JOURNAL] Error updating settlement for {record_id}: {err}")

    def get_open_paper_trades(self) -> List[JournalRecord]:
        records = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM journal_records WHERE record_type = 'PAPER_TRADE' AND status = 'OPEN'")
                rows = cursor.fetchall()
                for r in rows:
                    records.append(JournalRecord(
                        record_id=r[0], record_type=r[1], timestamp=r[2], symbol=r[3],
                        direction=r[4], contract_type=r[5], duration=r[6], duration_unit=r[7],
                        stake=r[8], ask_price=r[9], payout=r[10], spot_entry=r[11],
                        spot_exit=r[12], opportunity_score=r[13], calibrated_probability=r[14],
                        ev=r[15], status=r[16], rejection_stage=r[17], rejection_reason=r[18],
                        pnl=r[19], settled_at=r[20]
                    ))
        except Exception as err:
            logger.error(f"[TRADE_JOURNAL] Error fetching open trades: {err}")
        return records

    def get_summary(self) -> Dict[str, Any]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT status, COUNT(*) FROM journal_records GROUP BY status")
                status_counts = dict(cursor.fetchall())
                cursor.execute("SELECT SUM(pnl) FROM journal_records WHERE record_type = 'PAPER_TRADE'")
                total_pnl = cursor.fetchone()[0] or 0.0
                return {
                    "total_records": sum(status_counts.values()),
                    "status_counts": status_counts,
                    "total_paper_pnl": round(total_pnl, 2),
                }
        except Exception as err:
            logger.error(f"[TRADE_JOURNAL] Error getting summary: {err}")
            return {"total_records": 0, "status_counts": {}, "total_paper_pnl": 0.0}
