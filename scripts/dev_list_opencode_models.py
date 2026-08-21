import os
import openai
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("OPENCODE_ZEN_API_KEY")

for base_url in ["https://opencode.ai/zen/v1", "https://opencode.ai/zen/go/v1"]:
    client = openai.OpenAI(base_url=base_url, api_key=api_key)
    try:
        models = client.models.list()
        print(f"Models for {base_url}:")
        for m in models.data:
            print(f"  - {m.id}")
    except Exception as e:
        print(f"Error for {base_url}: {e}")
