"""
EXPERIMENT (2026-09-27): can a machine "listener" tell the cuts the user accepts by ear from the ones they reject?

Every option the user judged in the listening reviews (bench/review/<round>/answers.jsonl) is rebuilt exactly as the
review tool played it (bench/review/review.html playCut: word 1 = [max(w1_start, t - 0.6 s), t], word 2 = [t,
min(w2_end, t + 0.6 s)], 2 ms fades), each word padded with silence and scored ALONE by the engine's recognizers
(modal_listen.py): the CTC log-probability that the segment is exactly its word -- and that it is the word plus the
next word's first letter / phone (bleed, "thew") or minus its last one (clipped). Then, per junction, every accepted
cut is compared with every rejected one: does the listener prefer the accepted cut? (50 % = no better than chance.)
Choices are made on 026 only; 049 (held out) and old14 are reported as checks.

    python -m aligner2.listen_eval            # remote scoring once (cached in bench/cache/aligner2/listen/), then report
    python -m aligner2.listen_eval --report   # report from the cache
"""
import argparse
import collections
import json
import os
import time

import numpy as np

from aligner2 import ipv4  # noqa: F401  (IPv4 first, see aligner2/ipv4.py)
from aligner2.benchmark import BENCH, REVIEW_ROUNDS, load_sets

OUT = os.path.join(BENCH, "cache", "aligner2", "listen")
RES = os.path.join(OUT, "scores.json")
SR, PAD_S, FADE_S, CTX_S = 16000, 0.25, 0.002, 0.60
SETS = ("026", "049", "old14")


def judged():
    """[(round, answer, public item, private item)] for every answer that is not marked 'disregard'"""
    rows = []
    for r in REVIEW_ROUNDS:
        d = os.path.join(BENCH, "review", r)
        pub = json.load(open(os.path.join(d, "items_public.json")))
        pub = pub if isinstance(pub, dict) else {i["id"]: i for i in pub}
        prv = json.load(open(os.path.join(d, "items_private.json")))
        for line in open(os.path.join(d, "answers.jsonl"), encoding="utf-8"):
            if line.strip():
                a = json.loads(line)
                if "disregard" not in a.get("note", "").lower():
                    rows.append((r, a, pub[a["id"]], prv[a["id"]]))
    return rows


def cuts(a):
    """[(t, ok)] of one answer: the options played plus the user's own cut (ok)"""
    out = [(o["t"], bool(o["ok"])) for o in a["options"].values()]
    if a.get("manual") is not None:
        out.append((float(a["manual"]), True))
    return out


def _seg(x, s, e):
    y = x[int(round(s * SR)):int(round(e * SR))].astype(np.float32).copy()
    f = int(FADE_S * SR)
    if len(y) > 2 * f:
        ramp = np.linspace(0, 1, f, dtype=np.float32)
        y[:f] *= ramp; y[-f:] *= ramp[::-1]
    pad = np.zeros(int(PAD_S * SR), np.float32)
    return np.concatenate([pad, y, pad])


def _hyps(u1, u2):
    """word 1: exact, + next word's first unit (bleed), - its own last unit (clipped); word 2: exact, + previous
    word's last unit (bleed), - its own first unit (clipped)"""
    return ([u1, u1 + u2[:1], u1[:-1] if len(u1) > 1 else []],
            [u2, u1[-1:] + u2, u2[1:] if len(u2) > 1 else []])


