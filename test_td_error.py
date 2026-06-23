from twelvedata import TDClient
import asyncio

# Bad API Key
td = TDClient(apikey="invalid_key")

async def test():
    try:
        data = await asyncio.to_thread(lambda: td.symbol_search(symbol="aapl").as_json())
        print(data)
    except Exception as e:
        print(f"Error type: {type(e)}")
        print(f"Error string: {str(e)}")

asyncio.run(test())
