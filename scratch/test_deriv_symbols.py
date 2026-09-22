import asyncio
import json
import websockets

async def test_deriv_symbols():
    url = "wss://red.derivws.com/websockets/v3?app_id=1089"
    async with websockets.connect(url) as ws:
        # Request active_symbols brief
        req = {"active_symbols": "brief", "product_type": "basic"}
        await ws.send(json.dumps(req))
        resp = await ws.recv()
        data = json.loads(resp)
        symbols = data.get("active_symbols", [])
        
        print(f"Total active_symbols (brief, basic): {len(symbols)}")
        if not symbols:
            req = {"active_symbols": "brief"}
            await ws.send(json.dumps(req))
            resp = await ws.recv()
            data = json.loads(resp)
            symbols = data.get("active_symbols", [])
            print(f"Total active_symbols (brief): {len(symbols)}")

        crypto_syms = [s for s in symbols if str(s.get("market")).lower() == "cryptocurrency" or "crypto" in str(s.get("submarket")).lower()]
        print(f"Cryptocurrency symbols found: {len(crypto_syms)}")
        for cs in crypto_syms[:15]:
            print(f"  Symbol: {cs.get('symbol'):<15} Display: {cs.get('display_name'):<20} Market: {cs.get('market')} Sub: {cs.get('submarket')}")

        # Test candidate symbol names for tick streaming
        candidates = ["BTCUSD", "cryBTCUSD", "ETHUSD", "cryETHUSD"]
        for cand in candidates:
            print(f"\nTesting tick subscription for: {cand}")
            sub_req = {"ticks": cand, "subscribe": 1}
            await ws.send(json.dumps(sub_req))
            sub_resp = await ws.recv()
            print(f"  Sub Response for {cand}: {sub_resp}")
            data_sub = json.loads(sub_resp)
            if "subscription" in data_sub:
                # Wait for 2 ticks to verify continuous stream
                for _ in range(2):
                    msg = await ws.recv()
                    print(f"  Received Tick Update: {msg[:120]}")
                # Unsubscribe
                sub_id = data_sub["subscription"]["id"]
                await ws.send(json.dumps({"forget": sub_id}))

asyncio.run(test_deriv_symbols())
