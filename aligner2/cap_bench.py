"""
Captured-bundle benchmark (aligner2/PERFECTION_WORKFLOW.md): the current system on the GOLDEN words of every captured
clip, compared with the GOLDEN times boundary by boundary. Every golden boundary is gold (unchanged ones included).

    python -m aligner2.cap_bench prepare     # once per new capture: ONE engine call along the production path
                                             # (denoiser gate, signals, coarse + production cuts, phone strings) and
                                             # the clips' signals downloaded to bench/cache/aligner2/captures/
    python -m aligner2.cap_bench             # local, free: the rule stage on the cached coarse cuts vs golden
    python -m aligner2.cap_bench --list      # + every boundary that differs (junction class, the rule that placed it)

A boundary MATCHES when it is within 1 ms of golden (the editor stores sub-ms drags; touching words sit 1-2 ms apart in
the user's labels -- a 1 ms difference is not audible). Word-text corrections (CURRENT words -> GOLDEN words) are a
transcript issue, listed separately; the aligner is scored on the golden words.
"""
import argparse
import collections
import json
import os

import numpy as np

from aligner2 import refine as R
from aligner2.benchmark import BENCH
from aligner2.captures import load_captures

CACHE = os.path.join(BENCH, "cache", "aligner2", "captures")
TOL = 0.001


def _meta_path(bundle):
    from label_capture import safe_name
    return os.path.join(CACHE, safe_name(bundle) + ".json")


def prepare(clips):
    """production path on the golden words: denoise + gate, signals, align with GRID[0] (coarse) and GRID[3]
    (production); downloads the signals of the key production would use"""
    from aligner2 import denoise_gate, remote
    from aligner2.run_bench import GRID
    from aligner2.signals import clip_key, load_audio
    os.makedirs(CACHE, exist_ok=True)
    by_bundle = collections.defaultdict(list)
    for c in clips:
        by_bundle[c["bundle"]].append(c)
    try:
        for bundle, cs in by_bundle.items():
            texts = {c["clip"]: [t["text"] for t in c["tokens"]] for c in cs}
            meta_p = _meta_path(bundle)
            if os.path.exists(meta_p):
                old = json.load(open(meta_p, encoding="utf-8"))
                if all(old.get(str(c["clip"]), {}).get("texts") == texts[c["clip"]] for c in cs):
                    remote.log(f"{bundle}: prepared already (golden words unchanged)")
                    continue
            xs = [load_audio(c["wav"]) for c in cs]
            ys = remote.denoise_many(xs)
            keys, orig, den = {}, [], []
            for c, x, y in zip(cs, xs, ys):
                k = clip_key(c["wav"])
                if denoise_gate.use_denoised(x, y):
                    keys[c["clip"]] = f"{k}_dns64"; den.append((f"{k}_dns64", y))
                else:
                    keys[c["clip"]] = k; orig.append((k, c["wav"]))
            if orig:
                remote.ensure_signals(orig)
            if den:
                remote.ensure_signals_audio(den)
            res = remote.align_many([(keys[c["clip"]], texts[c["clip"]]) for c in cs], [GRID[0], GRID[3]])
            meta = {}
            for c in cs:
                k = keys[c["clip"]]
                zp = os.path.join(CACHE, k + ".npz")
                for attempt in range(4):
                    if os.path.exists(zp):
                        break
                    try:
                        # a container that has not reloaded the volume would try to compute the signals from the
                        # empty audio: missing() reloads its view first
                        if remote._obj().missing.remote([k]):
                            raise RuntimeError(f"signals for {k} are not on the volume")
                        z = remote._obj().signals.remote(k, b"", True)
                        np.savez_compressed(zp, **{n: np.asarray(v) for n, v in z.items()})
                    except Exception as e:
                        remote.log(f"download {k}: {e!r} (attempt {attempt + 1})")
                if not os.path.exists(zp):
                    raise RuntimeError(f"could not download the signals of {k}")
                meta[str(c["clip"])] = {"key": k, "denoised": k.endswith("_dns64"), "texts": texts[c["clip"]],
                                        "coarse": res[k][0], "production": res[k][1],
                                        "phones": remote.PHONES.get(k), "arpabet": remote.ARPA.get(k)}
            json.dump(meta, open(meta_p, "w", encoding="utf-8"))
            remote.log(f"{bundle}: prepared {len(cs)} clips ({sum(m['denoised'] for m in meta.values())} denoised)")
    finally:
        remote.stop_containers("(cap_bench prepare done)")


def load_prepared(clips):
    out = []
    metas = {}
    for c in clips:
        mp = _meta_path(c["bundle"])
        if mp not in metas:
            metas[mp] = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
        m = metas[mp].get(str(c["clip"]))
        if not m or m["texts"] != [t["text"] for t in c["tokens"]]:
            continue
        zf = np.load(os.path.join(CACHE, m["key"] + ".npz"))
        out.append((c, m, {k: zf[k] for k in zf.files}))
    return out


