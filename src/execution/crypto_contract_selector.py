"""
Crypto Contract Selector & Duration Engine for Deriv Crypto AI Bot Stage 6.

Separates market intelligence opinion from financial contract selection.
Maps consensus direction (BULLISH/BEARISH) and timeframe/regime into compatible,
API-confirmed Deriv contract options and duration parameters.
"""

from dataclasses import dataclass, field
from enum import Enum
import logging
import time
from typing import Dict, Any, List, Optional, Tuple

from src.opportunity.crypto_opportunity_scorer import CryptoOpportunity
from src.consensus.crypto_consensus_engine import ConsensusResult, ConsensusDirection
from src.market.crypto_market_registry import CryptoMarketRegistry

logger = logging.getLogger("CONTRACT_SELECTOR")


@dataclass
class ContractCandidate:
    symbol: str
    direction: str                             # BULLISH or BEARISH
    contract_type: str                         # CALL, PUT, MULTUP, MULTDOWN, etc.
    duration: int
    duration_unit: str                         # m, h, d, s, t
    basis: str = "stake"
    barrier: Optional[str] = None
    selection_reason: str = ""
    is_available: bool = True
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "contract_type": self.contract_type,
            "duration": self.duration,
            "duration_unit": self.duration_unit,
            "basis": self.basis,
            "barrier": self.barrier,
            "selection_reason": self.selection_reason,
            "is_available": self.is_available,
            "rejection_reason": self.rejection_reason,
        }


class ContractDurationEngine:
    """
    Selects valid contract duration based on strategy timeframe, regime, and API contract limits.
    """

    DEFAULT_TIMEFRAME_DURATIONS = {
        "1m": (5, "m"),
        "5m": (15, "m"),
        "15m": (30, "m"),
        "30m": (1, "h"),
        "1h": (4, "h"),
        "4h": (1, "d"),
    }

    @classmethod
    def select_duration(
        self,
        timeframe: str,
        regime: str,
        min_seconds: int = 60,
        max_seconds: int = 86400,
    ) -> Tuple[int, str]:
        """Calculates appropriate duration and unit for contract proposal."""
        dur, unit = self.DEFAULT_TIMEFRAME_DURATIONS.get(timeframe, (15, "m"))

        # Adjust for regime
        reg_upper = regime.upper()
        if "BREAKOUT" in reg_upper:
            # Short-horizon breakout
            dur, unit = max(1, dur // 2), unit

        return dur, unit


class CryptoContractSelector:
    """
    Selects API-supported financial derivative contracts based on market intelligence.
    """

    DIRECTION_CONTRACT_MAP = {
        "BULLISH": ["CALL", "MULTUP", "HIGHER"],
        "BEARISH": ["PUT", "MULTDOWN", "LOWER"],
    }

    def __init__(self, registry: Optional[CryptoMarketRegistry] = None):
        self.registry = registry or CryptoMarketRegistry()

    def select_contract(
        self,
        opportunity: Optional[Any] = None,
        consensus: Optional[Any] = None,
        preferred_timeframe: str = "15m",
        symbol: Optional[str] = None,
        direction: Optional[str] = None,
        regime: str = "RANGING",
        timeframe: Optional[str] = None,
        available_contracts: Optional[List[str]] = None,
    ) -> ContractCandidate:
        sym = symbol or (opportunity.symbol if opportunity else "UNKNOWN")
        dir_val = direction or (opportunity.direction if opportunity else (consensus.direction if consensus else "NONE"))
        reg_val = regime or (consensus.regime if consensus else "RANGING")
        tf_val = timeframe or preferred_timeframe or (opportunity.timeframe if hasattr(opportunity, "timeframe") else "15m")

        if dir_val not in ("BULLISH", "BEARISH"):
            return ContractCandidate(
                symbol=sym,
                direction=dir_val,
                contract_type="NONE",
                duration=0,
                duration_unit="m",
                is_available=False,
                rejection_reason=f"Unsupported direction for contract selection: {dir_val}",
            )

        sym_caps = self.registry.contract_capabilities.get(sym, {})
        possible_types = self.DIRECTION_CONTRACT_MAP.get(dir_val, [])

        matched_type = None
        # Check against passed available_contracts or registry caps
        avail = available_contracts if available_contracts is not None else list(sym_caps.keys())
        for c_type in possible_types:
            if not avail or c_type in avail or c_type in sym_caps:
                matched_type = c_type
                break

        # Fallback to standard CALL/PUT if no specific type matched
        if not matched_type:
            matched_type = "CALL" if dir_val == "BULLISH" else "PUT"

        cap_obj = sym_caps.get(matched_type)
        min_sec = cap_obj.min_seconds if cap_obj else 60
        max_sec = cap_obj.max_seconds if cap_obj else 86400

        dur, unit = ContractDurationEngine.select_duration(
            timeframe=tf_val,
            regime=reg_val,
            min_seconds=min_sec,
            max_seconds=max_sec,
        )

        return ContractCandidate(
            symbol=sym,
            direction=dir_val,
            contract_type=matched_type,
            duration=dur,
            duration_unit=unit,
            basis="stake",
            selection_reason=f"Matched {matched_type} for {dir_val} setup in {reg_val} regime",
            is_available=True,
        )
