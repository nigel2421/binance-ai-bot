# Binance Crypto AI Multi-Agent Trading Bot

A modular, multi-agent cryptocurrency trading bot designed for Binance Spot & Futures markets.

## Features & Architecture (Stage 1 & Stage 2)

- **Dynamic Market Discovery**: Queries Binance `/exchangeInfo` API at startup to discover active trading pairs, symbol filters (LOT_SIZE, PRICE_FILTER, MIN_NOTIONAL), and precision rules.
- **Async REST & WebSocket Engine**: Built with `aiohttp` and `websockets` for combined ticker/kline streaming (`wss://stream.binance.com:9443/stream?streams=...`).
- **Multi-Timeframe Candles**: Preloads and maintains live sliding OHLCV candle buffers across `1m`, `5m`, `15m`, `30m`, `1h`, `4h`.
- **Sub-Agent Watchers**: Dedicated `CryptoWatcher` per symbol tracking health status (`HEALTHY`, `SCANNING`, `STALE`, `ERROR`), tick counts, regime state, and signal statistics.
- **Safety Defaults**: `DRY_RUN=true` and `LIVE_TRADING=false` by default.

## Project Structure

```
binance-ai-bot/
├── main.py                  # Entrypoint for market discovery & streaming
├── requirements.txt         # Python dependencies
├── .env.example             # Configuration template
├── src/
│   ├── api/
│   │   └── binance_client.py       # REST & WebSocket client
│   ├── market/
│   │   ├── crypto_market_registry.py# Exchange info & discovery
│   │   └── market_data_engine.py   # Multi-tf candle storage & streams
│   ├── monitoring/
│   │   └── watcher_health.py       # Per-symbol sub-agent health watcher
│   └── config.py                   # Environment & settings loader
└── tests/
    ├── test_binance_client.py
    ├── test_market_registry.py
    └── test_market_data_engine.py
```

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and set your API keys:
   ```bash
   BINANCE_API_KEY=your_key_here
   BINANCE_API_SECRET=your_secret_here
   ```

3. Run discovery and market streaming test:
   ```bash
   python main.py
   ```

4. Run unit test suite:
   ```bash
   python -m pytest -v tests/
   ```
