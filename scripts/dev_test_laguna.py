import os
import json
import openai
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("OPENCODE_ZEN_API_KEY")

client = openai.OpenAI(base_url="https://opencode.ai/zen/v1", api_key=api_key)

system_prompt = """You are an expert news analyst. Analyze the following content item and score its importance/quality from 0.0 to 10.0.
Output JSON only with fields:
{
  "score": float (0-10),
  "reason": "short explanation",
  "summary": "one sentence summary",
  "tags": ["tag1", "tag2"]
}
"""

user_prompt = """Title: Qwen3.8-27B Hybrid IQ4_XS quantization for 16GB gang
Content: A Reddit post shares a GGUF IQ4_XS hybrid quantization of a Qwen3.8-27B model tailored to fit 16GB VRAM.
"""

res = client.chat.completions.create(
    model="laguna-s-2.1-free",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    temperature=0.1,
    max_tokens=300,
)

print("Laguna S 2.1 response:")
print(res.choices[0].message.content)
try:
    parsed = json.loads(res.choices[0].message.content.strip("```json").strip("```"))
    print("Parsed JSON successfully:", parsed)
except Exception as e:
    print("JSON parse error:", e)
