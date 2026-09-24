from pipeline import pipeline
clips = pipeline._match_and_order_clips()
print(f"Matched {len(clips)} clips successfully!")
for c in clips:
    print(f"  Clip {c['index']}: {c['filename']} ({c['duration_sec']:.2f}s, tokens={c['token_count']})")
