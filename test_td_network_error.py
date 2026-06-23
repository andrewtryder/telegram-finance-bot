from twelvedata import TDClient
import asyncio
import requests
import unittest.mock as mock

td = TDClient(apikey="MY_SECRET_API_KEY_12345")

async def test():
    try:
        with mock.patch("requests.get", side_effect=requests.exceptions.ConnectionError("Connection aborted. url='https://api.twelvedata.com/symbol_search?symbol=AAPL&apikey=MY_SECRET_API_KEY_12345'")):
            data = await asyncio.to_thread(lambda: td.symbol_search(symbol="aapl").as_json())
            print(data)
    except Exception as e:
        print(f"Error type: {type(e)}")
        print(f"Error string: {str(e)}")

asyncio.run(test())
