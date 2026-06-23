import httpx
import asyncio

async def fetch():
    try:
        response = await httpx.AsyncClient().get('https://httpbin.org/status/403?apikey=dummy_key_123')
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(f"Error caught: {e}")

asyncio.run(fetch())
