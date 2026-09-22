"""
Unit tests for Web Backend API Server (src.web.app).
"""

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from src.web.app import create_app


@pytest_asyncio.fixture
async def web_client():
    app = create_app()
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    yield client
    await client.close()


@pytest.mark.asyncio
async def test_web_status_endpoint(web_client):
    resp = await web_client.get('/api/status')
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "ONLINE"
    assert "config_version" in data
    assert "monitored_markets" in data


@pytest.mark.asyncio
async def test_web_markets_endpoint(web_client):
    resp = await web_client.get('/api/markets')
    assert resp.status == 200
    data = await resp.json()
    assert "markets" in data
    assert len(data["markets"]) >= 8
    assert data["markets"][0]["symbol"] == "cryBTCUSD"


@pytest.mark.asyncio
async def test_web_performance_endpoint(web_client):
    resp = await web_client.get('/api/performance')
    assert resp.status == 200
    data = await resp.json()
    assert "win_rate" in data
    assert "net_pnl" in data
    assert "profit_factor" in data


@pytest.mark.asyncio
async def test_web_strategies_endpoint(web_client):
    resp = await web_client.get('/api/strategies')
    assert resp.status == 200
    data = await resp.json()
    assert "strategies" in data
    assert len(data["strategies"]) == 5
    assert data["strategies"][0]["strategy"] == "CryptoTrendAgent"


@pytest.mark.asyncio
async def test_web_funnel_endpoint(web_client):
    resp = await web_client.get('/api/funnel')
    assert resp.status == 200
    data = await resp.json()
    assert "funnel_stages" in data
    assert "top_rejections" in data


@pytest.mark.asyncio
async def test_web_journal_endpoint(web_client):
    resp = await web_client.get('/api/journal')
    assert resp.status == 200
    data = await resp.json()
    assert "journal" in data


@pytest.mark.asyncio
async def test_web_index_page(web_client):
    resp = await web_client.get('/')
    assert resp.status == 200
    text = await resp.text()
    assert "<title>Deriv & Binance Crypto AI Bot — Live Dashboard</title>" in text
