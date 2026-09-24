import json
import wave
import os

d = json.load(open('f:/BB/ETN-SC/pulsar_auto/output/clip_tokens.json', encoding='utf-8'))
key = list(d.keys())[0]
tokens = d[key]['tokens']

print(f"Sample tokens:")
for i in [0, 1, 2, 76, 77, 107]:
    if i < len(tokens):
        print(f"Token {i}: id={tokens[i]['id']}, text={tokens[i]['text']}, clipIndex={tokens[i].get('clipIndex')}, start={tokens[i]['start']}, end={tokens[i]['end']}")

print("\nFiles in audio/:")
for f in sorted(os.listdir('f:/BB/ETN-SC/pulsar_auto/audio')):
    if f.endswith('.wav'):
        print(" ", f)
