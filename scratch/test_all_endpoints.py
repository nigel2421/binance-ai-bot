import websocket
import time
import json
import ssl

endpoints = [
    "wss://ws.derivws.com/websockets/v3?app_id=1089",
    "wss://blue.derivws.com/websockets/v3?app_id=1089",
    "wss://green.derivws.com/websockets/v3?app_id=1089",
    "wss://red.derivws.com/websockets/v3?app_id=1089",
    "wss://ws.binaryws.com/websockets/v3?app_id=1089",
    "wss://ws.derivws.com/websockets/v3?app_id=61047",
    "wss://ws.derivws.com/websockets/v3?app_id=36300",
]

def test_url(url):
    print(f"\nTesting: {url}")
    state = {"connected": False}
    
    def on_open(ws):
        print("  OPENED! Sending ping...")
        state["connected"] = True
        ws.send(json.dumps({"ping": 1}))
        
    def on_message(ws, msg):
        print("  RECV:", msg)
        ws.close()
        
    def on_error(ws, err):
        print("  ERROR:", type(err), err)
        
    ws = websocket.WebSocketApp(
        url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error
    )
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
    return state["connected"]

if __name__ == "__main__":
    for url in endpoints:
        if test_url(url):
            print("  SUCCESS!")
            break
