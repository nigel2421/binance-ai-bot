"""
Unit tests for CryptoOpportunityRanker.
"""

import time
import pytest
from src.opportunity.crypto_opportunity_scorer import CryptoOpportunity, OpportunityStatus, OpportunityTier
from src.opportunity.crypto_opportunity_ranker import CryptoOpportunityRanker


def test_opportunity_ranker_sorting():
    now = time.time()
    op1 = CryptoOpportunity("op1", "cryETHUSD", "BULLISH", 85.0, 80.0, 85.0, 85.0, 85.0, 75.0, 90.0, 85.0, 0.0, "CryptoMomentumAgent", created_at=now, expires_at=now+300, status=OpportunityStatus.QUALIFIED_LIVE, tier=OpportunityTier.ELITE)
    op2 = CryptoOpportunity("op2", "cryBCHUSD", "BULLISH", 94.0, 90.0, 95.0, 95.0, 90.0, 75.0, 90.0, 90.0, 0.0, "CryptoTrendAgent", created_at=now, expires_at=now+300, status=OpportunityStatus.QUALIFIED_LIVE, tier=OpportunityTier.ELITE)
    op3 = CryptoOpportunity("op3", "cryADAUSD", "CONFLICTED", 0.0, 0.0, 60.0, 60.0, 60.0, 0.0, 90.0, 0.0, 50.0, "CryptoTrendAgent", created_at=now, expires_at=now+300, status=OpportunityStatus.CONFLICTED, tier=OpportunityTier.REJECT)

    ranked = CryptoOpportunityRanker.rank_opportunities([op1, op2, op3], current_time=now)

    assert len(ranked) == 2
    assert ranked[0].symbol == "cryBCHUSD"
    assert ranked[1].symbol == "cryETHUSD"
