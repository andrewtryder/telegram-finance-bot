from twelvedata import TDClient
td = TDClient(apikey="dummy")
try:
    print(td.symbol_search(symbol="AAPL").as_json())
except Exception as e:
    print(e)
