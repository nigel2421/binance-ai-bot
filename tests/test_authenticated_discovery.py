import pytest
from unittest.mock import AsyncMock, patch
from src.api.deriv_client import DerivClient, ConnectionState
from src.market.crypto_market_registry import CryptoMarketRegistry, CryptoSymbolInfo


@pytest.mark.asyncio
async def test_deriv_client_sanitized_authorization():
    client = DerivClient(api_token="test_secret_token_12345")
    
    with patch.object(client, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"authorize": {"email": "trader@example.com", "balance": 1000.0}}
        res = await client.authorize()
        
        assert client.state == ConnectionState.AUTHENTICATED
        assert res.get("authorize", {}).get("email") == "trader@example.com"
        mock_req.assert_called_once_with({"authorize": "test_secret_token_12345"})


@pytest.mark.asyncio
async def test_contracts_for_capability_discovery_unconfirmed():
    client = DerivClient()
    registry = CryptoMarketRegistry(client=client)

    registry.symbols_info["cryBTCUSD"] = CryptoSymbolInfo({"symbol": "cryBTCUSD", "display_name": "Bitcoin / USD"})

    with patch.object(client, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"contracts_for": {"available": []}}
        caps = await registry.discover_contracts_for_symbol("cryBTCUSD")

        assert caps == {}
        assert registry.symbols_info["cryBTCUSD"].trading_capabilities["status"] == "UNKNOWN"

    matrix = registry.generate_capability_matrix_report()
    assert "cryBTCUSD" in matrix
    assert matrix["cryBTCUSD"]["trading_capability"]["status"] == "UNKNOWN"
