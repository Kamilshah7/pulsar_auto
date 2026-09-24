"""
Production word aligner: aligner2 = the coarse aligner (v16) + the rule stage (aligner2/refine.py), run on the
Modal GPU engine (modal_aligner2.py, app "aligner2-signals"). Drop-in for forced_aligner.ForcedAligner in
pipeline.py: `align(wav_path, words, **ignored) -> [{"text", "start", "end", "score"}]`, times in seconds from
the clip start.

Benchmark (bench/prov_runs/aligner2_v17.*, same engine and setting):
  MAE ms          v16    + rules   | human-moved boundaries: v16 -> + rules
  009 + 026       21.8   17.5      |  28.9 -> 22.7
  049 held-out    24.9   19.9      |  28.7 -> 22.9
  ear judgments (the user's manual placements, n=182): old production aligner 32.3, v16 27.4, v16 + rules 24.9.

`prefetch([(wav_path, words), ...])` aligns a whole bundle in one parallel engine call; `align` then answers
from that cache. Cost: Modal bills per second only while a container runs; the engine's containers stop 20 s after
the last call (modal_aligner2.SCALEDOWN_S) and prefetch stops them right away when the bundle is done, so a run pays
for its cold start (model load, ~30-60 s) and the processing, never for idle time. If the engine cannot be reached, the old ForcedAligner is used for that clip (logged), so the
pipeline never stops. ALIGNER=forced in the environment selects the old aligner outright.
"""
import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor

from aligner2 import remote
from aligner2.run_bench import GRID

SETTING = GRID[3]                      # v16 + rule stage (refine=True)
assert SETTING.get("refine") is True, "production setting must include the rule stage"


def _off_event_loop(fn, *args):
    """run fn(*args) where no asyncio event loop is running. The app's FastAPI endpoints (async def) call the
    pipeline on the event-loop thread, and Modal refuses its blocking interface there ("You can't
    iter(Function.starmap()) from an async function"): every engine call failed and each clip fell back to the old
    ForcedAligner (seen live 2026-09-24). A worker thread has no running loop, so the blocking calls work."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return fn(*args)                               # plain synchronous caller: call directly
    with ThreadPoolExecutor(1, thread_name_prefix="aligner2-engine") as ex:
        return ex.submit(fn, *args).result()


class Aligner2:
    name = "aligner2 v16 + rules (Modal GPU)"

    def __init__(self, log=print):
        self.log = log
        self._cache = {}
        self._fallback = None

    @staticmethod
    def _key(wav_path, words):
        return os.path.abspath(wav_path), tuple(words)

    def prefetch(self, items):
        """items: [(wav_path, words)] -> aligns every clip not cached yet in one parallel engine call"""
        from aligner2.signals import clip_key
        todo = [(p, list(w)) for p, w in items if w and self._key(p, w) not in self._cache]
        if not todo:
            return
        t0 = time.time()
        keys = [clip_key(p) for p, _ in todo]
        self.log(f"[aligner2] aligning {len(todo)} clips in one parallel engine call")
        res = _off_event_loop(self._engine, keys, todo)
        for k, (p, w) in zip(keys, todo):
            preds = res[k][0]
            if len(preds) != len(w):
                raise RuntimeError(f"aligner2 returned {len(preds)} times for {len(w)} words ({os.path.basename(p)})")
            self._cache[self._key(p, w)] = [{"text": t, "start": float(q["start"]), "end": float(q["end"]), "score": 1.0}
                                            for t, q in zip(w, preds)]
        self.log(f"[aligner2] aligned {len(todo)} clips on the GPU engine ({time.time() - t0:.0f}s)")

    @staticmethod
    def _engine(keys, todo):
        """signals for the clips the engine's volume lacks, then every clip aligned, all in parallel on the GPU"""
        try:
            remote.ensure_signals(list(zip(keys, [p for p, _ in todo])))
            return remote.align_many([(k, w) for k, (_, w) in zip(keys, todo)], [SETTING])
        finally:
            remote.stop_containers("(bundle done: no idle billing)")   # billed per second while a container runs: no idle tail after the bundle

    def align(self, wav_path, words, **ignored):
        """same result shape as ForcedAligner.align; pre-labels / hybrid flags are not used"""
        words = list(words)
        if not words:
            return []
        key = self._key(wav_path, words)
        if key not in self._cache:
            try:
                self.prefetch([(wav_path, words)])
            except Exception as e:                            # engine unreachable -> old aligner for this clip
                self.log(f"[aligner2] engine failed ({e!r}); using the old ForcedAligner for {os.path.basename(wav_path)}")
                return self._old().align(wav_path, words, **ignored)
        return [dict(x) for x in self._cache[key]]

    def _old(self):
        if self._fallback is None:
            from forced_aligner import ForcedAligner
            self._fallback = ForcedAligner()
        return self._fallback


def get_aligner(log=print):
    """the production aligner (ALIGNER=forced selects the old one)"""
    if os.environ.get("ALIGNER", "aligner2").lower() == "forced":
        from forced_aligner import ForcedAligner
        return ForcedAligner()
    return Aligner2(log=log)
