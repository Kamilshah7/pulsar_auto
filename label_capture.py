"""
Saves label captures from the Pulsar Label Capture extension (pulsar_label_capture/) -- see
aligner2/PERFECTION_WORKFLOW.md. app.py exposes it as POST /api/capture-labels.

    kind "current": the labels the CURRENT SYSTEM generates (our aligner's output, injected by the pipeline), saved
                    right after the injection, before the user touches anything. NOT the platform's prelabels.
    kind "golden":  those same labels after the user perfected every boundary by ear

Each save goes to bench/label_captures/<bundle>/<kind>_<timestamp>.json and is copied to <kind>.json (the latest);
nothing is ever overwritten except that "latest" copy. The bundle comes from the editor URL (?bundle=...), falling back
to output/current_bundle.txt. If it is the bundle the app is working on, its audio + pipeline files are archived right
away (pipeline.archive_bundle), so the clips are saved together with the labels.
"""
import datetime
import json
import os
import re
from urllib.parse import parse_qs, urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAPTURE_DIR = os.path.join(BASE_DIR, "bench", "label_captures")
KINDS = ("current", "golden")
MOVE_TOL = 0.0005          # the editor stores whole ms: anything beyond half a ms was moved


def safe_name(bundle):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", bundle)[:120]           # same as pipeline.archive_bundle


def wav_of(token_id):
    m = re.match(r"t_(.+\.wav)_\d+$", str(token_id or ""))
    return m.group(1) if m else None


def bundle_from(url, output_dir):
    q = parse_qs(urlparse(url or "").query)
    if q.get("bundle"):
        return q["bundle"][0], "editor URL"
    p = os.path.join(output_dir, "current_bundle.txt")
    if os.path.exists(p):
        b = open(p, encoding="utf-8").read().strip()
        if b:
            return b, "current_bundle.txt (the editor URL had no ?bundle=)"
    return None, None


NOTES_DIR = os.path.join(BASE_DIR, "bench", "edit_notes")
NOTES_TEMPLATE = """# Change notes for {bundle}
# One line per change:   clip # | word before | word after | what I did | why
#   clip # as the editor numbers it (first clip = 1); (start) / (end) for a clip's first word start / last word end
#   e.g.   3 | the | rabbit | cut 6 ms earlier | "the" kept the r of rabbit
#          5 | that | is | end of "that" later ~8 ms | t release belongs to "that"
# Lines starting with # are free comments.

"""


def _rel(path):
    try:
        return os.path.relpath(path, BASE_DIR)
    except ValueError:                                # another drive
        return path


