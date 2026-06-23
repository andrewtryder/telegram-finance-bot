import re

def redact_api_keys(text: str) -> str:
    """Redacts standard api key query parameters from a string."""
    return re.sub(r'([?&]apikey=)[^&\'\"\s]+', r'\1***REDACTED***', str(text), flags=re.IGNORECASE)

url = "https://api.twelvedata.com/symbol_search?symbol=Apple&apikey=MY_SECRET_KEY_123"
print(redact_api_keys(url))

error_msg = "Error caught: Client error '401 Unauthorized' for url 'https://api.twelvedata.com/symbol_search?symbol=Apple&apikey=MY_SECRET_KEY_123'"
print(redact_api_keys(error_msg))
