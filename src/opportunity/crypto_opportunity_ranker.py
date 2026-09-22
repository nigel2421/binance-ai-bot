"""
Crypto Opportunity Ranker for Deriv Crypto AI Bot Stage 5.

Collects CryptoOpportunity objects across all monitored markets, sorts descending by
opportunity score, filters out expired/conflicted setups, and assigns research tiers.

NO trade instructions or contract purchases.
"""

import logging
import time
from typing import Dict, List, Optional

from src.opportunity.crypto_opportunity_scorer import CryptoOpportunity, OpportunityStatus, OpportunityTier

logger = logging.getLogger("OPPORTUNITY_RANKER")


class CryptoOpportunityRanker:
    """
    Ranks qualified crypto opportunities across active markets.
    """

    @staticmethod
    def rank_opportunities(
        opportunities: List[CryptoOpportunity],
        current_time: Optional[float] = None,
        min_score: float = 0.0,
    ) -> List[CryptoOpportunity]:
        """
        Ranks opportunities descending by opportunity_score.
        Filters out expired and invalid opportunities.
        """
        now = time.time() if current_time is None else current_time
        valid_ops = [
            op for op in opportunities
            if op.is_valid_and_fresh(now) and op.opportunity_score >= min_score
        ]

        valid_ops.sort(key=lambda op: op.opportunity_score, reverse=True)
        return valid_ops

    @staticmethod
    def get_top_conflicted_markets(opportunities: List[CryptoOpportunity], limit: int = 5) -> List[CryptoOpportunity]:
        """Returns opportunities flagged as CONFLICTED or having high conflict penalties."""
        conflicted = [
            op for op in opportunities
            if op.status == OpportunityStatus.CONFLICTED or op.conflict_penalty >= 15.0
        ]
        conflicted.sort(key=lambda op: op.conflict_penalty, reverse=True)
        return conflicted[:limit]
