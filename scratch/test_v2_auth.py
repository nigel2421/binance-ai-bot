import asyncio
import httpx
import websocket
import json

API_BASE = "https://api.derivws.com"
APP_ID = "33R2Z6MTElnIWrId8aH3m"
PAT_TOKEN = "pat_40dfbb868f06483af060f5454e21784bf0eab55275b943ec9f7f64ce3f758fbb"

async def test_v2_flow():
    headers = {
        "Authorization": f"Bearer {PAT_TOKEN}",
        "Deriv-App-ID": APP_ID,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    
    print("1. Listing accounts from https://api.derivws.com/trading/v1/options/accounts ...")
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(f"{API_BASE}/trading/v1/options/accounts", headers=headers)
        print("   HTTP Status:", r.status_code)
        accounts_data = r.json()
        print("   Accounts Data:", accounts_data)
        
        accounts = accounts_data if isinstance(accounts_data, list) else accounts_data.get("data", [])
        if not accounts:
            print("   No accounts found!")
            return
            
        acc = accounts[0]
        acc_id = acc.get("account_id") or acc.get("loginid") or acc.get("id")
        print(f"\n2. Requesting OTP WS URL for account {acc_id} ...")
        
        otp_url = f"{API_BASE}/trading/v1/options/accounts/{acc_id}/otp"
        r_otp = await client.post(otp_url, headers=headers)
        print("   OTP HTTP Status:", r_otp.status_code)
        otp_data = r_otp.json()
        print("   OTP Response:", otp_data)
        
        ws_url = otp_data.get("data", {}).get("url") or otp_data.get("url")
        if ws_url:
            if ws_url.startswith("https://"):
                ws_url = "wss://" + ws_url[len("https://"):]
            print(f"\n3. Connecting to OTP WebSocket URL: {ws_url} ...")
            
            def on_open(ws):
                print("   WS OPENED! Sending ping...")
                ws.send(json.dumps({"ping": 1}))
                
            def on_message(ws, msg):
                print("   WS RECV:", msg)
                ws.close()
                
            def on_error(ws, err):
                print("   WS ERROR:", err)
                
            ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message, on_error=on_error)
            ws.run_forever()

if __name__ == "__main__":
    asyncio.run(test_v2_flow())
