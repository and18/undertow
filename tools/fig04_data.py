#!/usr/bin/env python3
"""
fig04_data.py — genera data/derived/fig04_overlap.csv (FIG-04, claim A3).

Prima il CSV era scritto a mano. Quattro run a scope 0,02, 5 ripetizioni ciascuno:
  mappatura condivisa  tre-20260920-114026 (12 req/s), -130038 (36 req/s): AGENT_MUL non
                       passato a k6, quindi permutazione di default (registry)
  mappatura separata   tre-20260921-150237 (12 req/s), -162248 (36 req/s):
                       AGENT_MUL=3266489917
Colonne:
  origin_rps / origin_se  media e SE (stdev / sqrt(n)) di origin_rps da points.csv
  agent_hit               media di h_agent da points.csv
  overlap_pct             quota delle basi agentiche che cadono nella testa umana, calcolata
                          sul generatore (harness/load/workload.js): basi agentiche
                          (r·AGENT_MUL + SEED) mod N per i ranghi r < floor(N·scope), testa
                          umana (r·2654435761 + SEED) mod N per gli stessi ranghi;
                          N = 16954, SEED = 42, scope 0,02 (339 basi)

Stampa anche, per confronto con claims.md, l'effetto separata − condivisa con SE combinato
e t di Welch, e la massa Zipf(1) del traffico umano sulle basi agentiche (didascalia).

Il lab resta in sola lettura: solo `ssh lab cat`.

Uso:
    python3 tools/fig04_data.py
"""
import csv
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope_ttest as st  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "derived" / "fig04_overlap.csv"

SEED = 42
HUMAN_MUL = 2654435761         # permute() di workload.js, anche default di AGENT_MUL
SEPARATED_MUL = 3266489917
# (agentica nominale, mappatura) -> (run, moltiplicatore agentico)
RUNS = {
    (12, "shared"): ("tre-20260920-114026", HUMAN_MUL),
    (12, "separated"): ("tre-20260921-150237", SEPARATED_MUL),
    (36, "shared"): ("tre-20260920-130038", HUMAN_MUL),
    (36, "separated"): ("tre-20260921-162248", SEPARATED_MUL),
}


def bases(mul, n=st.CORPUS, scope=float(st.SCOPE_DEFAULT)):
    return [(r * mul + SEED) % n for r in range(max(1, math.floor(n * scope)))]


def overlap(mul):
    head = set(bases(HUMAN_MUL))
    agent = bases(mul)
    return len(head.intersection(agent)) / len(agent)


def human_mass(mul, n=st.CORPUS):
    """Quota di una Zipf(1) esatta sui ranghi umani che cade sulle basi agentiche."""
    rank = {(r * HUMAN_MUL + SEED) % n: r for r in range(n)}
    h = sum(1 / k for k in range(1, n + 1))
    return sum(1 / ((rank[b] + 1) * h) for b in bases(mul))


def read_run(run):
    rows = list(csv.DictReader(st.lab_cat(run, "points.csv").splitlines()))
    if not rows:
        sys.exit(f"points.csv vuoto: {run}")
    o = [float(r["origin_rps"]) for r in rows]
    return {"mean": statistics.fmean(o), "var_mean": statistics.variance(o) / len(o),
            "hit": statistics.fmean(float(r["h_agent"]) for r in rows), "n": len(o)}


def main():
    res, out = {}, []
    for (load, mapping), (run, mul) in RUNS.items():
        r = res[(load, mapping)] = read_run(run)
        ov = overlap(mul)
        out.append([load, mapping, f"{100 * ov:.1f}", f"{r['mean']:.3f}",
                    f"{math.sqrt(r['var_mean']):.3f}", f"{r['hit']:.3f}"])
        print(f"  {load} {mapping:9s} {run}  origin {r['mean']:.4f} +/- "
              f"{math.sqrt(r['var_mean']):.4f}  hit agentico {r['hit']:.4f}  "
              f"overlap {100 * ov:.2f}%  massa umana {100 * human_mass(mul):.2f}%  (n = {r['n']})")
    for load in (12, 36):
        a, b = res[(load, "shared")], res[(load, "separated")]
        d, se = b["mean"] - a["mean"], math.sqrt(a["var_mean"] + b["var_mean"])
        print(f"  effetto a {load} req/s: {d:+.4f} +/- {se:.4f}  t = {d / se:.2f}")
    with OUT_CSV.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["agent_rps", "mapping", "overlap_pct", "origin_rps", "origin_se", "agent_hit"])
        w.writerows(out)
    print(f"scritto {OUT_CSV}")


if __name__ == "__main__":
    main()