def junction(arpa, k):
    from aligner2.micro_eval import junction_type
    return junction_type(arpa, k) or "?"


def run(prep, rules=None):
    """[(clip, meta, preds, trace)] -- the rule stage locally on the engine's coarse cuts"""
    if rules is not None:
        R.RULES.clear(); R.RULES.update(rules)
    out = []
    for c, m, z in prep:
        tr = {}
        p = R.refine(z, m["texts"], m["arpabet"], m["coarse"], tr)
        out.append((c, m, p, tr))
    return out


def boundaries(c, p):
    """[(set, clip, token j, side, gold, ours)] for every golden boundary"""
    out = []
    for j, g in enumerate(c["tokens"]):
        for side in ("start", "end"):
            out.append((c["set"], c["clip"], j, side, g[side], p[j][side]))
    return out


def report(results, listing=False):
    rows = []
    for c, m, p, tr in results:
        for s, ci, j, side, g, o in boundaries(c, p):
            k = j if side == "end" else j - 1                 # the junction this boundary belongs to
            rows.append(dict(set=s, clip=ci, j=j, side=side, gold=g, ours=o, err=(o - g) * 1000,
                             text=c["tokens"][j]["text"], changed=c["tokens"][j][f"{side}_changed"],
                             jtype=junction(m["arpabet"], k) if 0 <= k < len(p) - 1 else ("clip start" if k < 0 else "clip end"),
                             nxt=c["tokens"][k + 1]["text"] if 0 <= k < len(p) - 1 else "",
                             prv=c["tokens"][k]["text"] if 0 <= k < len(p) - 1 else "",
                             rule=str(tr.get(k, "")) if k >= 0 else "", pause=(0 <= k < len(p) - 1 and
                             c["tokens"][k + 1]["start"] - c["tokens"][k]["end"] > 0.010)))
    e = np.abs([r["err"] for r in rows])
    n = len(rows)
    print(f"{n} golden boundaries: MATCH (<= 1 ms) {np.sum(e <= 1)} = {np.mean(e <= 1):.1%} | <= 2 ms {np.mean(e <= 2):.1%} | "
          f"<= 5 {np.mean(e <= 5):.1%} | <= 10 {np.mean(e <= 10):.1%} | <= 20 {np.mean(e <= 20):.1%} | MAE {e.mean():.1f} ms")
    for lab, sel in (("left alone by the user (CURRENT was right)", lambda r: not r["changed"]),
                     ("corrected by the user", lambda r: r["changed"])):
        x = np.abs([r["err"] for r in rows if sel(r)])
        if len(x):
            print(f"   {lab:44} {len(x):5}: match {np.mean(x <= 1):.1%}, <= 10 ms {np.mean(x <= 10):.1%}, MAE {x.mean():.1f}")
    by = collections.defaultdict(list)
    for r in rows:
        by["pause" if r["pause"] else r["jtype"]].append(abs(r["err"]))
    print("   by junction: " + ", ".join(f"{k} {np.mean(np.array(v) <= 1):.0%} of {len(v)}"
                                       for k, v in sorted(by.items(), key=lambda x: -len(x[1]))[:14]))
    if listing:
        for r in sorted(rows, key=lambda r: (r["set"], r["clip"], r["j"], r["side"])):
            if abs(r["err"]) > 1:
                print(f"   {r['set']} clip {r['clip'] + 1:2} j{r['j']:<3} {r['side']:5} [{r['prv']}|{r['nxt']}] {r['jtype']:10} "
                      f"{'PAUSE ' if r['pause'] else ''}ours {r['err']:+6.0f} ms {'(corrected)' if r['changed'] else '(was right)'} :: {r['rule'][:90]}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="run", choices=("run", "prepare"))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--add", default=""); ap.add_argument("--drop", default="")
    args = ap.parse_args()
    clips = load_captures()
    if args.cmd == "prepare":
        prepare(clips)
        return
    prep = load_prepared(clips)
    if len(prep) < len(clips):
        print(f"{len(clips) - len(prep)} captured clips are not prepared (run: python -m aligner2.cap_bench prepare)")
    rules = (set(R.RULES) | {x for x in args.add.split(",") if x}) - {x for x in args.drop.split(",") if x}
    if args.add or args.drop:
        print(f"rules: current {'+ ' + args.add if args.add else ''} {'- ' + args.drop if args.drop else ''}")
    res = run(prep, rules)
    same = sum(all(abs(a[s] - b[s]) < 1e-6 for a, b in zip(p, m["production"]) for s in ("start", "end")) for c, m, p, _ in res)
    print(f"local rule stage == the engine's production cuts on {same} / {len(res)} clips")
    report(res, args.list)


if __name__ == "__main__":
    main()
