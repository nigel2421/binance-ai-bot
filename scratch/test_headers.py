import websocket
import time
import json

def on_message(ws, message):
    print("RECV:", message)
    ws.close()

def on_error(ws, error):
    print("ERROR:", error)

def on_open(ws):
    print("OPENED!")
    ws.send(json.dumps({"ping": 1}))

headers = [
    "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin: https://app.deriv.com"
]

urls = [
    "wss://ws.derivws.com/websockets/v3?app_id=1089",
    "wss://ws.binaryws.com/websockets/v3?app_id=1089",
    "wss://ws.derivws.com/websockets/v3?app_id=61047",
]

for url in urls:
    print(f"\n--- Testing WebSocketApp with headers on: {url} ---")
    ws = websocket.WebSocketApp(
        url,
        header=headers,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error
    )
    ws.run_forever()
