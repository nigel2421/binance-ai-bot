import pytest
from src.execution.crypto_contract_selector import CryptoContractSelector, ContractDurationEngine, ContractCandidate
from src.opportunity.crypto_opportunity_scorer import CryptoOpportunity, OpportunityStatus, OpportunityTier
from src.consensus.crypto_consensus_engine import ConsensusResult, ConsensusDirection, ConsensusStrength
from src.market.crypto_market_registry import CryptoMarketRegistry, CryptoContractCapability


def test_contract_selector_bullish_mapping():
    registry = CryptoMarketRegistry()
    selector = CryptoContractSelector(registry=registry)

    op = CryptoOpportunity("op1", "cryBTCUSD", "BULLISH", 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 80.0, 0.0, "CryptoTrendAgent", status=OpportunityStatus.QUALIFIED_LIVE, tier=OpportunityTier.STRONG)
    consensus = ConsensusResult("c1", "cryBTCUSD", 1000.0, ConsensusDirection.BULLISH, 0.80, 100.0, 0.0, 0.0, 2.0, 0.0, 0.0, regime="STRONG_UPTREND")

    candidate = selector.select_contract(op, consensus, preferred_timeframe="15m")

    assert candidate.symbol == "cryBTCUSD"
    assert candidate.direction == "BULLISH"
    assert candidate.contract_type == "CALL"
    assert candidate.duration == 30
    assert candidate.duration_unit == "m"
    assert candidate.is_available is True


def test_contract_duration_engine_breakout_adjustment():
    dur, unit = ContractDurationEngine.select_duration("15m", "BREAKOUT_BULLISH")
    assert dur == 15  # 30 // 2
    assert unit == "m"
