"""Round 6 (bundle_026): (1) RANDOM verified boundaries H1/H3 would move -- collateral check before
shipping; (2) H2 clipped at 30ms: its largest verified moves incl. 'proud -> i' + 3 random corrected."""
import glob, html, json, os, random, sys
import soundfile as sf
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import run_gold_bench as RGB
from build_listening import cut, wav_b64, cur, gold
SET = glob.glob(os.path.join(HERE, "gold_sets", "*bundle_026"))[0]
GT = json.load(open(os.path.join(SET, "gt_per_clip.json"), encoding="utf-8")); RGB.AUDIO_DIRS.insert(0, os.path.join(SET, "audio"))
R = [r for r in json.load(open(os.path.join(HERE, "prov_runs", "b026_branches.json"), encoding="utf-8")) if r["gold_gap_ms"] <= 5 and r.get("p_start") is not None]
L = {x["group"][1] + "|" + x["landmark"]: x["offset_ms"] / 1000 for x in json.load(open(os.path.join(HERE, "prov_runs", "loso_v1.json"), encoding="utf-8"))}
o2 = L["case10|1457|raw_w1_end"]
h1 = lambda r: r["p_mid"] - 0.03475
h3 = lambda r: r["p_mid"] - 0.01861
h2 = lambda r: min(cur(r) + 0.030, max(cur(r) - 0.030, r["in_w1_end"] + o2))
leaf = lambda r, k: (r["branch"], r["leaf_line"]) == k
verified = lambda r: r["prov_w1end"] == "verified" and r["prov_w2start"] == "verified" and abs(cur(r) - gold(r)) <= 0.002
corrected = lambda r: r["prov_w1end"] == "human" and r["prov_w2start"] == "human"
rnd = random.Random(66); cache = {}; parts = []; man = []

def sample(sid, r, vers, note):
    fn = GT[r["clip"]]["filename"]
    if fn not in cache:
        a, sr = sf.read(RGB.find_wav(fn)); cache[fn] = (a.mean(1) if a.ndim > 1 else a, sr)
    a, sr = cache[fn]
    pl = "".join(f"<div class='v'><span>{n}</span><audio controls preload='none' src='data:audio/wav;base64,"
                 f"{wav_b64(cut(a, sr, r['w1_start'], b, r['w2_end']), sr)}'></audio></div>" for n, b in vers)
    parts.append(f"<div class='s'><div class='h'><b>{sid}</b> &nbsp; &ldquo;{html.escape(r['w1'])}&rdquo; | "
                 f"&ldquo;{html.escape(r['w2'])}&rdquo;</div><div class='st'>{note}</div>{pl}</div>")
    man.append({"id": sid, "w1": r["w1"], "w2": r["w2"], "note": note})

for fid, name, key, f, n in (("C1", "H1 stop into vowel, compact pipe (only 2 exist; both already approved in round 5)", ("case10", 1451), h1, 6),
                             ("C3", "H3 vowel into stop", ("case7", 1356), h3, 8)):
    pool = [r for r in R if leaf(r, key) and verified(r) and abs(f(r) - cur(r)) > 0.002]
    parts.append(f"<section><h2>{fid} &middot; {name}: your VERIFIED boundaries it moves</h2>"
                 f"<p class='fix'>{len(pool)} verified boundaries move; {min(n, len(pool))} drawn at random</p>")
    for k, r in enumerate(rnd.sample(pool, min(n, len(pool))), 1):
        sample(f"{fid}-{k}", r, [("yours (verified)", gold(r)), ("NEW", f(r))], f"fix moves it {1000 * (f(r) - gold(r)):+.0f}ms")
    parts.append("</section>")

key = ("case10", 1457)
parts.append("<section><h2>H2 again, now clipped at 30ms &middot; stop into vowel</h2><p class='fix'>Its largest moves on your "
             "verified boundaries (incl. &ldquo;proud | i&rdquo;, which was bad at 59ms) and 3 random pairs you corrected</p>")
# Every large move is clipped to exactly 30ms, so a plain sort ties; force in "proud -> i" (the
# pair that failed at 59ms) and fill with the next-largest moves.
cand = sorted([r for r in R if leaf(r, key) and verified(r)], key=lambda r: -abs(h2(r) - cur(r)))
big = [r for r in cand if r["w1"] == "proud"][:1]
big += [r for r in cand if r not in big][:3 - len(big)]
for k, r in enumerate(big, 1):
    sample(f"D2-{k}", r, [("yours (verified)", gold(r)), ("NEW (clip 30)", h2(r))], f"fix moves it {1000 * (h2(r) - gold(r)):+.0f}ms")
for k, r in enumerate(rnd.sample([r for r in R if leaf(r, key) and corrected(r)], 3), 4):
    sample(f"D2-{k}", r, [("old (ours now)", cur(r)), ("NEW (clip 30)", h2(r)), ("yours", gold(r))],
           f"old {1000 * (cur(r) - gold(r)):+.0f}ms from yours, new {1000 * (h2(r) - gold(r)):+.0f}ms")
parts.append("</section>")

tpl = open(os.path.join(HERE, "listening", "fixes_round1.html"), encoding="utf-8").read()
page = (tpl[:tpl.index("<h1>")] + "<h1>Round 6</h1><p class='intro'>C1/C3: random draws of boundaries you <b>verified</b> "
        "that H1/H3 would move &mdash; is NEW still acceptable? D2: H2 limited to 30ms moves. Reply with ids.</p>"
        + "".join(parts) + "</body></html>")
out = os.path.join(HERE, "listening", "fixes_round6.html"); open(out, "w", encoding="utf-8").write(page)
json.dump(man, open(out[:-5] + "_manifest.json", "w", encoding="utf-8"), indent=1)
print(f"wrote {out} ({os.path.getsize(out) / 1e6:.1f} MB, {len(man)} samples)")
for m in man: print(f"  {m['id']:<6}{m['w1']:>12} | {m['w2']:<12} {m['note']}")
