import asyncio
import json
import websockets

async def test_deriv_all_symbols():
    url = "wss://red.derivws.com/websockets/v3?app_id=1089"
    async with websockets.connect(url) as ws:
        # Test active_symbols with landing_company or default
        for req in [
            {"active_symbols": "brief"},
            {"active_symbols": "full"},
            {"active_symbols": "brief", "product_type": "basic"},
            {"active_symbols": "brief", "landing_company": "svg"},
        ]:
            await ws.send(json.dumps(req))
            resp = await ws.recv()
            data = json.loads(resp)
            syms = data.get("active_symbols", [])
            print(f"Req {req} -> Returned {len(syms)} symbols")
            if syms:
                markets = set(s.get("market") for s in syms)
                print(f"  Markets: {markets}")
                crypto = [s for s in syms if "crypto" in str(s.get("market")).lower() or "crypto" in str(s.get("submarket")).lower()]
                print(f"  Crypto count: {len(crypto)}")
                if crypto:
                    for c in crypto[:5]:
                        print(f"    Symbol: {c.get('symbol')} ({c.get('display_name')})")

asyncio.run(test_deriv_all_symbols())
