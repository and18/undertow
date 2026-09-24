#!/usr/bin/env python3
"""
generator_contiguity.py — la metrica di contiguita' di honeypot_scope.py (sezione 4),
calcolata sulle richieste agentiche del generatore (harness/load/workload.js).

METRICA (identica a honeypot_scope.py, sezione 4)
  Per ogni «sessione» con almeno 2 richieste, in ordine: coppie di richieste
  consecutive (x, y) in cui entrambe si mappano su (libro, capitolo).
    contigua  stesso libro e |capitolo_y − capitolo_x| = 1 (successivo O precedente)
    ripetuta  stesso libro e stesso capitolo
  contiguita' = coppie contigue / coppie. Il denominatore conta COPPIE, non sessioni.

IPOTESI SUL GENERATORE (dichiarate, non misurate)
  1. «Sessione» dell'honeypot = connessione; qui = VU di k6: ogni VU tiene la propria
     connessione (noConnectionReuse falso) e il proprio stato agSession.
  2. Si considerano solo le richieste agentiche di ogni VU, in ordine: le sessioni del
     generatore (AGENT_SESSION capitoli contigui dalla base) si susseguono una dopo
     l'altra; le richieste di altre classi eseguite dallo stesso VU sono ignorate.
  3. Le iterazioni (λ·measure) sono assegnate ai VU in giro (--assign rr, coda FIFO dei
     VU liberi) oppure a caso (--assign random); VU = preAllocatedVUs di workload.js,
     min(max(ceil(2·RATE), 200), 4000). Ogni iterazione e' agentica con probabilita' β.
  4. Una sola invocazione k6 (la fase di misura): lo stato di sessione parte vuoto.
  5. Indice globale -> (libro, capitolo) come locate() di workload.js, sul vettore
     cumulativo che k6 ha davvero usato: setup_data (ids, cum) registrato nel JSON di k6
     del run (--run, --json), letto con `ssh lab cat`. Il 24 settembre setup_data e'
     risultato identico nei 117 JSON di misura dei 29 run dal 16 al 22 settembre, e
     identico, posizione per posizione, a data/corpus/books.csv (ORDER BY title, 485
     titoli distinti su 495: da solo non garantisce l'ordine fra titoli uguali); con
     --books lo script ripete il confronto.
  Base di sessione: rango r = min(scope−1, floor(scope·u^(1/(1−skew)))),
  base = (r·AGENT_MUL + SEED) mod N, capitoli base, base+1, ... mod N.

SCRIVE
  data/derived/generator_contiguity.csv  (--out): una riga, medie sui semi di coppie,
  contigue, ripetute, quote in %, VU con coppie, sessioni avviate, e i parametri usati.

Uso:
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
ap.add_argument("--rate", type=float, default=95.0, help="λ, req/s (default: run a 12 req/s)")
ap.add_argument("--beta", type=float, default=0.1263)
ap.add_argument("--scope", type=float, default=0.02)
ap.add_argument("--session", type=int, default=3)
ap.add_argument("--skew", type=float, default=0.6)
ap.add_argument("--mul", type=int, default=3266489917, help="AGENT_MUL (separata)")
ap.add_argument("--measure", type=int, default=620)
ap.add_argument("--assign", choices=("rr", "random"), default="rr")
ap.add_argument("--seeds", type=int, default=5)
ap.add_argument("--run", default="tre-20260921-150237", help="run da cui leggere setup_data")
ap.add_argument("--json", default="m-a0.2947-b0.1263-1.json", help="JSON di k6 del run")
ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "derived"
                                     / "generator_contiguity.csv"))
ap.add_argument("--books", default=None,
                help="confronta setup_data con questo CSV (gutenberg_id, n_chapters)")
A = ap.parse_args()


def library():
    """Vettore cumulativo usato da k6: setup_data del JSON di misura del run."""
    out = subprocess.run(["ssh", "lab", f"cat ~/undertow/harness/results/{A.run}/{A.json}"],
                         capture_output=True, text=True, check=True)
    sd = json.loads(out.stdout)["setup_data"]
    ids, cum = [str(i) for i in sd["ids"]], sd["cum"]
    if not ids or cum[-1] != sd["total"]:
        sys.exit(f"setup_data incoerente in {A.run}/{A.json}")
    if A.books:
        with open(A.books, newline="") as f:
            rows = list(csv.DictReader(f))
        bi = [r["gutenberg_id"] for r in rows]
        bc, t = [], 0
        for r in rows:
            t += int(r["n_chapters"])
            bc.append(t)
        diff = [i for i, (x, y) in enumerate(zip(ids, bi)) if x != y]
        print(f"confronto con {A.books}: libri {len(bi)} contro {len(ids)}, posizioni con id "
              f"diverso {len(diff) + abs(len(bi) - len(ids))}, vettore cumulativo "
              f"{'identico' if bc == cum else 'DIVERSO'}")
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
    print(f"corpus {len(ids)} libri, {n} capitoli; λ {A.rate}  β {A.beta}  scope {A.scope}  "
          f"sessione {A.session}  AGENT_MUL {A.mul}  measure {A.measure} s  assegnazione {A.assign}")
    res = [run(s, ids, cum, n) for s in range(1, A.seeds + 1)]
    for s, (p, a, r, c, ss) in enumerate(res, 1):
        print(f"  seme {s}: coppie {p}  contigue {a} ({a / p:.4f})  ripetute {r} ({r / p:.4f})  "
              f"VU con coppie {c}  sessioni avviate {ss}")
    share = [a / p for p, a, *_ in res]
    rshare = [r / p for p, _, r, *_ in res]
    print(f"contiguita' media {statistics.fmean(share):.4f}  "
          f"(min {min(share):.4f}, max {max(share):.4f}, {len(res)} semi)")
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
    print(f"scritto {A.out}")


if __name__ == "__main__":
    main()
