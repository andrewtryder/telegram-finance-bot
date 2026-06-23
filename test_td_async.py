from twelvedata import TDClient
import asyncio
import os

td = TDClient(apikey="dummy")

async def test():
    # Since TDClient is synchronous, we use asyncio.to_thread to make it non-blocking
    try:
        data = await asyncio.to_thread(lambda: td.symbol_search(symbol="aapl").as_json())
        print(data)
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())
