"""Round-2 listening: RANDOM accepted pairs each fix moves (not median/worst picks), to estimate
what fraction of the ~330 moved accepted boundaries the listener still finds acceptable."""
import html, json, os, random, sys
import numpy as np, soundfile as sf
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import run_gold_bench as RGB
from build_listening import cur, gold, cut, wav_b64

FIXES = [  # (id, description, leaf, fix, n samples) -- exactly what the round-1 candidate ships
    ("R3", "F3 quiet-valley minimum, halfway to pipe start", ("case11", 1410), lambda r: (cur(r) + r["p_start"]) / 2, 8),
    ("R1", "F1 default fallback, toward pipe start, max 20ms", ("case14", 1571), lambda r: max(r["p_start"], cur(r) - 0.020), 6),
    ("R2", "F2 nasal into vowel, halfway to pipe start", ("case10", 1393), lambda r: (cur(r) + r["p_start"]) / 2, 4),
]

def main(rows_p, set_dir, out, seed=11):
    gt = json.load(open(os.path.join(set_dir, "gt_per_clip.json"), encoding="utf-8"))
    RGB.AUDIO_DIRS.insert(0, os.path.join(set_dir, "audio"))
    rows = [r for r in json.load(open(rows_p, encoding="utf-8")) if r["gold_gap_ms"] <= 5 and r.get("p_start") is not None]
    rnd = random.Random(seed); cache = {}; parts = []; manifest = []
    for fid, desc, key, fn_, n in FIXES:
        pool = [r for r in rows if (r["branch"], r["leaf_line"]) == key and r["prov_w1end"] != "human"
                and r["prov_w2start"] != "human" and abs(cur(r) - gold(r)) * 1000 <= 2 and abs(fn_(r) - cur(r)) * 1000 > 2]
        pick = rnd.sample(pool, min(n, len(pool)))
        parts.append(f"<section><h2>{fid} &middot; {html.escape(desc)}</h2><p class='fix'>{len(pool)} accepted pairs move; "
                     f"{len(pick)} drawn at random</p>")
        for k, r in enumerate(pick, 1):
            fn = gt[r["clip"]]["filename"]
            if fn not in cache:
                a, sr = sf.read(RGB.find_wav(fn)); cache[fn] = (a.mean(1) if a.ndim > 1 else a, sr)
            a, sr = cache[fn]; sid = f"{fid}-{k}"; b_new = fn_(r); b_gold = gold(r)
            players = "".join(f"<div class='v'><span>{n_}</span><audio controls preload='none' src='data:audio/wav;base64,"
                              f"{wav_b64(cut(a, sr, r['w1_start'], b, r['w2_end']), sr)}'></audio></div>"
                              for n_, b in (("yours (accepted)", b_gold), ("NEW (fix)", b_new)))
            parts.append(f"<div class='s'><div class='h'><b>{sid}</b> &nbsp; &ldquo;{html.escape(r['w1'])}&rdquo; | "
                         f"&ldquo;{html.escape(r['w2'])}&rdquo;</div><div class='st'>clip {r['clip']} @ {b_gold:.3f}s &middot; "
                         f"fix moves it {1000 * (b_new - b_gold):+.0f}ms</div>{players}</div>")
            manifest.append({"id": sid, "clip": r["clip"], "pair": r["i"], "w1": r["w1"], "w2": r["w2"],
                             "gold": b_gold, "new": b_new})
        parts.append("</section>")
    tpl = open(os.path.join(HERE, "listening", "fixes_round1.html"), encoding="utf-8").read()
    head = tpl[:tpl.index("<h1>")]
    page = (head + "<h1>Round 2: boundaries you accepted that the fixes move</h1><p class='intro'>Random draws, so the "
            "answers estimate how many of the ~330 moved boundaries stay acceptable. Word 1, silence, word 2. For each: "
            "is NEW still acceptable? Reply like &ldquo;R3-1 ok, R3-2 no&rdquo;.</p>" + "".join(parts) + "</body></html>")
    open(out, "w", encoding="utf-8").write(page)
    json.dump(manifest, open(os.path.splitext(out)[0] + "_manifest.json", "w", encoding="utf-8"), indent=1)
    print(f"wrote {out} ({os.path.getsize(out) / 1e6:.1f} MB, {len(manifest)} samples)")

if __name__ == "__main__":
    import glob
    main("bench/prov_runs/b049_branches.json", glob.glob("bench/gold_sets/*bundle_049")[0], "bench/listening/collateral_round2.html")
