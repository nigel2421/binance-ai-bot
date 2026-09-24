import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from src.api.binance_client import BinanceClient

async def fetch():
    c = BinanceClient()
    try:
        info = await c.get_account_info()
        await c.close()
        non_zero = [
            {'asset': b['asset'], 'free': float(b['free']), 'locked': float(b['locked']), 'total': float(b['free']) + float(b['locked'])}
            for b in info.get('balances', [])
            if float(b['free']) > 0 or float(b['locked']) > 0
        ]
        print(f"Account Type: {info.get('accountType')}")
        print(f"Can Trade: {info.get('canTrade')}")
        print(f"Non-zero balances count: {len(non_zero)}")
        for b in non_zero:
            print(f"  {b['asset']:8} Free: {b['free']:12.6f} | Locked: {b['locked']:12.6f} | Total: {b['total']:12.6f}")
    except Exception as e:
        print(f"Error fetching balance: {e}")
        await c.close()

if __name__ == "__main__":
    asyncio.run(fetch())
