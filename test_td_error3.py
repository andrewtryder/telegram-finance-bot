from twelvedata import TDClient
import asyncio

# Good API Key (dummy), bad query
td = TDClient(apikey="dummy")

async def test():
    try:
        data = await asyncio.to_thread(lambda: td.symbol_search(symbol="this_symbol_does_not_exist_at_all").as_json())
        print(data)
    except Exception as e:
        print(f"Error type: {type(e)}")
        print(f"Error string: {str(e)}")

asyncio.run(test())