def fetch():
    import modal
    from aligner2 import lexical, remote
    from aligner2.signals import load_audio
    rows = judged()
    clips = {(c["set"], int(c["clip"])): c for c in load_sets(SETS)}
    have = json.load(open(RES)) if os.path.exists(RES) else {}
    # the listener app (modal_listen.py): deployed like the engine, through the IPv4-first modal CLI
    import subprocess
    r = subprocess.run(remote.MODAL_CLI + ["deploy", "modal_listen.py"], cwd=remote.ROOT, env=remote._env(),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("deploy modal_listen.py failed: " + (r.stdout + r.stderr)[-800:])
    L = modal.Cls.from_name("aligner2-listen", "Listener")()
    need = sorted({(p["set"], int(p["clip"])) for _, _, _, p in rows})
    remote.log(f"phone units for {len(need)} clips (espeak on the listener)")
    units = dict(zip(need, L.units.remote([[t["text"] for t in clips[k]["tokens"]] for k in need])))
    jobs, keys, seen, audio = [], [], set(), {}
    for rnd, a, pub, prv in rows:
        ck = (prv["set"], int(prv["clip"])); k = int(prv["pair"]); toks = clips[ck]["tokens"]
        if "w1" in pub:
            assert toks[k]["text"] == pub["w1"] and toks[k + 1]["text"] == pub["w2"], (a["id"], toks[k]["text"], pub["w1"])
        if prv["wav"] not in audio:
            audio[prv["wav"]] = load_audio(prv["wav"])
        x = audio[prv["wav"]]
        lu = _hyps(lexical.spell(toks[k]["text"]), lexical.spell(toks[k + 1]["text"]))
        pu = _hyps(units[ck][k], units[ck][k + 1])
        for t, _ in cuts(a):
            s = max(pub["w1_start"], t - CTX_S, pub["win_start"]); e = min(pub["w2_end"], t + CTX_S, pub["win_end"])
            for side, (s0, s1) in enumerate(((s, t), (t, e))):
                key = f"{prv['wav']}|{k}|{side}|{s0:.5f}|{s1:.5f}"
                if key in have or key in seen:
                    continue
                seen.add(key); keys.append(key); jobs.append((_seg(x, s0, s1).tobytes(), {"L": lu[side], "P": pu[side]}))
    remote.log(f"{len(jobs)} word segments to score ({len(have)} cached)")
    t0 = time.time(); B = 50
    try:
        for i, res in enumerate(L.run.map([jobs[j:j + B] for j in range(0, len(jobs), B)]), 1):
            for key, r in zip(keys[(i - 1) * B:i * B], res):
                have[key] = r
            if i % 10 == 0:
                remote.log(f"  {min(i * B, len(jobs))}/{len(jobs)} ({time.time() - t0:.0f}s)")
    finally:
        os.makedirs(OUT, exist_ok=True)
        json.dump(have, open(RES, "w"))
        subprocess.run(remote.MODAL_CLI + ["app", "stop", "--yes", "aligner2-listen"], cwd=remote.ROOT, env=remote._env(),
                       capture_output=True)          # the experiment app: nothing left running or deployed
        remote.log("listener app stopped")
    return have


def score_table(have):
    """{answer id: [(t, ok, {name: score})]}"""
    rows = judged()
    v25 = json.load(open(os.path.join(BENCH, "prov_runs", "aligner2_v25.json")))["grid_preds"][3]
    out = {}
    for rnd, a, pub, prv in rows:
        k = int(prv["pair"]); p = v25.get(f"{prv['set']}|{prv['clip']}")
        ours = (p[k]["end"] + p[k + 1]["start"]) / 2 if p else None
        lst = []
        for t, ok in cuts(a):
            s = max(pub["w1_start"], t - CTX_S, pub["win_start"]); e = min(pub["w2_end"], t + CTX_S, pub["win_end"])
            r1 = have.get(f"{prv['wav']}|{k}|0|{s:.5f}|{t:.5f}"); r2 = have.get(f"{prv['wav']}|{k}|1|{t:.5f}|{e:.5f}")
            if r1 is None or r2 is None:
                continue
            sc = {}
            for m in ("L", "P"):
                (e1, b1, c1), (e2, b2, c2) = r1[m], r2[m]
                sc[f"{m} exact"] = e1 + e2
                alt1 = np.logaddexp(b1, c1 if np.isfinite(c1) else -1e9)   # nan-safe: a 1-unit word has no clipped form
                alt2 = np.logaddexp(b2, c2 if np.isfinite(c2) else -1e9)
                sc[f"{m} margin"] = (e1 - alt1) + (e2 - alt2)
            sc["L+P exact"] = sc["L exact"] + sc["P exact"]
            sc["L+P margin"] = sc["L margin"] + sc["P margin"]
            if ours is not None:
                sc["closer to our cut (baseline)"] = -abs(t - ours)
            lst.append((t, ok, sc))
        out.setdefault(a["id"], []).extend(lst)
    return out


def report(have):
    T = score_table(have)
    names = collections.OrderedDict()
    for lst in T.values():
        for _, _, sc in lst:
            for n in sc:
                names[n] = 1
    print(f"pairwise accuracy: the listener prefers the cut you ACCEPTED over one you REJECTED at the same junction "
          f"(50 % = chance); n = accepted-vs-rejected pairs")
    for s in SETS:
        line = []
        for n in names:
            win = tot = 0.0
            for iid, lst in T.items():
                if not iid.startswith(s + "-"):
                    continue
                acc = [x for x in lst if x[1] and n in x[2]]; rej = [x for x in lst if not x[1] and n in x[2]]
                for _, _, sa in acc:
                    for _, _, sr in rej:
                        tot += 1; win += 1.0 if sa[n] > sr[n] else 0.5 if sa[n] == sr[n] else 0.0
            if tot:
                line.append(f"{n} {win / tot:.1%}")
        print(f"  {s:6} n={int(tot):4}: " + " | ".join(line))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    have = json.load(open(RES)) if args.report else fetch()
    report(have)


if __name__ == "__main__":
    main()
