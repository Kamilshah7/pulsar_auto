"""
Client for the aligner2 GPU engine (modal_aligner2.py, deployed app "aligner2-signals").

    python -m aligner2.remote fill     # compute + cache signals for every benchmark clip on the GPU
    python -m aligner2.remote warm     # keep 1 A10G container always on (~$1.10/h while warm!)
    python -m aligner2.remote cool     # back to on-demand (containers stop 20 s after the last call)
    python -m aligner2.remote ping     # time a round trip (cold vs warm start)

Any change to the engine's code (REMOTE_FILES, modal_aligner2.py) is redeployed automatically before the next call.
"""
import glob
import hashlib
import os
import subprocess
import sys
import time

import numpy as np

APP_NAME, CLS_NAME = "aligner2-signals", "Engine"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAMP = os.path.join(ROOT, "bench", "cache", "aligner2", "deployed.sha")
_OBJ = None
PHONES = {}                       # key -> per-token phone strings from the last align_many
ARPA = {}                         # key -> per-token ARPAbet strings (charsiu) from the last align_many
REMOTE_FILES = ("signals.py", "lexical.py", "segment.py", "phones.py", "fc_align.py", "refine.py")   # the engine's code


def _source_hash():
    h = hashlib.sha1()
    for p in [os.path.join(ROOT, "aligner2", f) for f in REMOTE_FILES] + [os.path.join(ROOT, "modal_aligner2.py")]:
        h.update(open(p, "rb").read())
    return h.hexdigest()


def _env():
    """the modal CLI prints non-ASCII (a check mark); on Windows a piped child defaults to cp1252 and the deploy dies
    with 'charmap' codec can't encode (seen 2026-09-25) -> force UTF-8 in every modal subprocess"""
    return dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def ensure_deployed():
    h = _source_hash()
    if os.path.exists(STAMP) and open(STAMP).read().strip() == h:
        return
    log("source changed -> redeploying GPU engine (deploy output follows)")
    p = subprocess.Popen([sys.executable, "-m", "modal", "deploy", "modal_aligner2.py"], cwd=ROOT, env=_env(),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    for line in p.stdout:
        if "Deprecation" not in line and "set_event_loop" not in line and line.strip():
            enc = getattr(sys.stdout, "encoding", None) or "utf-8"      # the app's console / a log file may be cp1252
            print("    " + line.rstrip().encode(enc, "replace").decode(enc, "replace"), flush=True)
    if p.wait() != 0:
        raise RuntimeError("modal deploy failed (see output above)")
    os.makedirs(os.path.dirname(STAMP), exist_ok=True)
    open(STAMP, "w").write(h)
    stop_containers()
    log("deployed; the first call starts a fresh container that loads the models (~30-60 s)")


def stop_containers(why="so no call reaches old code"):
    """stop every running container of the engine: warm containers from a previous deploy keep serving
    the OLD code otherwise (seen 2026-09-24: calls right after a deploy still ran the previous segment.py);
    production also calls it after each bundle so no idle time is billed"""
    import json
    r = subprocess.run([sys.executable, "-m", "modal", "container", "list", "--json"], cwd=ROOT, env=_env(),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        ids = [c["container_id"] for c in json.loads(r.stdout) if c.get("app_name") == APP_NAME]
    except ValueError:
        ids = []
    for cid in ids:
        subprocess.run([sys.executable, "-m", "modal", "container", "stop", "--yes", cid], cwd=ROOT, env=_env(),
                       capture_output=True)
    log(f"stopped {len(ids)} running engine container(s) {why}")


def _local_code_hash():
    h = hashlib.sha1()
    for f in REMOTE_FILES:
        h.update(open(os.path.join(ROOT, "aligner2", f), "rb").read())
    return h.hexdigest()


def _obj():
    global _OBJ
    ensure_deployed()
    if _OBJ is None:
        import modal
        _OBJ = modal.Cls.from_name(APP_NAME, CLS_NAME)()
        want = _local_code_hash()
        for attempt in range(3):
            got = _OBJ.code_version.remote()
            where = got.split(" @ ")[1] if " @ " in got else "?"
            if got.split(" @ ")[0] == want:
                log(f"engine code verified ({want[:8]}, loaded from {where})")
                break
            log(f"engine is running stale code ({got[:8]} from {where} != local {want[:8]}) -> forcing redeploy")
            if os.path.exists(STAMP):
                os.remove(STAMP)
            ensure_deployed()
            _OBJ = modal.Cls.from_name(APP_NAME, CLS_NAME)()
        else:
            raise RuntimeError("engine still runs stale code after 3 redeploys")
    return _OBJ


def _bytes(x):
    return np.asarray(x, np.float32).tobytes()


def signals(key, audio):
    return _obj().signals.remote(key, _bytes(audio), True)


def ensure_signals(clips):
    """clips: [(key, wav_path)] -> computes (on the GPU) the ones the volume does not have yet"""
    from aligner2.signals import load_audio
    keys = [k for k, _ in clips]
    log(f"asking the engine which of {len(keys)} clips need signals (starts a container if none is warm)")
    miss = set(_obj().missing.remote(keys))
    log(f"{len(miss)} clips need signals")
    todo = [(k, _bytes(load_audio(p)), False) for k, p in clips if k in miss]
    if not todo:                          # Modal's starmap never returns on an empty input
        return 0
    t0 = time.time()
    for i, r in enumerate(_obj().signals.starmap(todo, order_outputs=False), 1):
        log(f"signals {i}/{len(todo)}  ({time.time() - t0:.0f}s)")
    return len(todo)


def align_many(items, grid):
    """items: [(key, texts)] -> {key: [preds for each grid setting]}"""
    out = {}
    t0 = time.time()
    log(f"aligning {len(items)} clips x {len(grid)} settings")
    for i, r in enumerate(_obj().align.starmap([(k, t, grid) for k, t in items], order_outputs=False), 1):
        out[r["key"]] = r["preds"]
        PHONES[r["key"]] = r.get("phones"); ARPA[r["key"]] = r.get("arpabet")
        log(f"aligned {i}/{len(items)}  ({time.time() - t0:.0f}s)")
    return out


def set_warm(on):
    _obj().update_autoscaler(min_containers=1 if on else 0)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ping"
    if cmd == "fill":
        from aligner2.benchmark import load_sets
        from aligner2.signals import clip_key
        C = load_sets()
        t = time.time(); n = ensure_signals([(clip_key(c["wav"]), c["wav"]) for c in C])
        print(f"{n} clips computed on the GPU ({time.time() - t:.0f}s)")
    elif cmd in ("warm", "cool"):
        set_warm(cmd == "warm")
        print(f"min_containers = {1 if cmd == 'warm' else 0}")
    elif cmd == "ping":
        for i in range(2):
            t = time.time(); _obj().ping.remote(); print(f"ping {i + 1}: {time.time() - t:.1f}s")
