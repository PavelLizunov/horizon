import os
import json
import openai
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("OPENCODE_ZEN_API_KEY")

client = openai.OpenAI(base_url="https://opencode.ai/zen/v1", api_key=api_key)

system_prompt = """Ты эксперт-аналитик новостей. Сформируй обогащенный материал на русском языке.
Верни ТОЛЬКО валидный JSON:
{
  "title": "Заголовок на русском",
  "blocks": [
    {
      "id": "background",
      "title": "Контекст",
      "content": "Подробный контекст на русском языке..."
    },
    {
      "id": "impact",
      "title": "Влияние",
      "content": "Подробное влияние на индустрию на русском языке..."
    }
  ]
}
"""

user_prompt = """Материал: Qwen3.8-27B Hybrid IQ4_XS quantization for 16GB gang
Reddit post: GGUF IQ4_XS hybrid quantization of Qwen3.8-27B model to run on 16GB VRAM.
"""

res = client.chat.completions.create(
    model="laguna-s-2.1-free",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    temperature=0.2,
    max_tokens=600,
)

print("Laguna S 2.1 Russian enrichment response:")
print(res.choices[0].message.content)
try:
    text = res.choices[0].message.content.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    parsed = json.loads(text.strip())
    print("Parsed JSON successfully:")
    print("Title:", parsed.get("title"))
    print("Blocks:", len(parsed.get("blocks", [])))
except Exception as e:
    print("JSON parse error:", e)
