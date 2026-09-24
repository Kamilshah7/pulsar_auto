import json
import os
import re
import sys

sys.path.insert(0, ".")
from pipeline import GROQ_API_KEY
from groq import Groq

from transcript_reconciler import build_full_prompt, load_clip_texts

MODEL = sys.argv[1] if len(sys.argv) > 1 else "openai/gpt-oss-120b"

clips = load_clip_texts()
prompt = build_full_prompt(clips)

client = Groq(api_key=GROQ_API_KEY)
resp = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": prompt}],
    temperature=0.1,
    max_completion_tokens=8000,
    reasoning_effort="low",
)
choice = resp.choices[0]
raw = choice.message.content
print("finish_reason:", choice.finish_reason)
print("reasoning:", getattr(choice.message, "reasoning", None))
print("=== RAW RESPONSE (first 2000 chars) ===")
print(repr(raw[:2000]) if raw else raw)

m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
cleaned = m.group(1).strip() if m else raw.strip()
try:
    parsed = json.loads(cleaned)
except Exception as e:
    print("FAILED TO PARSE:", e)
    sys.exit(1)

out_path = os.path.join("output", "reconciled_transcript.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(parsed, f, indent=2)
print(f"\nWrote {out_path}: {len(parsed)} clips")
for k, v in list(parsed.items())[:3]:
    print(k, v[:15])
