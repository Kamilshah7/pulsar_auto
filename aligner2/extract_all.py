"""Compute and cache every signal for every benchmark clip:  python -m aligner2.extract_all"""
import sys
import time

from aligner2.benchmark import load_sets
from aligner2.signals import compute

if __name__ == "__main__":
    C = load_sets()
    t0 = time.time()
    for i, c in enumerate(C):
        t = time.time()
        compute(c["wav"])
        print(f"[{i + 1}/{len(C)}] {c['set']}-{c['clip']}  {time.time() - t:.0f}s  (total {time.time() - t0:.0f}s)", flush=True)
    sys.exit(0)
