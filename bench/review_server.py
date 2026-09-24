"""
Local server for the interactive boundary review (bench/review/review.html).

    python bench/review_server.py            # http://127.0.0.1:8765
    REVIEW_DIR=bench/review/confirm_ear REVIEW_PORT=8766 python bench/review_server.py   # another round

Serves the page, the public item list, and per-item audio windows sliced on demand from the
frozen gold-set WAVs (nothing leaves this machine). Every submitted answer is appended to
bench/review/answers.jsonl, enriched server-side with what each blind letter actually was
(live aligner, the human's earlier boundary, pipe start, vowel onset, burst end, closure start),
so the listener never sees option identities. Re-submitting an item appends again; the last
answer per item wins.
"""
import io
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
REVIEW = os.path.join(HERE, "review")
ROUND = os.path.abspath(os.environ.get("REVIEW_DIR", REVIEW))  # items + answers of this round; page is shared
PORT = int(os.environ.get("REVIEW_PORT", "8765"))

PUBLIC = json.load(open(os.path.join(ROUND, "items_public.json"), encoding="utf-8"))
PRIVATE = json.load(open(os.path.join(ROUND, "items_private.json"), encoding="utf-8"))
PUB_BY_ID = {p["id"]: p for p in PUBLIC}
ANSWERS = os.path.join(ROUND, "answers.jsonl")
LOCK = threading.Lock()
AUDIO_CACHE = {}


def load_answers():
    out = {}
    if os.path.exists(ANSWERS):
        for line in open(ANSWERS, encoding="utf-8"):
            line = line.strip()
            if line:
                a = json.loads(line)
                out[a["id"]] = a
    return out


def audio_window(iid):
    if iid in AUDIO_CACHE:
        return AUDIO_CACHE[iid]
    pub, prv = PUB_BY_ID[iid], PRIVATE[iid]
    info = sf.info(prv["wav"])
    s0 = max(0, int(pub["win_start"] * info.samplerate))
    s1 = min(info.frames, int(pub["win_end"] * info.samplerate))
    x, sr = sf.read(prv["wav"], start=s0, stop=s1, dtype="float32")
    if x.ndim > 1:
        x = x.mean(1)
    buf = io.BytesIO()
    sf.write(buf, np.clip(x, -1, 1), sr, format="WAV", subtype="PCM_16")
    data = buf.getvalue()
    if len(AUDIO_CACHE) > 300:
        AUDIO_CACHE.clear()
    AUDIO_CACHE[iid] = data
    return data


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # keep the console quiet
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self._send(200, open(os.path.join(REVIEW, "review.html"), encoding="utf-8").read(), "text/html; charset=utf-8")
        if path == "/api/items":
            return self._send(200, PUBLIC)
        if path == "/api/answers":
            with LOCK:
                a = load_answers()
            return self._send(200, {k: {"ok": v["ok"], "manual": v.get("manual"), "note": v.get("note", "")} for k, v in a.items()})
        if path.startswith("/api/audio/") and path.endswith(".wav"):
            iid = path[len("/api/audio/"):-4]
            if iid not in PUB_BY_ID:
                return self._send(404, {"error": "unknown item"})
            return self._send(200, audio_window(iid), "audio/wav")
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/answer":
            return self._send(404, {"error": "not found"})
        try:
            a = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            iid = a["id"]
            prv = PRIVATE[iid]
            ok = {k: bool(v) for k, v in a.get("ok", {}).items() if k in prv["options"]}
            manual = a.get("manual")
            rec = {"id": iid, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "ok": ok,
                   "manual": float(manual) if manual is not None else None, "note": str(a.get("note", ""))[:500],
                   # server-side enrichment: what each blind letter was
                   "set": prv["set"], "kind": prv["kind"], "class": prv["class"], "branch": prv["branch"],
                   "leaf_line": prv["leaf_line"], "gold": prv["gold"], "live": prv["live"], "rule": prv.get("rule"),
                   "options": {k: {"t": m["t"], "cues": m["cues"], "ok": ok.get(k, False)} for k, m in prv["options"].items()}}
            with LOCK:
                with open(ANSWERS, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec) + "\n")
                n = len(load_answers())
            return self._send(200, {"saved": True, "answered": n, "total": len(PUBLIC)})
        except Exception as e:
            return self._send(400, {"error": str(e)})


if __name__ == "__main__":
    print(f"Boundary review: http://127.0.0.1:{PORT}  ({len(PUBLIC)} items, answers -> {ANSWERS})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
