#!/usr/bin/env python3
"""
generator_contiguity.py — the contiguity metric of honeypot_scope.py (section 4),
computed on the agentic requests of the generator (harness/load/workload.js).

METRIC (identical to honeypot_scope.py, section 4)
  For each «session» with at least 2 requests, in order: pairs of consecutive
  requests (x, y) in which both map to (book, chapter).
    contiguous  same book and |chapter_y − chapter_x| = 1 (next OR previous)
    repeated    same book and same chapter
  contiguity = contiguous pairs / pairs. The denominator counts PAIRS, not sessions.

ASSUMPTIONS ON THE GENERATOR (declared, not measured)
  1. Honeypot «session» = connection; here = k6 VU: each VU keeps its own
     connection (noConnectionReuse false) and its own agSession state.
  2. Only the agentic requests of each VU are considered, in order: the generator's
     sessions (AGENT_SESSION contiguous chapters from the base) follow one after
     the other; requests of other classes executed by the same VU are ignored.
  3. The iterations (λ·measure) are assigned to the VUs round-robin (--assign rr, FIFO queue of
     free VUs) or at random (--assign random); VU = preAllocatedVUs of workload.js,
     min(max(ceil(2·RATE), 200), 4000). Each iteration is agentic with probability β.
  4. A single k6 invocation (the measurement phase): the session state starts empty.
  5. Global index -> (book, chapter) as locate() of workload.js, on the cumulative
     vector that k6 really used: setup_data (ids, cum) recorded in the run's k6 JSON
     (--run, --json), read with `ssh lab cat`. On 24 September setup_data turned out
     identical in the 117 measurement JSONs of the 29 runs from 16 to 22 September, and
     identical, position by position, to data/corpus/books.csv (ORDER BY title, 485
     distinct titles out of 495: on its own it does not guarantee the order between equal titles); with
     --books the script repeats the comparison.
  Session base: rank r = min(scope−1, floor(scope·u^(1/(1−skew)))),
  base = (r·AGENT_MUL + SEED) mod N, chapters base, base+1, ... mod N.

WRITES
  data/derived/generator_contiguity.csv  (--out): one row, means over the seeds of pairs,
  contiguous, repeated, shares in %, VUs with pairs, sessions started, and the parameters used.

Usage:
    python3 tools/generator_contiguity.py [--rate 95 --beta 0.1263 --scope 0.02]
"""
import argparse
import bisect
import csv
import json
import math
import random
import statistics
import subprocess
import sys
from pathlib import Path

SEED = 42

ap = argparse.ArgumentParser()
ap.add_argument("--rate", type=float, default=95.0, help="λ, req/s (default: the 12 req/s run)")
ap.add_argument("--beta", type=float, default=0.1263)
ap.add_argument("--scope", type=float, default=0.02)
ap.add_argument("--session", type=int, default=3)
ap.add_argument("--skew", type=float, default=0.6)
ap.add_argument("--mul", type=int, default=3266489917, help="AGENT_MUL (separate)")
ap.add_argument("--measure", type=int, default=620)
ap.add_argument("--assign", choices=("rr", "random"), default="rr")
ap.add_argument("--seeds", type=int, default=5)
ap.add_argument("--run", default="tre-20260921-150237", help="run to read setup_data from")
ap.add_argument("--json", default="m-a0.2947-b0.1263-1.json", help="k6 JSON of the run")
ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "derived"
                                     / "generator_contiguity.csv"))
ap.add_argument("--books", default=None,
                help="compare setup_data with this CSV (gutenberg_id, n_chapters)")
A = ap.parse_args()


