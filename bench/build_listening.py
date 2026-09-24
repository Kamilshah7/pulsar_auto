"""
Build a self-contained local HTML page of listening samples for candidate boundary fixes.

For each fix: 2 random human-CORRECTED pairs (old / new / yours) and 2 human-ACCEPTED pairs
the fix would shift (median shift and LARGEST shift = worst case) (yours / new).
Each clip plays word 1, 300 ms of silence, word 2, so the cut is audible.
Audio is embedded as base64 WAV; nothing is uploaded anywhere.
"""
import base64
import html
import io
import json
import os
import random
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_gold_bench as RGB  # noqa: E402

N_CORRECTED = 2  # corrected pairs per fix; small leaves can set this high to hear every pair


def cur(r):
    return (r["pred_w1end"] + r["pred_w2start"]) / 2


def gold(r):
    return (r["gold_w1end"] + r["gold_w2start"]) / 2


def rms_rise(win_ms):
    def f(r, audio, sr, rms):
        a = max(0, int((r["p_start"] - 0.060) * sr)); b = min(len(rms), int((r["p_end"] + 0.020) * sr))
        w = int(win_ms / 1000 * sr); x = 20 * np.log10(rms[a:b] + 1e-6)
        return (a + int(np.argmax(x[w:] - x[:-w])) + w // 2) / sr if len(x) > w else cur(r)
    return f


FIXES = [
    ("F1", "default fallback (pipe midpoint)", ("case14", 1571), "move to pipe start", lambda r, *a: r["p_start"]),
    ("F2", "nasal into vowel", ("case10", 1393), "halfway to pipe start", lambda r, *a: (cur(r) + r["p_start"]) / 2),
    ("F3", "quiet-valley minimum (largest leaf)", ("case11", 1410), "halfway to pipe start", lambda r, *a: (cur(r) + r["p_start"]) / 2),
    ("F4", "stop into vowel (dip + 15ms)", ("case10", 1404), "steepest energy rise (vowel onset)", rms_rise(20)),
    ("F5", "velar stop into vowel, compact pipe", ("case10", 1370), "steepest energy rise (vowel onset)", rms_rise(10)),
    ("F6", "stop onset after vowel", ("case7", 1332), "halfway to pipe start", lambda r, *a: (cur(r) + r["p_start"]) / 2),
]


def wav_b64(x, sr):
    buf = io.BytesIO()
    sf.write(buf, np.clip(x, -1, 1), sr, format="WAV", subtype="PCM_16")
    return base64.b64encode(buf.getvalue()).decode()


def cut(audio, sr, w1_start, bnd, w2_end, cap=0.6, gap=0.3, fade_ms=2):
    a = max(w1_start, bnd - cap); b = min(w2_end, bnd + cap)
    p1 = audio[int(a * sr):int(bnd * sr)].copy(); p2 = audio[int(bnd * sr):int(b * sr)].copy()
    f = int(fade_ms / 1000 * sr)
    for p in (p1, p2):
        if len(p) > 2 * f:
            p[:f] *= np.linspace(0, 1, f); p[-f:] *= np.linspace(1, 0, f)
    return np.concatenate([p1, np.zeros(int(gap * sr)), p2])


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    gt = json.load(open(os.path.join(args.set, "gt_per_clip.json"), encoding="utf-8"))
    RGB.AUDIO_DIRS.insert(0, os.path.join(args.set, "audio"))
    rows = [r for r in json.load(open(args.rows, encoding="utf-8")) if r["gold_gap_ms"] <= 5 and r.get("p_start") is not None]
    cache = {}

    def load(fn):
        if fn not in cache:
            a, sr = sf.read(RGB.find_wav(fn)); a = a.mean(1) if a.ndim > 1 else a
            w = max(1, int(sr * 0.002)); c = np.cumsum(np.pad(a.astype(float) ** 2, (0, w)))
            cache[fn] = (a, sr, np.sqrt(np.maximum((c[w:] - c[:-w]) / w, 0)))
        return cache[fn]

    rnd = random.Random(args.seed)
    parts, manifest = [], []
    for fid, leaf_desc, key, fix_desc, fn_ in FIXES:
        R = [r for r in rows if (r["branch"], r["leaf_line"]) == key]
        fixed = [r for r in R if r["prov_w1end"] == "human" and r["prov_w2start"] == "human"]
        kept = [r for r in R if r["prov_w1end"] != "human" and r["prov_w2start"] != "human"]
        new = {}
        for r in R:
            a, sr, rms = load(gt[r["clip"]]["filename"]); new[id(r)] = fn_(r, a, sr, rms)
        samples = [("corrected", r) for r in rnd.sample(fixed, min(N_CORRECTED, len(fixed)))]
        # Collateral = accepted boundaries where ours currently MATCHES yours (<=2ms) that the fix
        # moves. Accepted pairs where ours already differs (our current run uses your final text,
        # the injection used the LLM text) would test the wrong thing. Ranked by the fix's own move.
        shifted = sorted([r for r in kept if abs(cur(r) - gold(r)) * 1000 <= 2 and abs(new[id(r)] - cur(r)) * 1000 > 2],
                         key=lambda r: abs(new[id(r)] - cur(r)))
        if len(shifted) >= 2:
            samples += [("accepted", shifted[(len(shifted) - 1) // 2]), ("accepted", shifted[-1])]
        elif shifted:
            samples += [("accepted", shifted[0])]
        parts.append(f'<section><h2>{fid} &middot; {html.escape(leaf_desc)}</h2>'
                     f'<p class="fix">Fix: <b>{html.escape(fix_desc)}</b></p>')
        for k, (kind, r) in enumerate(samples, 1):
            sid = f"{fid}-{chr(96 + k)}"
            a, sr, _ = load(gt[r["clip"]]["filename"])
            b_old, b_new, b_gold = cur(r), new[id(r)], gold(r)
            vers = ([("old (ours now)", b_old), ("NEW (fix)", b_new), ("yours", b_gold)] if kind == "corrected"
                    else [("yours (you accepted this)", b_gold), ("NEW (fix)", b_new)])
            label = ("you corrected this one" if kind == "corrected" else
                     ("accepted by you, fix moves it " + ("(largest shift)" if k == len(samples) and sum(1 for x in samples if x[0] == "accepted") == 2 else "(median shift)")))
            stats = (f"old is {1000 * (b_old - b_gold):+.0f}ms from yours, new is {1000 * (b_new - b_gold):+.0f}ms"
                     if kind == "corrected" else f"fix moves your boundary {1000 * (b_new - b_gold):+.0f}ms")
            players = "".join(
                f'<div class="v"><span>{html.escape(n)}</span>'
                f'<audio controls preload="none" src="data:audio/wav;base64,{wav_b64(cut(a, sr, r["w1_start"], b, r["w2_end"]), sr)}"></audio></div>'
                for n, b in vers)
            parts.append(f'<div class="s"><div class="h"><b>{sid}</b> &nbsp; &ldquo;{html.escape(r["w1"])}&rdquo; | '
                         f'&ldquo;{html.escape(r["w2"])}&rdquo; &nbsp;<span class="k {kind}">{label}</span></div>'
                         f'<div class="st">clip {r["clip"]} @ {b_gold:.3f}s &middot; {stats}</div>{players}</div>')
            manifest.append({"id": sid, "fix": fid, "kind": kind, "clip": r["clip"], "pair": r["i"], "w1": r["w1"],
                             "w2": r["w2"], "old": b_old, "new": b_new, "gold": b_gold})
        parts.append("</section>")

    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Boundary Fix Samples</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{{--bg:#fbfaf8;--fg:#1d1c1a;--mut:#6b6862;--card:#fff;--bd:#e6e2dc;--acc:#b5532c;--ok:#2f7d5b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#1a1917;--fg:#ecebe8;--mut:#a3a09a;--card:#232220;--bd:#34322f;--acc:#e08a63;--ok:#6fc49b}}}}
:root[data-theme="dark"]{{--bg:#1a1917;--fg:#ecebe8;--mut:#a3a09a;--card:#232220;--bd:#34322f;--acc:#e08a63;--ok:#6fc49b}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:860px;padding:24px 16px}}
h1{{font-size:22px;margin:0 0 6px}} h2{{font-size:17px;margin:28px 0 4px}} .fix{{color:var(--mut);margin:0 0 10px}}
.intro{{color:var(--mut)}} .s{{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:12px 14px;margin:10px 0}}
.h{{font-size:15px}} .st{{color:var(--mut);font-size:13px;margin:2px 0 8px}}
.k{{font-size:12px;padding:2px 8px;border-radius:99px;border:1px solid var(--bd)}} .k.corrected{{color:var(--ok)}} .k.accepted{{color:var(--acc)}}
.v{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:4px 0}} .v span{{min-width:190px;font-size:13px}}
audio{{height:34px;max-width:100%}}
</style></head><body>
<h1>Boundary fix samples</h1>
<p class="intro">Each player plays <b>word 1</b>, 300&nbsp;ms of silence, then <b>word 2</b>, cut at that version's boundary.
Listen for word 1 ending cleanly (no start of word 2 left on it) and word 2 starting cleanly (nothing missing).
<b>Green</b> tags are pairs you corrected: is NEW acceptable? <b>Orange</b> tags are pairs you accepted that the fix moves:
is NEW still acceptable? Reply with ids, e.g. &ldquo;F1-a ok, F1-c no&rdquo;.</p>
{''.join(parts)}
</body></html>"""
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    open(args.out, "w", encoding="utf-8").write(page)
    json.dump(manifest, open(os.path.splitext(args.out)[0] + "_manifest.json", "w", encoding="utf-8"), indent=1)
    print(f"wrote {args.out} ({os.path.getsize(args.out) / 1e6:.1f} MB, {len(manifest)} samples)")


if __name__ == "__main__":
    main()
