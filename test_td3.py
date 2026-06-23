from twelvedata import TDClient
import asyncio
td = TDClient(apikey="dummy")

async def test():
    print(td.symbol_search(symbol="AAPL").as_json())

asyncio.run(test())
