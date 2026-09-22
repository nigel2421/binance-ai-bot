"""
Deriv Contract Settlement Tracker module for Deriv Crypto AI Bot.

Subscribes to live Deriv WebSocket `proposal_open_contract` (POC) stream to track real-time
contract settlement outcomes, payout processing, and journal updates for live binary options.
"""

from dataclasses import dataclass
import time
import logging
from typing import Dict, List, Optional, Any

from src.api.deriv_client import DerivClient
from src.execution.trade_journal import CryptoTradeJournal

logger = logging.getLogger("SETTLEMENT_TRACKER")


@dataclass
class ContractSettlementInfo:
    contract_id: str
    record_id: str
    symbol: str
    status: str                                  # "WON", "LOST", "OPEN", "EXPIRED"
    profit: float
    payout: float
    spot_exit: float
    settled_at: Optional[float]
    is_settled: bool


class DerivSettlementTracker:
    """
    Subscribes to proposal_open_contract streams and updates trade journal upon contract resolution.
    """

    def __init__(self, client: DerivClient, trade_journal: CryptoTradeJournal):
        self.client = client
        self.trade_journal = trade_journal
        self.tracked_contracts: Dict[str, Dict[str, Any]] = {}
        self.settled_history: Dict[str, ContractSettlementInfo] = {}

    async def subscribe_contract(self, contract_id: str, record_id: str, symbol: str) -> bool:
        """
        Subscribes to proposal_open_contract updates for a specific purchased contract.
        """
        if not contract_id:
            logger.warning("[SETTLEMENT_TRACKER] Cannot subscribe: empty contract_id.")
            return False

        payload = {
            "proposal_open_contract": 1,
            "contract_id": contract_id,
            "subscribe": 1,
        }

        sub_id = await self.client.subscribe(
            payload=payload,
            callback=lambda msg: self._on_poc_message(msg, contract_id=contract_id),
        )

        if sub_id:
            self.tracked_contracts[contract_id] = {
                "record_id": record_id,
                "symbol": symbol,
                "subscription_id": sub_id,
                "subscribed_at": time.time(),
            }
            logger.info(f"[SETTLEMENT_TRACKER] Subscribed to POC stream for contract_id={contract_id} (record_id={record_id}).")
            return True
        else:
            logger.error(f"[SETTLEMENT_TRACKER] Failed to subscribe to POC stream for contract_id={contract_id}.")
            return False

    def _on_poc_message(self, msg: Dict[str, Any], contract_id: str) -> None:
        """
        Parses incoming proposal_open_contract WebSocket message.
        """
        msg_type = msg.get("msg_type")
        if msg_type != "proposal_open_contract":
            return

        poc = msg.get("proposal_open_contract", {})
        c_id = str(poc.get("contract_id", contract_id))

        info = self.tracked_contracts.get(c_id)
        if not info:
            return

        record_id = info["record_id"]
        symbol = info["symbol"]

        is_sold = bool(poc.get("is_sold") == 1)
        is_expired = bool(poc.get("is_expired") == 1)
        is_settled = bool(poc.get("is_settled") == 1 or is_sold or is_expired)
        raw_status = str(poc.get("status", "open")).lower()

        profit = float(poc.get("profit", 0.0))
        payout = float(poc.get("payout", 0.0))
        exit_spot = float(poc.get("exit_tick") or poc.get("sell_price") or 0.0)

        if raw_status == "won":
            status_str = "WON"
        elif raw_status == "lost":
            status_str = "LOST"
        elif is_settled:
            status_str = "WON" if profit > 0 else "LOST"
        else:
            status_str = "OPEN"

        settlement_info = ContractSettlementInfo(
            contract_id=c_id,
            record_id=record_id,
            symbol=symbol,
            status=status_str,
            profit=profit,
            payout=payout,
            spot_exit=exit_spot,
            settled_at=time.time() if is_settled else None,
            is_settled=is_settled,
        )

        if is_settled:
            logger.info(f"[SETTLEMENT_TRACKER] Contract {c_id} ({symbol}) SETTLED: {status_str} (Profit: ${profit:.2f}, Spot Exit: {exit_spot})")
            self.trade_journal.update_settlement(
                record_id=record_id,
                status=status_str,
                spot_exit=exit_spot,
                pnl=profit,
            )
            self.settled_history[c_id] = settlement_info
            if c_id in self.tracked_contracts:
                del self.tracked_contracts[c_id]
