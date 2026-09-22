import asyncio
import json
import logging
import hmac
import hashlib
import time
from typing import Dict, Any, List, Optional, Callable
import aiohttp
import websockets

from src.config import config

logger = logging.getLogger("BinanceClient")

class BinanceClient:
    """
    Asynchronous REST & WebSocket client for Binance API (Spot / Futures).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        rest_url: Optional[str] = None,
        ws_url: Optional[str] = None
    ):
        self.api_key = api_key or config.binance_api_key
        self.api_secret = api_secret or config.binance_api_secret
        self.rest_url = (rest_url or config.binance_rest_url).rstrip("/")
        self.ws_url = (ws_url or config.binance_ws_url).rstrip("/")
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws_connection = None
        self.is_connected = False
        self._running = False

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            headers = {"User-Agent": "Binance-Crypto-AI-Bot/1.0"}
            if self.api_key:
                headers["X-MBX-APIKEY"] = self.api_key
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    async def get_exchange_info(self) -> Dict[str, Any]:
        """Fetch exchange metadata including active symbols, status, precisions, and filters."""
        session = await self._get_session()
        url = f"{self.rest_url}/api/v3/exchangeInfo"
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json()

    async def get_klines(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 500
    ) -> List[List[Any]]:
        """Fetch historical kline/candlestick bars from Binance REST API."""
        session = await self._get_session()
        url = f"{self.rest_url}/api/v3/klines"
        params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
        async with session.get(url, params=params) as response:
            response.raise_for_status()
            return await response.json()

    async def get_ticker_price(self, symbol: Optional[str] = None) -> Any:
        """Fetch latest price ticker for symbol or all symbols."""
        session = await self._get_session()
        url = f"{self.rest_url}/api/v3/ticker/price"
        params = {"symbol": symbol.upper()} if symbol else {}
        async with session.get(url, params=params) as response:
            response.raise_for_status()
            return await response.json()

    async def get_account_info(self, recv_window: int = 10000) -> Dict[str, Any]:
        """Fetch private account metadata and balances using signed API request."""
        session = await self._get_session()
        params = {
            "recvWindow": recv_window,
            "timestamp": int(time.time() * 1000),
        }
        query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        sig = self._generate_signature(params)
        url = f"{self.rest_url}/api/v3/account?{query_string}&signature={sig}"
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json()

    async def stream_klines(
        self,
        symbols: List[str],
        intervals: List[str],
        callback: Callable[[Dict[str, Any]], None]
    ):
        """
        Connect to Binance combined WebSocket stream for klines.
        e.g., stream parameter: btcusdt@kline_1m/ethusdt@kline_1m
        """
        self._running = True
        stream_names = [
            f"{s.lower()}@kline_{i}"
            for s in symbols
            for i in intervals
        ]
        ws_endpoint = f"{self.ws_url}/stream?streams={'/'.join(stream_names)}"
        logger.info(f"Connecting to Binance combined stream for {len(symbols)} symbols: {ws_endpoint}")

        retry_delay = 2
        while self._running:
            try:
                async with websockets.connect(ws_endpoint, ping_interval=20, ping_timeout=10) as ws:
                    self.ws_connection = ws
                    self.is_connected = True
                    logger.info("Binance WebSocket stream established successfully.")
                    retry_delay = 2

                    async for message in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(message)
                            await callback(data)
                        except Exception as parse_err:
                            logger.error(f"Error handling WS message: {parse_err}")

            except asyncio.CancelledError:
                logger.info("WebSocket stream cancelled.")
                break
            except Exception as e:
                self.is_connected = False
                logger.warning(f"WebSocket connection dropped ({e}). Reconnecting in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)

    async def close(self):
        """Close REST session and WebSocket connection."""
        self._running = False
        if self.ws_connection:
            await self.ws_connection.close()
        if self.session and not self.session.closed:
            await self.session.close()
        self.is_connected = False
        logger.info("BinanceClient closed.")
