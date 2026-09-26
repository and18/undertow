"""
trace.py — generatore di tracce: riproduzione di harness/load/workload.js come lo lancia
harness/load/treclassi.sh (docs/PREREG-simulatore-fase1.md, «Generatore»).

Una ripetizione = warm-up (300 s) + misura (620 s), due invocazioni k6 separate:
  - iterazione i al tempo i/λ, λ·durata iterazioni (constant-arrival-rate);
  - classe da un solo sorteggio u: esaustiva se u < α, agentica se u < α+β, umana altrimenti;
  - umana: permute(min(floor(N^u), N-1)), moltiplicatore 2654435761, SEED 42;
  - agentica: sessione di AGENT_SESSION capitoli contigui per VU; VU = i mod nVU,
    nVU = min(max(ceil(2λ), 200), 4000); stato di sessione vuoto a inizio invocazione;
  - esaustiva: permuteTrav(offset + TRAV_SKIP + i), i = iterationInTest (tutte le classi);
    TRAV_SKIP = 0 nel warm-up, int(300·λ·α) nella misura (printf "%d" di awk: tronca).
Math.random di k6 non ha seme: qui random.Random(seme). Stessa distribuzione, non la sequenza.
Gli interi sono esatti in Python; in double lo sono anche in k6 (prodotti < 2^53).
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
    """(ids, cum): vettore cumulativo nell'ordine di /library (books.csv)."""
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
    """Richieste di un'invocazione k6: lista di (classe, indice di capitolo, VU)."""
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
    """(warm-up, misura) di una ripetizione."""
    rnd = random.Random(seed)
    warm = phase(rnd, n, lam, alpha, beta, scope, agent_mul, WARMUP, 0)
    skip = int(WARMUP * lam * alpha)
    meas = phase(rnd, n, lam, alpha, beta, scope, agent_mul, MEASURE, skip)
    return warm, meas


def contiguity(meas, ids, cum):
    """Metrica di C5 sulle richieste agentiche della misura, sessione = VU."""
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