def library():
    """Cumulative vector used by k6: setup_data of the run's measurement JSON."""
    out = subprocess.run(["ssh", "lab", f"cat ~/undertow/harness/results/{A.run}/{A.json}"],
                         capture_output=True, text=True, check=True)
    sd = json.loads(out.stdout)["setup_data"]
    ids, cum = [str(i) for i in sd["ids"]], sd["cum"]
    if not ids or cum[-1] != sd["total"]:
        sys.exit(f"setup_data inconsistent in {A.run}/{A.json}")
    if A.books:
        with open(A.books, newline="") as f:
            rows = list(csv.DictReader(f))
        bi = [r["gutenberg_id"] for r in rows]
        bc, t = [], 0
        for r in rows:
            t += int(r["n_chapters"])
            bc.append(t)
        diff = [i for i, (x, y) in enumerate(zip(ids, bi)) if x != y]
        print(f"comparison with {A.books}: books {len(bi)} versus {len(ids)}, positions with different "
              f"id {len(diff) + abs(len(bi) - len(ids))}, cumulative vector "
              f"{'identical' if bc == cum else 'DIFFERENT'}")
    return ids, cum, sd["total"]


def run(seed, ids, cum, n):
    rnd = random.Random(seed)
    vus = min(max(math.ceil(A.rate * 2), 200), 4000)
    scope = max(1, math.floor(n * A.scope))
    state = [None] * vus                      # agSession per VU: [base, left, k]
    seq = [[] for _ in range(vus)]
    for i in range(int(A.rate * A.measure)):
        v = i % vus if A.assign == "rr" else rnd.randrange(vus)
        if rnd.random() >= A.beta:
            continue
        s = state[v]
        if s is None or s[1] <= 0:
            r = min(scope - 1, math.floor(scope * rnd.random() ** (1 / (1 - A.skew))))
            s = state[v] = [(r * A.mul + SEED) % n, A.session, 0]
        s[1] -= 1
        idx = (s[0] + s[2]) % n
        s[2] += 1
        b = bisect.bisect_right(cum, idx)
        seq[v].append((ids[b], idx - (cum[b - 1] if b else 0) + 1))
    pairs = adj = rep = clients = 0
    for q in seq:
        if len(q) < 2:
            continue
        clients += 1
        for x, y in zip(q, q[1:]):
            pairs += 1
            if x[0] == y[0]:
                adj += abs(y[1] - x[1]) == 1
                rep += y[1] == x[1]
    sessions = sum(math.ceil(len(q) / A.session) for q in seq)
    return pairs, adj, rep, clients, sessions


def main():
    ids, cum, n = library()
    print(f"corpus {len(ids)} books, {n} chapters; λ {A.rate}  β {A.beta}  scope {A.scope}  "
          f"session {A.session}  AGENT_MUL {A.mul}  measure {A.measure} s  assignment {A.assign}")
    res = [run(s, ids, cum, n) for s in range(1, A.seeds + 1)]
    for s, (p, a, r, c, ss) in enumerate(res, 1):
        print(f"  seed {s}: pairs {p}  contiguous {a} ({a / p:.4f})  repeated {r} ({r / p:.4f})  "
              f"VUs with pairs {c}  sessions started {ss}")
    share = [a / p for p, a, *_ in res]
    rshare = [r / p for p, _, r, *_ in res]
    print(f"mean contiguity {statistics.fmean(share):.4f}  "
          f"(min {min(share):.4f}, max {max(share):.4f}, {len(res)} seeds)")
    m = lambda i: statistics.fmean(x[i] for x in res)
    with open(A.out, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["pairs", "contiguous", "repeated", "contiguous_pct", "contiguous_pct_min",
                    "contiguous_pct_max", "repeated_pct", "vus_with_pairs", "sessions",
                    "seeds", "rate", "beta", "scope", "session", "agent_mul", "measure_s",
                    "assign", "run"])
        w.writerow([f"{m(0):.0f}", f"{m(1):.0f}", f"{m(2):.0f}",
                    f"{100 * statistics.fmean(share):.2f}", f"{100 * min(share):.2f}",
                    f"{100 * max(share):.2f}", f"{100 * statistics.fmean(rshare):.2f}",
                    f"{m(3):.0f}", f"{m(4):.0f}", len(res), A.rate, A.beta, A.scope,
                    A.session, A.mul, A.measure, A.assign, A.run])
    print(f"written {A.out}")


if __name__ == "__main__":
    main()
