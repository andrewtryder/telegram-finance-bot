from twelvedata import TDClient
import asyncio
import os

apikey = os.getenv("TWELVEDATA_API_KEY", "dummy_key")
td = TDClient(apikey=apikey)

# Check if twelvedata supports async, or if we need to wrap it
try:
    res = td.symbol_search().with_symbol("AAPL").as_json()
    print(res)
except Exception as e:
    print("Error:", e)
