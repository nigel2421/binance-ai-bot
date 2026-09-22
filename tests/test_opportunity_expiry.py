"""
Unit tests for opportunity expiration.
"""

import time
import pytest
from src.opportunity.crypto_opportunity_scorer import CryptoOpportunity, OpportunityStatus, OpportunityTier
from src.opportunity.crypto_opportunity_ranker import CryptoOpportunityRanker


def test_opportunity_expiration_filtering():
    now = time.time()
    op_fresh = CryptoOpportunity("op1", "cryBTCUSD", "BULLISH", 80.0, 80.0, 80.0, 80.0, 80.0, 75.0, 90.0, 80.0, 0.0, "CryptoTrendAgent", created_at=now, expires_at=now+100.0, status=OpportunityStatus.QUALIFIED_LIVE, tier=OpportunityTier.STRONG)
    op_expired = CryptoOpportunity("op2", "cryETHUSD", "BULLISH", 85.0, 85.0, 85.0, 85.0, 85.0, 75.0, 90.0, 85.0, 0.0, "CryptoMomentumAgent", created_at=now-200.0, expires_at=now-10.0, status=OpportunityStatus.QUALIFIED_LIVE, tier=OpportunityTier.ELITE)

    ranked = CryptoOpportunityRanker.rank_opportunities([op_fresh, op_expired], current_time=now)

    assert len(ranked) == 1
    assert ranked[0].symbol == "cryBTCUSD"
