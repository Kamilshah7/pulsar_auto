import json, os

OUTPUT_DIR = 'f:/BB/ETN-SC/pulsar_auto/output'
AUDIO_DIR = 'f:/BB/ETN-SC/pulsar_auto/audio'

clips = json.load(open(os.path.join(OUTPUT_DIR, 'ordered_clips.json'), encoding='utf-8'))
groq_data = json.load(open(os.path.join(OUTPUT_DIR, 'groq_transcriptions.json'), encoding='utf-8'))
groq_map = {g['clip_index']: g for g in groq_data}

comparisons = []
for clip in clips:
    idx = clip['index']
    fname = clip['filename']
    g_info = groq_map.get(idx, {'text': '', 'words': []})
    json_name = fname.replace('.wav', '.json')
    json_path = os.path.join(AUDIO_DIR, json_name)

    pre_words = []
    if os.path.exists(json_path):
        with open(json_path, encoding='utf-8') as jf:
            jd = json.load(jf)
            pre_words = [s.get('refTranscript', s.get('text', '')) for s in jd.get('segments', [])]

    comp = {
        'clip_index': idx,
        'clip_id': clip['id'],
        'filename': fname,
        'pre_label_word_count': len(pre_words),
        'pre_label_text': ' '.join(pre_words),
        'groq_word_count': len(g_info.get('words', [])),
        'groq_text': g_info.get('text', ''),
        'groq_words_with_timing': [
            {'word': w['word'], 'start': round(w['start'], 3), 'end': round(w['end'], 3)}
            for w in g_info.get('words', [])
        ]
    }
    comparisons.append(comp)

with open(os.path.join(OUTPUT_DIR, 'clip_comparisons.json'), 'w', encoding='utf-8') as f:
    json.dump(comparisons, f, indent=2)

lines = ['=== CLIPS TO PROCESS ===\n']
for c in comparisons:
    lines.append(f"--- CLIP {c['clip_index']} ({c['filename']}) ---")
    lines.append(f"Pre-label Draft:\n{c['pre_label_text']}\n")
    lines.append(f"Groq Whisper Transcript:\n{c['groq_text']}\n")
    lines.append('Groq Word Timestamps (seconds):')
    words_str = ', '.join(f"{w['word']} [{w['start']:.2f}-{w['end']:.2f}]" for w in c['groq_words_with_timing'])
    lines.append(f"{words_str}\n")
    lines.append('=' * 60 + '\n')

input_payload = '\n'.join(lines)
with open(os.path.join(OUTPUT_DIR, 'pulsar_llm_input.txt'), 'w', encoding='utf-8') as f:
    f.write(input_payload)

print('Updated clip_comparisons.json and pulsar_llm_input.txt successfully!')
