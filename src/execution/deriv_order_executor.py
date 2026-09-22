"""
Deriv Live Order Execution Engine module for Deriv Crypto AI Bot.

Provides dedicated live binary option contract purchase execution over Deriv WebSocket API (`{"buy": 1}`)
with 5-layer safety check protocol, max stake cap clamping, runtime confirmation locks,
and emergency kill switch functionality.
"""

from dataclasses import dataclass
import time
import logging
from typing import Dict, Optional, Any

from src.config import config
from src.api.deriv_client import DerivClient, ConnectionState
from src.execution.exceptions import LiveTradingSafetyViolation

logger = logging.getLogger("DERIV_ORDER_EXECUTOR")


@dataclass
class LiveOrderResult:
    proposal_id: str
    contract_id: Optional[str]
    symbol: str
    buy_price: float
    payout: float
    purchase_time: float
    balance_after: Optional[float]
    is_success: bool
    error_message: Optional[str] = None


class DerivOrderExecutor:
    """
    Executes real binary option purchases over authenticated Deriv WebSocket API.
    """

    def __init__(
        self,
        client: DerivClient,
        max_stake_cap: float = 50.0,
        allow_live_execution: bool = False,
    ):
        self.client = client
        self.max_stake_cap = max_stake_cap
        self.allow_live_execution = allow_live_execution
        self.kill_switch_active = False
        self.kill_switch_reason = ""

    def trigger_kill_switch(self, reason: str) -> None:
        """Triggers emergency kill switch blocking all future live executions."""
        self.kill_switch_active = True
        self.kill_switch_reason = reason
        logger.critical(f"[ORDER_EXECUTOR] EMERGENCY KILL SWITCH ACTIVATED: {reason}")

    def reset_kill_switch(self) -> None:
        """Resets emergency kill switch."""
        self.kill_switch_active = False
        self.kill_switch_reason = ""
        logger.info("[ORDER_EXECUTOR] Emergency kill switch reset to operational.")

    async def execute_buy(
        self,
        proposal_id: str,
        ask_price: float,
        symbol: str,
        payout: float = 0.0,
    ) -> LiveOrderResult:
        """
        Evaluates 5-layer safety check and transmits live contract purchase payload.
        """
        # Safety Check 1: Configuration Safety Flags
        if config.dry_run or not config.live_trading:
            err_msg = (
                f"[SAFETY_VIOLATION] Live order execution blocked: "
                f"DRY_RUN={config.dry_run}, LIVE_TRADING={config.live_trading}"
            )
            logger.error(err_msg)
            return LiveOrderResult(
                proposal_id=proposal_id,
                contract_id=None,
                symbol=symbol,
                buy_price=ask_price,
                payout=payout,
                purchase_time=time.time(),
                balance_after=None,
                is_success=False,
                error_message=err_msg,
            )

        # Safety Check 2: Runtime Confirmation Lock
        if not self.allow_live_execution:
            err_msg = "[SAFETY_VIOLATION] Live execution blocked: Runtime allow_live_execution flag is False."
            logger.error(err_msg)
            return LiveOrderResult(
                proposal_id=proposal_id,
                contract_id=None,
                symbol=symbol,
                buy_price=ask_price,
                payout=payout,
                purchase_time=time.time(),
                balance_after=None,
                is_success=False,
                error_message=err_msg,
            )

        # Safety Check 3: Emergency Kill Switch
        if self.kill_switch_active:
            err_msg = f"[KILL_SWITCH_ACTIVE] Live execution blocked: {self.kill_switch_reason}"
            logger.critical(err_msg)
            return LiveOrderResult(
                proposal_id=proposal_id,
                contract_id=None,
                symbol=symbol,
                buy_price=ask_price,
                payout=payout,
                purchase_time=time.time(),
                balance_after=None,
                is_success=False,
                error_message=err_msg,
            )

        # Safety Check 4: Maximum Stake Cap
        if ask_price > self.max_stake_cap:
            err_msg = f"[STAKE_CAP_EXCEEDED] Requested stake ${ask_price:.2f} exceeds max stake cap ${self.max_stake_cap:.2f}."
            logger.error(err_msg)
            return LiveOrderResult(
                proposal_id=proposal_id,
                contract_id=None,
                symbol=symbol,
                buy_price=ask_price,
                payout=payout,
                purchase_time=time.time(),
                balance_after=None,
                is_success=False,
                error_message=err_msg,
            )

        # Safety Check 5: Authenticated Deriv Connection
        if self.client.state != ConnectionState.AUTHENTICATED:
            err_msg = f"[NOT_AUTHENTICATED] DerivClient must be authorized to place live buy orders (state={self.client.state.value})."
            logger.error(err_msg)
            return LiveOrderResult(
                proposal_id=proposal_id,
                contract_id=None,
                symbol=symbol,
                buy_price=ask_price,
                payout=payout,
                purchase_time=time.time(),
                balance_after=None,
                is_success=False,
                error_message=err_msg,
            )

        # All 5 safety checks passed. Construct live buy payload.
        payload = {
            "buy": proposal_id,
            "price": ask_price,
        }

        try:
            logger.info(f"[ORDER_EXECUTOR] Transmitting live contract purchase: proposal_id={proposal_id}, ask_price=${ask_price:.2f}...")
            response = await self.client.request(payload)

            if "error" in response:
                err_dict = response["error"]
                err_msg = f"Deriv API error [{err_dict.get('code', 'UNKNOWN')}]: {err_dict.get('message', 'Buy request failed')}"
                logger.error(f"[ORDER_EXECUTOR] Live contract purchase REJECTED: {err_msg}")
                return LiveOrderResult(
                    proposal_id=proposal_id,
                    contract_id=None,
                    symbol=symbol,
                    buy_price=ask_price,
                    payout=payout,
                    purchase_time=time.time(),
                    balance_after=None,
                    is_success=False,
                    error_message=err_msg,
                )

            buy_res = response.get("buy", {})
            contract_id = str(buy_res.get("contract_id", ""))
            buy_price = float(buy_res.get("buy_price", ask_price))
            balance_after = float(buy_res.get("balance_after", 0.0))
            purchase_time = float(buy_res.get("purchase_time", time.time()))

            logger.info(f"[ORDER_EXECUTOR] Live contract PURCHASED successfully! Contract ID: {contract_id}, Buy Price: ${buy_price:.2f}, Balance After: ${balance_after:.2f}")

            return LiveOrderResult(
                proposal_id=proposal_id,
                contract_id=contract_id,
                symbol=symbol,
                buy_price=buy_price,
                payout=payout,
                purchase_time=purchase_time,
                balance_after=balance_after,
                is_success=True,
            )
        except Exception as err:
            logger.error(f"[ORDER_EXECUTOR] Exception during live buy request: {err}")
            return LiveOrderResult(
                proposal_id=proposal_id,
                contract_id=None,
                symbol=symbol,
                buy_price=ask_price,
                payout=payout,
                purchase_time=time.time(),
                balance_after=None,
                is_success=False,
                error_message=str(err),
            )
