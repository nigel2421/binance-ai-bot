import asyncio
import aiohttp

urls = [
    "wss://ws.derivws.com/websockets/v3?app_id=1089&l=EN&brand=deriv",
    "wss://ws.derivws.com/websockets/v3?app_id=36300&l=EN&brand=deriv",
    "wss://ws.derivws.com/websockets/v3?app_id=61047&l=EN&brand=deriv",
    "wss://ws.derivws.com/websockets/v3?app_id=1089&l=EN",
]

async def test_url(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://app.deriv.com"
    }
    print(f"Testing {url}...")
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.ws_connect(url, timeout=5) as ws:
                await ws.send_str('{"ping": 1}')
                msg = await ws.receive()
                print("SUCCESS:", url, msg.data)
                return True
    except Exception as e:
        print("FAILED:", url, e)
        return False

async def main():
    for u in urls:
        if await test_url(u):
            break

if __name__ == "__main__":
    asyncio.run(main())
