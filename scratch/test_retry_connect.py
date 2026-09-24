import websocket
import time
import json

endpoints = [
    "wss://ws.derivws.com/websockets/v3?app_id=1089",
    "wss://blue.derivws.com/websockets/v3?app_id=1089",
    "wss://green.derivws.com/websockets/v3?app_id=1089",
    "wss://ws.binaryws.com/websockets/v3?app_id=1089",
]

connected = False
for ep in endpoints:
    print(f"Attempting connection to {ep}...")
    for attempt in range(1, 4):
        try:
            ws = websocket.WebSocket()
            ws.connect(ep, timeout=5)
            ws.send(json.dumps({"ping": 1}))
            res = ws.recv()
            print(f"SUCCESS on {ep} (attempt {attempt}): {res}")
            ws.close()
            connected = True
            break
        except Exception as e:
            print(f"  Attempt {attempt} failed on {ep}: {e}")
            time.sleep(1)
    if connected:
        break