def ensure_notes(bundle):
    """bench/edit_notes/<short id>.txt, created with the format header on the first capture of a bundle"""
    import sys
    sys.path.insert(0, BASE_DIR)
    from aligner2.captures import short_id
    path = os.path.join(NOTES_DIR, short_id(bundle) + ".txt")
    if os.path.exists(path):
        return path, False
    os.makedirs(NOTES_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(NOTES_TEMPLATE.format(bundle=bundle))
    return path, True


def diff(start, gold):
    """boundary differences between two token lists, matched by token id"""
    S = {t.get("id"): t for t in start if t.get("id") is not None}
    G = {t.get("id"): t for t in gold if t.get("id") is not None}
    moved_s = moved_e = 0
    for i, g in G.items():
        s = S.get(i)
        if s is None:
            continue
        moved_s += abs(float(g["start"]) - float(s["start"])) > MOVE_TOL
        moved_e += abs(float(g["end"]) - float(s["end"])) > MOVE_TOL
    return {"boundaries_moved": moved_s + moved_e, "starts_moved": moved_s, "ends_moved": moved_e,
            "tokens_added": len(set(G) - set(S)), "tokens_removed": len(set(S) - set(G)),
            "text_changed": sum(1 for i, g in G.items() if i in S and (g.get("text") or "") != (S[i].get("text") or ""))}


def save_capture(payload, output_dir, audio_dir, archive_dir, archive_fn=None, log=print):
    kind = str(payload.get("kind", "")).lower()
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
    tokens = payload.get("tokens")
    if not isinstance(tokens, list) or not tokens:
        raise ValueError("no tokens in the capture")
    bundle, bundle_src = bundle_from(payload.get("url"), output_dir)
    if not bundle:
        raise ValueError("cannot tell which bundle this is (no ?bundle= in the editor URL and no current_bundle.txt)")
    safe = safe_name(bundle)

    # the clips: WAV names from the token ids, per clipIndex
    clip_wav = {}
    for t in tokens:
        w = wav_of(t.get("id"))
        if w is not None and t.get("clipIndex") is not None:
            clip_wav.setdefault(int(t["clipIndex"]), w)
    wavs = sorted(set(clip_wav.values()))
    clip_idx = sorted({int(t["clipIndex"]) for t in tokens if t.get("clipIndex") is not None})

    # make sure the audio is saved with the labels: archive now if this is the bundle the app is working on
    archived_now = False
    cur = os.path.join(output_dir, "current_bundle.txt")
    if archive_fn and os.path.exists(cur) and open(cur, encoding="utf-8").read().strip() == bundle:
        archived_now = bool(archive_fn(bundle, log))
    arch_audio = os.path.join(archive_dir, safe, "audio")
    found = [w for w in wavs if os.path.exists(os.path.join(arch_audio, w)) or os.path.exists(os.path.join(audio_dir, w))]

    # what it differs from: golden vs the CURRENT capture (or what we injected); current vs what we injected
    out_dir = os.path.join(CAPTURE_DIR, safe)
    injected = os.path.join(archive_dir, safe, "pipeline", "injected_tokens.json")
    ref_path, ref_name = None, None
    if kind == "golden" and os.path.exists(os.path.join(out_dir, "current.json")):
        ref_path, ref_name = os.path.join(out_dir, "current.json"), "your CURRENT capture"
    elif os.path.exists(injected):
        ref_path, ref_name = injected, "the injected labels"
    cmp = None
    if ref_path:
        ref = json.load(open(ref_path, encoding="utf-8"))
        cmp = diff(ref["tokens"] if isinstance(ref, dict) else ref, tokens)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(out_dir, exist_ok=True)
    rec = {"kind": kind, "bundle": bundle, "bundle_source": bundle_src, "url": payload.get("url"),
           "saved_at": datetime.datetime.now().isoformat(timespec="seconds"), "extracted_at": payload.get("extracted_at"),
           "clip_wav": {str(k): v for k, v in sorted(clip_wav.items())}, "clips_dom": payload.get("clips", []),
           "compared_to": ref_name, "diff": cmp, "tokens": tokens}
    path = os.path.join(out_dir, f"{kind}_{ts}.json")
    n = 2
    while os.path.exists(path):                       # two saves within one second: never overwrite
        path = os.path.join(out_dir, f"{kind}_{ts}_{n}.json"); n += 1
    for p in (path, os.path.join(out_dir, f"{kind}.json")):
        with open(p, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=1)
    notes_file, notes_created = ensure_notes(bundle)
    summary = {"ok": True, "kind": kind, "bundle": bundle, "bundle_source": bundle_src, "tokens": len(tokens),
               "clips": len(clip_idx), "wavs": len(wavs), "wavs_found": len(found), "archived_now": archived_now,
               "compared_to": ref_name, "diff": cmp, "file": path,
               "notes_file": _rel(notes_file), "notes_created": notes_created}
    log(f"[capture] {kind.upper()} {bundle}: {len(tokens)} tokens, {len(clip_idx)} clips, audio {len(found)}/{len(wavs)}"
        + (f"; vs {ref_name}: {cmp['boundaries_moved']} boundaries moved, {cmp['tokens_added']} added, "
           f"{cmp['tokens_removed']} removed" if cmp else "") + f" -> {path}")
    return summary


if __name__ == "__main__":                 # python label_capture.py import <downloaded capture .json> [...]
    import sys
    if len(sys.argv) < 3 or sys.argv[1] != "import":
        sys.exit("usage: python label_capture.py import <pulsar_current_....json | pulsar_golden_....json> [...]")
    sys.path.insert(0, BASE_DIR)
    from pipeline import ARCHIVE_DIR, AUDIO_DIR, OUTPUT_DIR, archive_bundle
    for f in sys.argv[2:]:
        save_capture(json.load(open(f, encoding="utf-8")), OUTPUT_DIR, AUDIO_DIR, ARCHIVE_DIR, archive_fn=archive_bundle)
