import os
import openai
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("OPENCODE_ZEN_API_KEY")

client = openai.OpenAI(base_url="https://opencode.ai/zen/v1", api_key=api_key)

for m in ["nemotron-3-ultra-free", "nemotron-3.5-lightning-free", "laguna-s-2.1-free"]:
    try:
        res = client.chat.completions.create(
            model=m,
            messages=[
                {"role": "system", "content": "You are an assistant. Return only valid JSON: {\"score\": 8.0, \"summary\": \"test\"}"},
                {"role": "user", "content": "Score this article about python release"}
            ],
            temperature=0.1,
            max_tokens=150,
        )
        print(f"[{m}] JSON output:\n{res.choices[0].message.content}\n")
    except Exception as e:
        print(f"[{m}] Error: {e}")
