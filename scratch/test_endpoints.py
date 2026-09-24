import websocket
import json

endpoints = [
    "wss://ws.binaryws.com/websockets/v3?app_id=1089",
    "wss://ws.derivws.com/websockets/v3?app_id=1089",
    "wss://red.derivws.com/websockets/v3?app_id=1089",
    "wss://blue.derivws.com/websockets/v3?app_id=1089",
    "wss://green.derivws.com/websockets/v3?app_id=1089",
    "wss://ws.deriv.com/websockets/v3?app_id=1089",
]

headers = [
    "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin: https://app.deriv.com"
]

for ep in endpoints:
    print(f"Testing {ep} ...")
    try:
        ws = websocket.WebSocket()
        ws.connect(ep, header=headers, timeout=5)
        ws.send(json.dumps({"ping": 1}))
        res = ws.recv()
        print(f"  SUCCESS! Response: {res[:100]}")
        ws.close()
    except Exception as e:
        print(f"  FAILED: {e}")
