import pytest
from unittest.mock import AsyncMock, patch
from src.api.deriv_client import DerivClient
from src.execution.crypto_contract_selector import ContractCandidate
from src.execution.proposal_engine import DerivProposalEngine, ProposalResult, ContractEconomics


@pytest.mark.asyncio
async def test_proposal_engine_successful_quote():
    client = DerivClient()
    proposal_engine = DerivProposalEngine(client=client, default_stake=10.0)

    candidate = ContractCandidate(
        symbol="cryBTCUSD",
        direction="BULLISH",
        contract_type="CALL",
        duration=30,
        duration_unit="m",
    )

    mock_resp = {
        "proposal": {
            "id": "prop_xyz123",
            "ask_price": 10.0,
            "payout": 19.50,
            "spot": 50000.0,
        }
    }

    with patch.object(client, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_resp
        res = await proposal_engine.request_proposal(candidate, stake_amount=10.0)

        assert res.is_valid is True
        assert res.proposal_id == "prop_xyz123"
        assert res.economics is not None
        assert res.economics.ask_price == 10.0
        assert res.economics.payout == 19.50
        assert res.economics.net_profit == 9.50
        assert res.economics.breakeven_probability == pytest.approx(0.5128, abs=0.001)


@pytest.mark.asyncio
async def test_proposal_engine_rejected_quote():
    client = DerivClient()
    proposal_engine = DerivProposalEngine(client=client)

    candidate = ContractCandidate(
        symbol="cryETHUSD",
        direction="BEARISH",
        contract_type="PUT",
        duration=15,
        duration_unit="m",
    )

    mock_resp = {"error": {"message": "Symbol is unavailable for trading"}}

    with patch.object(client, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_resp
        res = await proposal_engine.request_proposal(candidate)

        assert res.is_valid is False
        assert "unavailable" in res.error_message.lower()
