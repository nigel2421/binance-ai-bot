import asyncio
import websockets
import ssl
import json

async def test_async_ws():
    ssl_context = ssl.create_default_context()
    
    url = "wss://ws.derivws.com/websockets/v3?app_id=1089"
    print(f"Connecting with async websockets to {url}...")
    try:
        async with websockets.connect(url, ssl=ssl_context) as ws:
            print("CONNECTED ASYNC WEBSOCKET SUCCESS!")
            await ws.send(json.dumps({"ping": 1}))
            res = await ws.recv()
            print("RECV:", res)
    except Exception as e:
        print("ASYNC WEBSOCKET FAILED:", type(e), e)

if __name__ == "__main__":
    asyncio.run(test_async_ws())
