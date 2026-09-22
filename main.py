import asyncio
import logging
import sys
import time

from src.config import config
from src.api.binance_client import BinanceClient
from src.market.crypto_market_registry import BinanceMarketRegistry
from src.market.market_data_engine import BinanceMarketDataEngine
from src.monitoring.watcher_health import CryptoWatcher, WatcherState

# Ensure UTF-8 output formatting for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("BinanceCryptoBot")

async def run_discovery_and_streaming(test_stream_seconds: int = 5):
    print("==================================================")
    print("[+] BINANCE CRYPTO AI MULTI-AGENT TRADING BOT")
    print(f"Mode: DRY_RUN={config.dry_run} | LIVE_TRADING={config.live_trading}")
    print("==================================================")

    client = BinanceClient()
    registry = BinanceMarketRegistry(client=client)
    data_engine = BinanceMarketDataEngine(client=client)

    # 1. Market Discovery
    active_symbols = await registry.discover_markets(quote_asset=config.quote_asset)
    
    # Select top markets to monitor up to config limit
    monitored_symbols = active_symbols[:config.max_markets_to_watch]
    print(f"\n[PHASE 1] Discovered {len(active_symbols)} active Binance markets for {config.quote_asset}.")
    print(f"Selected Top {len(monitored_symbols)} markets for monitoring:")
    for sym in monitored_symbols:
        info = registry.get_symbol_info(sym)
        if info:
            print(f"  • {info.symbol:<10} | Base: {info.base_asset:<6} | Precision P/Q: {info.price_precision}/{info.quantity_precision} | Min Notional: ${info.min_notional:.2f}")

    # 2. Watchers Initialization
    watchers = {sym: CryptoWatcher(sym) for sym in monitored_symbols}

    # 3. Preload Historical Klines
    print(f"\n[PHASE 2] Preloading historical candles across multi-timeframes (1m, 5m, 15m, 1h)...")
    await data_engine.preload_historical_klines(monitored_symbols, intervals=["1m", "5m", "15m", "1h"], limit=50)

    # Update watchers with initial candle prices
    for sym in monitored_symbols:
        df = data_engine.get_dataframe(sym, interval="1m")
        if not df.empty:
            last_close = df.iloc[-1]["close"]
            watchers[sym].update_tick(last_close)
            watchers[sym].update_state(WatcherState.HEALTHY)

    # 4. Stream Live Klines
    print(f"\n[PHASE 3] Starting live WebSocket stream test for {test_stream_seconds} seconds...")

    async def ws_message_handler(msg):
        await data_engine.handle_ws_message(msg)
        if "data" in msg and "k" in msg["data"]:
            k = msg["data"]["k"]
            sym = k["s"]
            price = float(k["c"])
            if sym in watchers:
                watchers[sym].update_tick(price)

    stream_task = asyncio.create_task(
        client.stream_klines(monitored_symbols, ["1m"], ws_message_handler)
    )

    # Let WebSocket receive data for test_stream_seconds
    await asyncio.sleep(test_stream_seconds)

    # Cancel stream and close connection
    stream_task.cancel()
    await client.close()

    # 5. Print Stage 1 & 2 Status Report
    print("\n==================================================")
    print("STAGE 1 & 2 REPORT: WATCHER & MARKET STATUS")
    print("==================================================")
    for sym, watcher in watchers.items():
        candles_1m = len(data_engine.get_candles(sym, "1m"))
        candles_5m = len(data_engine.get_candles(sym, "5m"))
        candles_15m = len(data_engine.get_candles(sym, "15m"))
        summary = watcher.get_summary()
        print(
            f"Symbol: {summary['symbol']:<10} | Status: {summary['state']:<8} | "
            f"Price: ${summary['current_price']:<10.4f} | Ticks: {summary['tick_count']:<3} | "
            f"Candles Buffer (1m/5m/15m): {candles_1m}/{candles_5m}/{candles_15m}"
        )
    print("==================================================\n")

if __name__ == "__main__":
    asyncio.run(run_discovery_and_streaming(test_stream_seconds=5))
