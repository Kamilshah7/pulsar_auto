"""
Captured golden bundles as benchmark clips (aligner2/PERFECTION_WORKFLOW.md).

Each bundle in bench/label_captures/<bundle>/ with a golden.json becomes one set "cap:<short id>" of clips in the same
shape as aligner2.benchmark.load_sets:
    {set, clip, wav, bundle, tokens: [{text, start, end, start_human, end_human, start_changed, end_changed}],
     start_tokens: [...CURRENT labels of that clip...], notes: [lines of bench/edit_notes/<id>.txt]}

Terms: CURRENT = the labels the current system generated and injected (current.json, else the archived
injected_tokens.json) -- never the platform's prelabels; GOLDEN = those labels after the user perfected them.
EVERY golden boundary is gold (start_human / end_human True): unchanged ones were reviewed and right, changed ones were
corrected (start_changed / end_changed: moved > 0.5 ms from CURRENT, or a token with no CURRENT counterpart).
Times are converted to clip-local seconds: the editor (and injected_tokens.json) uses ONE timeline across the bundle,
clip i spanning [start_sec, end_sec) of the archived ordered_clips.json.

    python -m aligner2.captures            # list the captured bundles and their correction counts
"""
import glob
import json
import os
import re

from aligner2.benchmark import BENCH

CAPTURES = os.path.join(BENCH, "label_captures")
ARCHIVE = os.path.join(BENCH, "bundle_archive")
NOTES = os.path.join(BENCH, "edit_notes")
TOL = 0.0005


def short_id(bundle):
    """'..._b24_bundle_042' -> 'b24_bundle_042', '..._b13_pack_006_2026...' -> 'b13_pack_006' (the last such tag;
    the batch number is kept: bundle numbers repeat across batches)"""
    m = re.findall(r"(?:^|[_-])((?:b\d+_)?(?:bundle|pack)_\d+)", bundle)
    return m[-1] if m else re.sub(r"[^A-Za-z0-9_.-]", "_", bundle)[-40:]


def _tokens(path):
    d = json.load(open(path, encoding="utf-8"))
    return d["tokens"] if isinstance(d, dict) else d


def _notes(bundle):
    sid = short_id(bundle)
    for f in glob.glob(os.path.join(NOTES, "*.txt")):
        stem = os.path.splitext(os.path.basename(f))[0]
        if stem == sid or stem in bundle:
            return [ln.rstrip("\n") for ln in open(f, encoding="utf-8", errors="replace") if ln.strip()]
    return []


def load_captures():
    out = []
    for gpath in sorted(glob.glob(os.path.join(CAPTURES, "*", "golden.json"))):
        d = os.path.dirname(gpath); safe = os.path.basename(d)
        meta = json.load(open(gpath, encoding="utf-8"))
        bundle = meta.get("bundle", safe)
        start_path = os.path.join(d, "current.json")
        if not os.path.exists(start_path):
            start_path = os.path.join(ARCHIVE, safe, "pipeline", "injected_tokens.json")
        start = _tokens(start_path) if os.path.exists(start_path) else []
        gold = meta["tokens"]
        S = {t.get("id"): t for t in start}
        clip_wav = {int(k): v for k, v in (meta.get("clip_wav") or {}).items()}
        for t in start:                                   # fill clip -> wav from the CURRENT ids too
            m = re.match(r"t_(.+\.wav)_\d+$", str(t.get("id") or ""))
            if m and t.get("clipIndex") is not None:
                clip_wav.setdefault(int(t["clipIndex"]), m.group(1))
        notes = _notes(bundle)
        oc_path = os.path.join(ARCHIVE, safe, "pipeline", "ordered_clips.json")
        offset = {int(c["index"]): float(c["start_sec"]) for c in json.load(open(oc_path, encoding="utf-8"))}             if os.path.exists(oc_path) else {}
        for c in (json.load(open(oc_path, encoding="utf-8")) if os.path.exists(oc_path) else []):
            clip_wav.setdefault(int(c["index"]), c["filename"])
        for ci in sorted({int(t["clipIndex"]) for t in gold if t.get("clipIndex") is not None}):
            toks, off = [], offset.get(ci, 0.0)
            for t in sorted((t for t in gold if t.get("clipIndex") == ci), key=lambda t: float(t["start"])):
                s = S.get(t.get("id"))
                toks.append({"text": t.get("text", ""), "start": float(t["start"]) - off, "end": float(t["end"]) - off,
                             "start_human": True, "end_human": True,
                             "start_changed": s is None or abs(float(t["start"]) - float(s["start"])) > TOL,
                             "end_changed": s is None or abs(float(t["end"]) - float(s["end"])) > TOL})
            wav = clip_wav.get(ci)
            wav_path = next((p for p in (os.path.join(ARCHIVE, safe, "audio", wav or ""),) if wav and os.path.exists(p)), None)
            out.append({"set": f"cap:{short_id(bundle)}", "clip": ci, "bundle": bundle, "wav": wav_path, "tokens": toks,
                        "start_tokens": [dict(t, start=float(t["start"]) - off, end=float(t["end"]) - off) for t in
                                         sorted((t for t in start if t.get("clipIndex") == ci), key=lambda t: float(t["start"]))],
                        "offset": off,
                        "notes": notes})
    return out


if __name__ == "__main__":
    C = load_captures()
    by = {}
    for c in C:
        b = by.setdefault(c["set"], {"clips": 0, "bounds": 0, "changed": 0, "no_wav": 0, "notes": len(c["notes"])})
        b["clips"] += 1; b["no_wav"] += c["wav"] is None
        for t in c["tokens"]:
            b["bounds"] += 2; b["changed"] += t["start_changed"] + t["end_changed"]
    for s, b in by.items():
        print(f"{s:16} {b['clips']:3} clips, {b['bounds']:5} boundaries, {b['changed']:4} corrected "
              f"({b['changed'] / max(1, b['bounds']):.0%}), notes {b['notes']} lines" + (f", {b['no_wav']} clips WITHOUT audio" if b["no_wav"] else ""))
    if not by:
        print("no captured golden bundles yet (bench/label_captures/<bundle>/golden.json)")
