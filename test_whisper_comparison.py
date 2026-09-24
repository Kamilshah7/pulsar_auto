from secrets_loader import get_secret
import os
from groq import Groq

client = Groq(api_key=get_secret("GROQ_API_KEY"))
wpath = 'f:/BB/ETN-SC/pulsar_auto/audio/zencastr-en_5e86398b9f9f8b0015b2f007-00000_79.wav'
with open(wpath, 'rb') as f:
    resp = client.audio.transcriptions.create(
        file=('test.wav', f.read()),
        model='whisper-large-v3',
        response_format='verbose_json',
        timestamp_granularities=['word']
    )

print('Whisper text:', resp.text)
print('\nFirst 8 Whisper words:')
for w in resp.words[:8]:
    print(f"  {w['word']:15s} start={w['start']:.3f} end={w['end']:.3f}")
