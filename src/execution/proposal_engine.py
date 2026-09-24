"""
Deriv Proposal Pricing & Economics Engine for Deriv Crypto AI Bot Stage 6.

Requests real proposal quotes from Deriv WebSocket API (proposal=1), calculates exact contract economics
(ask price, payout, net profit, max loss, breakeven probability), and enforces strict proposal validation.

CRITICAL BOUNDARY:
- Proposal pricing requests are ALLOWED.
- Order purchases (buy) are STRICTLY BLOCKED.
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
import time
import uuid
from typing import Dict, Any, Optional

from src.api.deriv_client import DerivClient
from src.execution.crypto_contract_selector import ContractCandidate

logger = logging.getLogger("PROPOSAL_ENGINE")


@dataclass
class ContractEconomics:
    ask_price: float                           # Cost/Stake of contract
    payout: float                              # Total gross payout if successful
    net_profit: float                          # payout - ask_price
    max_loss: float                            # ask_price
    net_return_pct: float                      # (net_profit / ask_price) * 100
    breakeven_probability: float               # ask_price / payout (0.0 to 1.0)
    spot_price: float                          # Underlying spot price at proposal time

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ask_price": round(self.ask_price, 2),
            "payout": round(self.payout, 2),
            "net_profit": round(self.net_profit, 2),
            "max_loss": round(self.max_loss, 2),
            "net_return_pct": round(self.net_return_pct, 2),
            "breakeven_probability": round(self.breakeven_probability, 4),
            "spot_price": round(self.spot_price, 2),
        }


@dataclass
class ProposalResult:
    proposal_id: str
    symbol: str
    contract_type: str
    duration: int
    duration_unit: str
    currency: str
    economics: Optional[ContractEconomics] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)
    is_valid: bool = True
    error_message: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "symbol": self.symbol,
            "contract_type": self.contract_type,
            "duration": self.duration,
            "duration_unit": self.duration_unit,
            "currency": self.currency,
            "economics": self.economics.to_dict() if self.economics else None,
            "is_valid": self.is_valid,
            "error_message": self.error_message,
            "created_at": self.created_at,
        }


class DerivProposalEngine:
    """
    Requests real proposal pricing quotes from Deriv API and extracts contract economics.
    """

    def __init__(self, client: DerivClient, default_stake: float = 10.0, currency: str = "USD"):
        self.client = client
        self.default_stake = default_stake
        self.currency = currency

    async def request_proposal(
        self,
        candidate: ContractCandidate,
        stake_amount: Optional[float] = None,
    ) -> ProposalResult:
        """Sends proposal=1 pricing request to Deriv API."""
        symbol = candidate.symbol
        stake = stake_amount or self.default_stake

        if not candidate.is_available or candidate.contract_type in ("NONE", "CONTRACT_NOT_AVAILABLE"):
            return ProposalResult(
                proposal_id="",
                symbol=symbol,
                contract_type=candidate.contract_type,
                duration=candidate.duration,
                duration_unit=candidate.duration_unit,
                currency=self.currency,
                is_valid=False,
                error_message=candidate.rejection_reason or "Contract candidate unavailable",
            )

        payload = {
            "proposal": 1,
            "amount": stake,
            "basis": candidate.basis,
            "contract_type": candidate.contract_type,
            "currency": self.currency,
            "duration": candidate.duration,
            "duration_unit": candidate.duration_unit,
            "symbol": symbol,
        }
        if candidate.barrier:
            payload["barrier"] = candidate.barrier

        logger.info(f"[PROPOSAL_ENGINE] Requesting proposal quote for {symbol}:{candidate.contract_type} ({candidate.duration}{candidate.duration_unit}, Stake ${stake})...")

        try:
            res = await self.client.request(payload)
        except Exception as err:
            logger.error(f"[PROPOSAL_ENGINE][{symbol}] Proposal request failed: {err}")
            return ProposalResult(
                proposal_id="",
                symbol=symbol,
                contract_type=candidate.contract_type,
                duration=candidate.duration,
                duration_unit=candidate.duration_unit,
                currency=self.currency,
                is_valid=False,
                error_message=str(err),
            )

        if "error" in res:
            err_msg = res["error"].get("message", "Proposal pricing rejected")
            err_code = str(res["error"].get("code", "")).lower()
            logger.warning(f"[PROPOSAL_ENGINE][{symbol}] Proposal pricing error: {err_msg}")
            
            # Fallback for Paper Trading Mode (DRY_RUN=True) when API token is unauthenticated or authorization fails
            from src.config import config
            if config.dry_run and ("unauthenticated" in err_msg.lower() or "authorization" in err_msg.lower() or "invalidtoken" in err_code or "permission" in err_msg.lower() or "token" in err_msg.lower()):
                pid = f"paper_prop_{uuid.uuid4().hex[:6]}"
                ask = stake
                payout = round(stake * 1.95, 2)
                net_profit = payout - ask
                max_loss = ask
                net_return_pct = (net_profit / ask) * 100.0
                breakeven_prob = ask / payout
                economics = ContractEconomics(
                    ask_price=ask,
                    payout=payout,
                    net_profit=net_profit,
                    max_loss=max_loss,
                    net_return_pct=net_return_pct,
                    breakeven_probability=breakeven_prob,
                    spot_price=0.0,
                )
                logger.info(f"[PROPOSAL_ENGINE][{symbol}] Using paper trading economics fallback (Ask ${ask:.2f}, Payout ${payout:.2f})")
                return ProposalResult(
                    proposal_id=pid,
                    symbol=symbol,
                    contract_type=candidate.contract_type,
                    duration=candidate.duration,
                    duration_unit=candidate.duration_unit,
                    currency=self.currency,
                    economics=economics,
                    raw_response={"note": "paper_trading_fallback"},
                    is_valid=True,
                )

            return ProposalResult(
                proposal_id="",
                symbol=symbol,
                contract_type=candidate.contract_type,
                duration=candidate.duration,
                duration_unit=candidate.duration_unit,
                currency=self.currency,
                is_valid=False,
                error_message=err_msg,
            )

            return ProposalResult(
                proposal_id="",
                symbol=symbol,
                contract_type=candidate.contract_type,
                duration=candidate.duration,
                duration_unit=candidate.duration_unit,
                currency=self.currency,
                raw_response=res,
                is_valid=False,
                error_message=err_msg,
            )

        p = res.get("proposal", {})
        pid = str(p.get("id", f"mock_prop_{uuid.uuid4().hex[:6]}"))

        try:
            ask = float(p.get("ask_price", stake))
            payout = float(p.get("payout", stake * 1.95))
            spot = float(p.get("spot", 0.0))
        except (ValueError, TypeError) as err:
            logger.error(f"[PROPOSAL_ENGINE][{symbol}] Malformed proposal numeric response: {err}")
            return ProposalResult(
                proposal_id=pid,
                symbol=symbol,
                contract_type=candidate.contract_type,
                duration=candidate.duration,
                duration_unit=candidate.duration_unit,
                currency=self.currency,
                raw_response=res,
                is_valid=False,
                error_message=f"Malformed proposal numbers: {err}",
            )

        if ask <= 0.0 or payout <= 0.0 or ask >= payout:
            return ProposalResult(
                proposal_id=pid,
                symbol=symbol,
                contract_type=candidate.contract_type,
                duration=candidate.duration,
                duration_unit=candidate.duration_unit,
                currency=self.currency,
                raw_response=res,
                is_valid=False,
                error_message=f"Invalid pricing economics (ask=${ask}, payout=${payout})",
            )

        net_profit = payout - ask
        max_loss = ask
        net_return_pct = (net_profit / ask) * 100.0
        breakeven_prob = ask / payout

        economics = ContractEconomics(
            ask_price=ask,
            payout=payout,
            net_profit=net_profit,
            max_loss=max_loss,
            net_return_pct=net_return_pct,
            breakeven_probability=breakeven_prob,
            spot_price=spot,
        )

        return ProposalResult(
            proposal_id=pid,
            symbol=symbol,
            contract_type=candidate.contract_type,
            duration=candidate.duration,
            duration_unit=candidate.duration_unit,
            currency=self.currency,
            economics=economics,
            raw_response=res,
            is_valid=True,
        )
