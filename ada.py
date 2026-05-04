# test_key.py
from dotenv import load_dotenv
load_dotenv()
import os

api_key = os.getenv("GEMINI_API_KEY")
print(f"API Key found: {api_key is not None}")
if api_key:
    print(f"First 10 chars: {api_key[:10]}...")
    print(f"Length: {len(api_key)}")
else:
    print("ERROR: API Key not loaded from .env")