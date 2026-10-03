"""
trace.py — trace generator: reproduction of harness/load/workload.js as launched by
harness/load/treclassi.sh (docs/PREREG-simulatore-fase1.md, «Generatore»).

One repetition = warm-up (300 s) + measurement (620 s), two separate k6 invocations:
  - iteration i at time i/λ, λ·duration iterations (constant-arrival-rate);
  - class from a single draw u: exhaustive if u < α, agentic if u < α+β, human otherwise;
  - human: permute(min(floor(N^u), N-1)), multiplier 2654435761, SEED 42;
  - agentic: session of AGENT_SESSION contiguous chapters per VU; VU = i mod nVU,
    nVU = min(max(ceil(2λ), 200), 4000); session state empty at the start of the invocation;
  - exhaustive: permuteTrav(offset + TRAV_SKIP + i), i = iterationInTest (all classes);
    TRAV_SKIP = 0 in the warm-up, int(300·λ·α) in the measurement (awk's printf "%d": truncates).
k6's Math.random has no seed: here random.Random(seed). Same distribution, not the sequence.
The integers are exact in Python; in double they are also in k6 (products < 2^53).
"""
import bisect
import csv
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEED = 42
PERM_MUL = 2654435761
TRAV_MUL = 2246822519
WARMUP, MEASURE = 300, 620
HUMAN, AGENT, TRAV = 0, 1, 2
CLASS_NAMES = ("human", "agentic", "exhaustive")


def corpus():
    """(ids, cum): cumulative vector in the order of /library (books.csv)."""
    ids, cum, t = [], [], 0
    with open(ROOT / "data" / "corpus" / "books.csv", newline="") as f:
        for r in csv.DictReader(f):
            ids.append(r["gutenberg_id"])
            t += int(r["n_chapters"])
            cum.append(t)
    return ids, cum


def locate(ids, cum, idx):
    b = bisect.bisect_right(cum, idx)
    return ids[b], idx - (cum[b - 1] if b else 0) + 1


def phase(rnd, n, lam, alpha, beta, scope, agent_mul, duration, trav_skip,
          session=3, skew=0.6):
    """Requests of a k6 invocation: list of (class, chapter index, VU)."""
    iters = int(round(lam * duration))
    nvu = min(max(math.ceil(2 * lam), 200), 4000)
    s_bases = max(1, math.floor(n * scope))
    offset = (SEED * 7919) % n
    tmul = TRAV_MUL % n
    state = [None] * nvu                      # [base, left, k] per VU
    out = []
    expo = 1 / (1 - skew)
    for i in range(iters):
        u = rnd.random()
        if u < alpha:
            idx = (((offset + trav_skip + i) % n) * tmul + SEED * 7919) % n
            out.append((TRAV, idx, -1))
        elif u < alpha + beta:
            v = i % nvu
            s = state[v]
            if s is None or s[1] <= 0:
                r = min(s_bases - 1, math.floor(s_bases * rnd.random() ** expo))
                s = state[v] = [(r * agent_mul + SEED) % n, session, 0]
            s[1] -= 1
            idx = (s[0] + s[2]) % n
            s[2] += 1
            out.append((AGENT, idx, v))
        else:
            r = min(math.floor(n ** rnd.random()), n - 1)
            out.append((HUMAN, (r * PERM_MUL + SEED) % n, -1))
    return out


def repetition(seed, n, lam, alpha, beta, scope, agent_mul):
    """(warm-up, measurement) of a repetition."""
    rnd = random.Random(seed)
    warm = phase(rnd, n, lam, alpha, beta, scope, agent_mul, WARMUP, 0)
    skip = int(WARMUP * lam * alpha)
    meas = phase(rnd, n, lam, alpha, beta, scope, agent_mul, MEASURE, skip)
    return warm, meas


def contiguity(meas, ids, cum):
    """C5 metric on the agentic requests of the measurement, session = VU."""
    seq = {}
    for c, idx, v in meas:
        if c == AGENT:
            seq.setdefault(v, []).append(locate(ids, cum, idx))
    pairs = adj = 0
    for q in seq.values():
        for x, y in zip(q, q[1:]):
            pairs += 1
            adj += x[0] == y[0] and abs(y[1] - x[1]) == 1
    return pairs, adj
