import websocket
import time
import json

headers = [
    "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin: https://app.deriv.com"
]

endpoints = [
    "wss://ws.derivws.com/websockets/v3?app_id=1089",
    "wss://ws.derivws.com/websockets/v3?app_id=61047",
    "wss://ws.binaryws.com/websockets/v3?app_id=1089",
]

for ep in endpoints:
    print(f"Testing {ep} with User-Agent header...")
    try:
        ws = websocket.WebSocket()
        ws.connect(ep, header=headers, timeout=10)
        ws.send(json.dumps({"ping": 1}))
        res = ws.recv()
        print(f"SUCCESS! {ep} -> {res}")
        ws.close()
        break
    except Exception as e:
        print(f"FAILED on {ep}: {e}")
