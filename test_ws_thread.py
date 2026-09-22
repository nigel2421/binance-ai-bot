import json
import time
import websocket

servers = [
    "wss://ws.derivws.com/websockets/v3?app_id=61047",
    "wss://ws.derivws.com/websockets/v3?app_id=36300",
    "wss://ws.derivws.com/websockets/v3?app_id=1089",
    "wss://green.derivws.com/websockets/v3?app_id=1089",
    "wss://red.derivws.com/websockets/v3?app_id=1089",
    "wss://blue.derivws.com/websockets/v3?app_id=1089"
]

def test_server(url):
    print(f"Testing {url}...")
    success = False

    def on_message(ws, msg):
        nonlocal success
        print("SUCCESS Received:", msg)
        success = True
        ws.close()

    def on_error(ws, err):
        print("ERROR:", err)

    def on_open(ws):
        print("Connected! Sending ping...")
        ws.send(json.dumps({"ping": 1}))

    ws = websocket.WebSocketApp(
        url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error
    )
    ws.run_forever()
    return success

if __name__ == "__main__":
    for s in servers:
        if test_server(s):
            break
