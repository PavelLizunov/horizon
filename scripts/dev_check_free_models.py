import os
import openai
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("OPENCODE_ZEN_API_KEY")

free_models = [
    "deepseek-v4-flash-free",
    "mimo-v2.5-free",
    "hy3-free",
    "nemotron-3-ultra-free",
    "nemotron-3.5-lightning-free",
    "laguna-s-2.1-free",
]

client = openai.OpenAI(base_url="https://opencode.ai/zen/v1", api_key=api_key)

print("Testing all free models:")
for m in free_models:
    try:
        res = client.chat.completions.create(
            model=m,
            messages=[{"role": "user", "content": "Respond with OK"}],
            max_tokens=10,
        )
        print(f"  [AVAILABLE] {m}: {res.choices[0].message.content.strip()}")
    except Exception as e:
        print(f"  [FAILED] {m}: {e}")
