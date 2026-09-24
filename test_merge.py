from secrets_loader import get_secret
import os
import json
from groq import Groq

GROQ_API_KEY = get_secret("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

def merge_texts(pre_text, groq_text):
    if not pre_text:
        return groq_text
    prompt = f"Transcript 1 (Pre-labels): {pre_text}\nTranscript 2 (Whisper): {groq_text}\nMerge them into a single verbatim text. Keep all stutters, false starts, and filler words from Transcript 1, but correct spelling using Transcript 2. Return ONLY the raw merged text string. No quotes, no markdown, no explanation."
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-70b-versatile",
    )
    return chat_completion.choices[0].message.content.strip()

print(merge_texts("i saw it i saw it on hbo when i was like i guess i was it was right when it came out so it wouldn't have been yeah so i was in i was i guess i was in high school yeah anyway and it was uh yeah ha ha ha", "I saw it. I saw it on HBO when I was like, I guess I was, it was right when it came out, so it wouldn't have been yeah, so I was in, I guess I was in high school. Yeah. Anyway, and it was... yeah."))
