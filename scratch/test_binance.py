import sys
import asyncio
import logging
from src.api.binance_client import BinanceClient

logging.basicConfig(level=logging.INFO)

async def main():
    client = BinanceClient()
    try:
        # 1. Fetch Exchange Info
        info = await client.get_exchange_info()
        symbols = info.get("symbols", [])
        print(f"[OK] Binance Exchange Info Connected: Discovered {len(symbols)} active trading pairs.")

        # 2. Fetch Latest Ticker Price for BTCUSDT
        ticker = await client.get_ticker_price("BTCUSDT")
        price = float(ticker['price'])
        print(f"[OK] Binance Ticker API Connected: BTCUSDT Price = ${price:,.2f}")

        # 3. Fetch Historical Klines/Candles for ETHUSDT
        klines = await client.get_klines("ETHUSDT", interval="1m", limit=5)
        latest_close = float(klines[-1][4])
        print(f"[OK] Binance Kline/Candle API Connected: ETHUSDT Latest 1m Close = ${latest_close:,.2f} ({len(klines)} bars returned)")

        print("\nSUMMARY: Binance API is wired and fully functional!")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
