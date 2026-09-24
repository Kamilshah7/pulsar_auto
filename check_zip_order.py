import zipfile, json, wave, io, os

z = zipfile.ZipFile('audio/bundle.zip', 'r')
wav_names = [n for n in z.namelist() if n.endswith('.wav')]
print("WAV files in zip in order:")
for idx, name in enumerate(wav_names):
    wdata = z.read(name)
    wf = wave.open(io.BytesIO(wdata), 'rb')
    dur = wf.getnframes() / wf.getframerate()
    print(f"  [{idx}] {name} -> dur={dur:.3f}s")

print("\nClips from clip_list.json in order:")
clip_list = json.load(open('output/clip_list.json', encoding='utf-8'))
for c in clip_list:
    print(f"  [{c['index']}] {c['label']} -> {c['time']}")
