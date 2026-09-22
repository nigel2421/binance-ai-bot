import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
import pandas as pd

from src.api.binance_client import BinanceClient

logger = logging.getLogger("BinanceMarketDataEngine")

class Candle:
    def __init__(
        self,
        timestamp: int,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float,
        is_closed: bool = True
    ):
        self.timestamp = timestamp
        self.open = open_price
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.is_closed = is_closed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "is_closed": self.is_closed,
        }

class BinanceMarketDataEngine:
    """
    Market Data Engine managing historical klines preloading, live kline WS stream processing,
    and multi-timeframe candle buffers for crypto symbols.
    """

    SUPPORTED_TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h"]

    def __init__(self, client: Optional[BinanceClient] = None):
        self.client = client or BinanceClient()
        # Storage structure: candles_buffer[symbol][interval] = List[Candle]
        self.candles_buffer: Dict[str, Dict[str, List[Candle]]] = {}
        self.last_tick_timestamp: Dict[str, float] = {}
        self.max_buffer_size = 500

    def _init_symbol_storage(self, symbol: str):
        if symbol not in self.candles_buffer:
            self.candles_buffer[symbol] = {tf: [] for tf in self.SUPPORTED_TIMEFRAMES}

    async def preload_historical_klines(
        self,
        symbols: List[str],
        intervals: Optional[List[str]] = None,
        limit: int = 200
    ):
        """Fetch historical kline data for symbols via Binance REST API."""
        target_intervals = intervals or ["1m", "5m", "15m", "1h"]
        logger.info(f"Preloading historical klines for {len(symbols)} symbols across timeframes: {target_intervals}...")

        for s in symbols:
            self._init_symbol_storage(s)
            for tf in target_intervals:
                if tf not in self.SUPPORTED_TIMEFRAMES:
                    continue
                try:
                    raw_klines = await self.client.get_klines(s, interval=tf, limit=limit)
                    parsed_candles = []
                    for k in raw_klines:
                        # Binance kline format:
                        # [Open time, Open, High, Low, Close, Volume, Close time, ...]
                        candle = Candle(
                            timestamp=int(k[0]),
                            open_price=float(k[1]),
                            high=float(k[2]),
                            low=float(k[3]),
                            close=float(k[4]),
                            volume=float(k[5]),
                            is_closed=True
                        )
                        parsed_candles.append(candle)
                    self.candles_buffer[s][tf] = parsed_candles[-self.max_buffer_size:]
                    if parsed_candles:
                        self.last_tick_timestamp[s] = time.time()
                except Exception as e:
                    logger.error(f"Failed to preload historical klines for {s} ({tf}): {e}")

        logger.info("Historical klines preloading complete.")

    async def handle_ws_message(self, msg: Dict[str, Any]):
        """Callback for processing live WebSocket stream messages from Binance."""
        if "data" not in msg:
            return
        
        data = msg["data"]
        e_type = data.get("e")
        if e_type == "kline":
            k = data["k"]
            symbol = k["s"]
            interval = k["i"]
            is_closed = k["x"]

            self._init_symbol_storage(symbol)
            candle = Candle(
                timestamp=int(k["t"]),
                open_price=float(k["o"]),
                high=float(k["h"]),
                low=float(k["l"]),
                close=float(k["c"]),
                volume=float(k["v"]),
                is_closed=is_closed
            )

            if interval in self.candles_buffer[symbol]:
                buf = self.candles_buffer[symbol][interval]
                if buf and buf[-1].timestamp == candle.timestamp:
                    buf[-1] = candle  # Update current forming candle
                else:
                    buf.append(candle)
                    if len(buf) > self.max_buffer_size:
                        buf.pop(0)

            self.last_tick_timestamp[symbol] = time.time()

    def get_candles(self, symbol: str, interval: str = "1m") -> List[Candle]:
        """Return list of candle objects for symbol and timeframe."""
        return self.candles_buffer.get(symbol, {}).get(interval, [])

    def get_dataframe(self, symbol: str, interval: str = "1m") -> pd.DataFrame:
        """Return pandas DataFrame for candles of given symbol & interval."""
        candles = self.get_candles(symbol, interval)
        if not candles:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume", "is_closed"])
        
        data = [c.to_dict() for c in candles]
        df = pd.DataFrame(data)
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df

    def is_stale(self, symbol: str, max_age_seconds: float = 30.0) -> bool:
        """Check if market data for symbol is stale."""
        last_t = self.last_tick_timestamp.get(symbol, 0)
        return (time.time() - last_t) > max_age_seconds
