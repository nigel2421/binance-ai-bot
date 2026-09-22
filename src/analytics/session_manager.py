"""
Forward Test Session Manager for Deriv Crypto AI Bot Stage 7.

Manages persistent session lifecycle records, attaches configuration fingerprints (config_hash),
and provides multi-session period aggregations (CURRENT SESSION, TODAY, LAST 7 DAYS, LAST 30 DAYS, ALL TIME).
"""

from dataclasses import dataclass, asdict
import sqlite3
import os
import time
import uuid
import logging
from typing import Dict, List, Optional, Any

from src.config import config
from src.execution.trade_journal import JournalRecord

logger = logging.getLogger("SESSION_MANAGER")


@dataclass
class ForwardTestSession:
    session_id: str
    start_time: float
    end_time: Optional[float] = None
    config_version: str = "stage6_paper_v1"
    config_hash: str = ""
    opening_balance: float = 1000.0
    closing_balance: float = 1000.0
    trades_count: int = 0
    wins: int = 0
    losses: int = 0
    net_pnl: float = 0.0
    max_drawdown: float = 0.0
    status: str = "ACTIVE"                       # "ACTIVE", "COMPLETED"


class ForwardTestSessionManager:
    """
    SQLite-backed manager tracking paper forward testing sessions.
    """

    def __init__(self, db_path: str = "config/test_sessions.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS test_sessions (
                        session_id TEXT PRIMARY KEY,
                        start_time REAL NOT NULL,
                        end_time REAL,
                        config_version TEXT NOT NULL,
                        config_hash TEXT NOT NULL,
                        opening_balance REAL NOT NULL,
                        closing_balance REAL NOT NULL,
                        trades_count INTEGER NOT NULL,
                        wins INTEGER NOT NULL,
                        losses INTEGER NOT NULL,
                        net_pnl REAL NOT NULL,
                        max_drawdown REAL NOT NULL,
                        status TEXT NOT NULL
                    )
                """)
                conn.commit()
        except Exception as err:
            logger.error(f"[SESSION_MANAGER] Database init error: {err}")

    def start_session(self, opening_balance: float = 1000.0) -> ForwardTestSession:
        fp = config.get_config_fingerprint()
        session_id = f"sess_{uuid.uuid4().hex[:8]}"

        session = ForwardTestSession(
            session_id=session_id,
            start_time=time.time(),
            config_version=fp["config_version"],
            config_hash=fp["config_hash"],
            opening_balance=opening_balance,
            closing_balance=opening_balance,
            status="ACTIVE"
        )

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO test_sessions (
                        session_id, start_time, end_time, config_version, config_hash,
                        opening_balance, closing_balance, trades_count, wins, losses,
                        net_pnl, max_drawdown, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session.session_id, session.start_time, session.end_time,
                    session.config_version, session.config_hash, session.opening_balance,
                    session.closing_balance, session.trades_count, session.wins,
                    session.losses, session.net_pnl, session.max_drawdown, session.status
                ))
                conn.commit()
        except Exception as err:
            logger.error(f"[SESSION_MANAGER] Error starting session {session_id}: {err}")

        logger.info(f"[SESSION_MANAGER] Started Forward Test Session {session_id} (Config Hash: {fp['config_hash']})")
        return session

    def end_session(
        self,
        session_id: str,
        closing_balance: float,
        trades_count: int,
        wins: int,
        losses: int,
        net_pnl: float,
        max_drawdown: float,
    ) -> None:
        end_time = time.time()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE test_sessions
                    SET end_time = ?, closing_balance = ?, trades_count = ?,
                        wins = ?, losses = ?, net_pnl = ?, max_drawdown = ?, status = 'COMPLETED'
                    WHERE session_id = ?
                """, (end_time, closing_balance, trades_count, wins, losses, net_pnl, max_drawdown, session_id))
                conn.commit()
        except Exception as err:
            logger.error(f"[SESSION_MANAGER] Error ending session {session_id}: {err}")
        logger.info(f"[SESSION_MANAGER] Ended Session {session_id} (Net PnL: ${net_pnl:.2f}, Trades: {trades_count})")

    @classmethod
    def filter_records_by_period(cls, records: List[JournalRecord], period: str = "all") -> List[JournalRecord]:
        if period == "all" or not records:
            return records

        now = time.time()
        p_lower = period.lower()

        if p_lower == "today":
            # Records within last 24 hours
            cutoff = now - 86400
        elif p_lower in ("7d", "week"):
            cutoff = now - (7 * 86400)
        elif p_lower in ("30d", "month"):
            cutoff = now - (30 * 86400)
        else:
            cutoff = 0.0

        return [r for r in records if r.timestamp >= cutoff]
