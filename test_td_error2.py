from twelvedata import TDClient
import asyncio

# Bad API Key
td = TDClient(apikey="invalid_key")

async def test():
    try:
        # Some methods fail with bad API keys, let's test a simple quote
        data = await asyncio.to_thread(lambda: td.price(symbol="AAPL").as_json())
        print(data)
    except Exception as e:
        print(f"Error type: {type(e)}")
        print(f"Error string: {str(e)}")

asyncio.run(test())
