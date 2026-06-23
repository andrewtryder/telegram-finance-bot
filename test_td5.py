from twelvedata import TDClient
import asyncio
td = TDClient(apikey="dummy")

async def test():
    try:
        print(td.symbol_search(symbol="aapl").as_json())
    except Exception as e:
        print(f"Error type: {type(e)}")
        print(f"Error string: {str(e)}")

asyncio.run(test())
