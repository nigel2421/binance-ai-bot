import asyncio
import logging
import time
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

from src.api.deriv_client import DerivClient
from src.config import config

logger = logging.getLogger("MARKET")

class TimeframeReadiness(str, Enum):
    READY = "READY"
    WARMING_UP = "WARMING_UP"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

class Candle:
    def __init__(
        self,
        timestamp: int,
        open_price: float,
        high: float,
        low: float,
        close: float,
        tick_count: int = 1,
        complete: bool = False
    ):
        self.timestamp = int(timestamp)  # UTC epoch seconds of candle start boundary
        self.open = float(open_price)
        self.high = float(high)
        self.low = float(low)
        self.close = float(close)
        self.tick_count = int(tick_count)  # Tick activity count (NOT volume)
        self.complete = bool(complete)

    def update_tick(self, price: float):
        """Update forming candle with a new tick price."""
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.tick_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "tick_count": self.tick_count,
            "complete": self.complete,
        }

class CryptoMarketDataEngine:
    """
    Market Data Engine managing live tick processing, late/duplicate tick filtering,
    deterministic UTC epoch boundary candle aggregation across 6 timeframes (1m, 5m, 15m, 30m, 1h, 4h),
    and historical warmup readiness.
    """

    TIMEFRAMES_SEC = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "4h": 14400,
    }

    def __init__(self, client: Optional[DerivClient] = None):
        self.client = client or DerivClient()

        # Bounded buffers: candles_buffer[symbol][timeframe] = List[Candle]
        self.candles_buffer: Dict[str, Dict[str, List[Candle]]] = {}
        self.readiness: Dict[str, Dict[str, TimeframeReadiness]] = {}

        # Price & Tick metrics per symbol
        self.last_price: Dict[str, float] = {}
        self.previous_price: Dict[str, float] = {}
        self.tick_count: Dict[str, int] = {}
        self.last_tick_timestamp: Dict[str, float] = {}
        self.recent_tick_times: Dict[str, List[float]] = {}  # for ticks/min calculation
        self.price_buffer: Dict[str, List[float]] = {}        # bounded tick price history (max 1000)

        self.max_candle_buffer = 500
        self.max_price_buffer = 1000

    def _init_symbol(self, symbol: str):
        if symbol not in self.candles_buffer:
            self.candles_buffer[symbol] = {tf: [] for tf in self.TIMEFRAMES_SEC}
            self.readiness[symbol] = {tf: TimeframeReadiness.WARMING_UP for tf in self.TIMEFRAMES_SEC}
            self.last_price[symbol] = 0.0
            self.previous_price[symbol] = 0.0
            self.tick_count[symbol] = 0
            self.last_tick_timestamp[symbol] = 0.0
            self.recent_tick_times[symbol] = []
            self.price_buffer[symbol] = []

    def get_candle_boundary(self, timestamp: float, timeframe_sec: int) -> int:
        """Calculate deterministic UTC epoch boundary start timestamp for timeframe."""
        return (int(timestamp) // timeframe_sec) * timeframe_sec

    def process_tick(self, symbol: str, price: float, epoch_time: float) -> bool:
        """
        Validate and process a tick into price buffers and UTC candles.
        Returns True if tick was accepted, False if malformed/duplicate/late.
        """
        self._init_symbol(symbol)

        # 1. Validation: Malformed price or timestamp
        if price <= 0 or epoch_time <= 0:
            logger.warning(f"[MARKET] Malformed tick rejected for {symbol}: price={price}, time={epoch_time}")
            return False

        last_t = self.last_tick_timestamp[symbol]

        # 2. Duplicate or out-of-order tick validation
        if epoch_time < last_t:
            logger.debug(f"[MARKET] Out-of-order/late tick rejected for {symbol}: {epoch_time} < {last_t}")
            return False

        # 3. Update tick metrics & price buffer
        self.previous_price[symbol] = self.last_price[symbol] or price
        self.last_price[symbol] = price
        self.tick_count[symbol] += 1
        self.last_tick_timestamp[symbol] = epoch_time

        self.price_buffer[symbol].append(price)
        if len(self.price_buffer[symbol]) > self.max_price_buffer:
            self.price_buffer[symbol].pop(0)

        # Record tick time for ticks/min rate
        now = time.time()
        self.recent_tick_times[symbol].append(now)
        self.recent_tick_times[symbol] = [t for t in self.recent_tick_times[symbol] if (now - t) <= 60.0]

        # 4. Form candles across all timeframes with deterministic UTC boundaries
        for tf, secs in self.TIMEFRAMES_SEC.items():
            boundary = self.get_candle_boundary(epoch_time, secs)
            buf = self.candles_buffer[symbol][tf]

            if not buf:
                # First candle in buffer
                new_candle = Candle(timestamp=boundary, open_price=price, high=price, low=price, close=price, tick_count=1)
                buf.append(new_candle)
            else:
                last_candle = buf[-1]
                if last_candle.timestamp == boundary:
                    # Tick belongs to current active candle
                    last_candle.update_tick(price)
                elif boundary > last_candle.timestamp:
                    # Current active candle has closed
                    last_candle.complete = True
                    # Open new candle
                    new_candle = Candle(timestamp=boundary, open_price=price, high=price, low=price, close=price, tick_count=1)
                    buf.append(new_candle)
                    if len(buf) > self.max_candle_buffer:
                        buf.pop(0)

            # Update readiness based on buffer depth
            if len(buf) >= 20:
                self.readiness[symbol][tf] = TimeframeReadiness.READY
            elif len(buf) > 0:
                self.readiness[symbol][tf] = TimeframeReadiness.WARMING_UP
            else:
                self.readiness[symbol][tf] = TimeframeReadiness.INSUFFICIENT_DATA

        return True

    def get_ticks_per_minute(self, symbol: str) -> float:
        """Return rolling tick frequency per minute for symbol."""
        if symbol not in self.recent_tick_times:
            return 0.0
        now = time.time()
        self.recent_tick_times[symbol] = [t for t in self.recent_tick_times[symbol] if (now - t) <= 60.0]
        return float(len(self.recent_tick_times[symbol]))

    async def preload_historical_candles(
        self,
        symbols: List[str],
        timeframes: Optional[List[str]] = None,
        count: int = 100
    ):
        """Fetch historical candles via Deriv ticks_history API to warm up buffers."""
        target_tfs = timeframes or ["1m", "5m", "15m", "30m", "1h", "4h"]
        logger.info(f"[MARKET] Preloading historical candles for {len(symbols)} symbols across {target_tfs}...")

        for sym in symbols:
            self._init_symbol(sym)
            for tf in target_tfs:
                if tf not in self.TIMEFRAMES_SEC:
                    continue
                secs = self.TIMEFRAMES_SEC[tf]
                try:
                    res = await self.client.request({
                        "ticks_history": sym,
                        "adjust_start_time": 1,
                        "count": count,
                        "end": "latest",
                        "style": "candles",
                        "granularity": secs
                    })

                    if "error" in res:
                        logger.warning(f"[MARKET] Failed to fetch history for {sym} ({tf}): {res['error'].get('message')}")
                        self.readiness[sym][tf] = TimeframeReadiness.INSUFFICIENT_DATA
                        continue

                    candles_list = res.get("candles", [])
                    parsed_candles = []
                    for c in candles_list:
                        candle = Candle(
                            timestamp=c["epoch"],
                            open_price=c["open"],
                            high=c["high"],
                            low=c["low"],
                            close=c["close"],
                            tick_count=1,
                            complete=True
                        )
                        parsed_candles.append(candle)

                    self.candles_buffer[sym][tf] = parsed_candles[-self.max_candle_buffer:]
                    if parsed_candles:
                        self.last_price[sym] = parsed_candles[-1].close
                        self.last_tick_timestamp[sym] = parsed_candles[-1].timestamp

                    if len(parsed_candles) >= 20:
                        self.readiness[sym][tf] = TimeframeReadiness.READY
                    elif len(parsed_candles) > 0:
                        self.readiness[sym][tf] = TimeframeReadiness.WARMING_UP
                    else:
                        self.readiness[sym][tf] = TimeframeReadiness.INSUFFICIENT_DATA

                except Exception as err:
                    logger.error(f"[MARKET] Exception preloading history for {sym} ({tf}): {err}")
                    self.readiness[sym][tf] = TimeframeReadiness.INSUFFICIENT_DATA

        logger.info("[MARKET] Historical candles preloading complete.")

    def get_candles(self, symbol: str, timeframe: str = "1m") -> List[Candle]:
        return self.candles_buffer.get(symbol, {}).get(timeframe, [])

    def get_dataframe(self, symbol: str, timeframe: str = "1m") -> pd.DataFrame:
        candles = self.get_candles(symbol, timeframe)
        if not candles:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "tick_count", "complete"])

        data = [c.to_dict() for c in candles]
        df = pd.DataFrame(data)
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
        return df
