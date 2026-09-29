#!/usr/bin/env python3
"""
fig04_data.py — genera data/derived/fig04_overlap.csv (FIG-04, claim A3).

Quattro run primari a scope 0,02, 5 ripetizioni ciascuno, stesso giorno (28 set), traversata
esaustiva in scenario proprio (TRAV_MODE=scen, claims v3.8; docs/RISULTATO-lab-trav-own-20260928.md):
  mappatura condivisa  tre-20260928-134141 (12 req/s), tre-20260928-190230 (36 req/s):
                       AGENT_MUL=2654435761
  mappatura separata   tre-20260928-150154 (12 req/s), tre-20260928-162206 (36 req/s):
                       AGENT_MUL=3266489917
La colonna run dice da quale run viene ogni riga.
Colonne:
  origin_rps / origin_se  media e SE (stdev / sqrt(n)) di origin_rps da points.csv
  agent_hit               media di h_agent da points.csv
  overlap_pct             quota delle basi agentiche che cadono nella testa umana, sul
                          generatore (harness/load/workload.js): basi agentiche
                          (r·AGENT_MUL + SEED) mod N per r < floor(N·scope); testa umana =
                          gli stessi 339 ranghi piu' popolari che zipfRank estrae davvero,
                          cioe' r = 1..339 (floor(N^u) >= 1: il rango 0 non esce mai),
                          mappati con (r·2654435761 + SEED) mod N; N = 16954, SEED = 42
  human_mass_pct          quota del traffico umano che cade sulle basi agentiche, con la
                          distribuzione vera di zipfRank: r = floor(N^u), u uniforme,
                          P(r = k) = log_N(k+1) − log_N(k) per k >= 1, P(0) = 0

Stampa anche, per confronto, l'effetto separata − condivisa con SE combinato e t, e le due
grandezze con le definizioni precedenti (testa = ranghi 0..338, Zipf(1) esatta con 1/(k·H_N)).
Il file e' letto da FIG-04 anche per la didascalia: ci sono anche effect / effect_se / t.
  prev_effect / prev_effect_se / prev_t  stesso effetto nella misura precedente, la replica
                          pre-registrata del 25-26 set con la traversata a indice globale (R7):
                          C12 tre-20260925-213527, S12 tre-20260925-225538,
                          S36 tre-20260926-001550, C36 tre-20260926-025613 (prev_runs). La
                          figura disegna solo i run primari; la misura precedente entra solo
                          nella didascalia.

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
    (12, "shared"): ("tre-20260928-134141", HUMAN_MUL),
    (12, "separated"): ("tre-20260928-150154", SEPARATED_MUL),
    (36, "shared"): ("tre-20260928-190230", HUMAN_MUL),
    (36, "separated"): ("tre-20260928-162206", SEPARATED_MUL),
}
# misura precedente: replica pre-registrata del 25-26 set, traversata globale (R7)
REPLICA = {
    (12, "shared"): "tre-20260925-213527",
    (12, "separated"): "tre-20260925-225538",
    (36, "shared"): "tre-20260926-025613",
    (36, "separated"): "tre-20260926-001550",
}


def bases(mul, ranks=None, n=st.CORPUS, scope=float(st.SCOPE_DEFAULT)):
    k = max(1, math.floor(n * scope))
    return [(r * mul + SEED) % n for r in (ranks if ranks is not None else range(k))]


def overlap(mul, head_from=1):
    """Quota delle basi agentiche nella testa umana di uguale ampiezza (ranghi head_from..)."""
    agent = bases(mul)
    head = set(bases(HUMAN_MUL, range(head_from, head_from + len(agent))))
    return len(head.intersection(agent)) / len(agent)


def _rank_of(n=st.CORPUS):
    return {(r * HUMAN_MUL + SEED) % n: r for r in range(n)}


def human_mass(mul, n=st.CORPUS):
    """Quota del traffico umano sulle basi agentiche, con r = floor(N^u) di zipfRank."""
    rank = _rank_of(n)
    p = lambda k: (math.log(k + 1) - math.log(k)) / math.log(n) if k >= 1 else 0.0
    return sum(p(rank[b]) for b in bases(mul))


def human_mass_exact_zipf(mul, n=st.CORPUS):
    """Definizione precedente: Zipf(1) esatta sui ranghi 0..N−1, P(k) = 1 / ((k+1)·H_N)."""
    rank = _rank_of(n)
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
    res, out = {}, {}
    for (load, mapping), (run, mul) in RUNS.items():
        r = res[(load, mapping)] = read_run(run)
        ov, mass = overlap(mul), human_mass(mul)
        out[(load, mapping)] = [load, mapping, f"{100 * ov:.1f}", f"{100 * mass:.1f}",
                                f"{r['mean']:.3f}", f"{math.sqrt(r['var_mean']):.3f}",
                                f"{r['hit']:.3f}"]
        print(f"  {load} {mapping:9s} {run}  origin {r['mean']:.4f} +/- "
              f"{math.sqrt(r['var_mean']):.4f}  hit agentico {r['hit']:.4f}  (n = {r['n']})")
        print(f"      overlap {100 * ov:.2f}% (testa 0..338: {100 * overlap(mul, 0):.2f}%)  "
              f"massa umana {100 * mass:.2f}% (Zipf(1) esatta: "
              f"{100 * human_mass_exact_zipf(mul):.2f}%)")
    rep = {k: read_run(run) for k, run in REPLICA.items()}
    rows = []
    for load in (12, 36):
        a, b = res[(load, "shared")], res[(load, "separated")]
        d, se = b["mean"] - a["mean"], math.sqrt(a["var_mean"] + b["var_mean"])
        print(f"  effetto a {load} req/s: {d:+.4f} +/- {se:.4f}  t = {d / se:.2f}")
        ra, rb = rep[(load, "shared")], rep[(load, "separated")]
        rd, rse = rb["mean"] - ra["mean"], math.sqrt(ra["var_mean"] + rb["var_mean"])
        print(f"  precedente (globale) a {load} req/s: {rd:+.4f} +/- {rse:.4f}  t = {rd / rse:.2f}")
        prev_runs = f"{REPLICA[(load, 'shared')]} {REPLICA[(load, 'separated')]}"
        for mapping in ("shared", "separated"):
            eff = ([f"{d:.3f}", f"{se:.3f}", f"{d / se:.2f}",
                    f"{rd:.3f}", f"{rse:.3f}", f"{rd / rse:.2f}", prev_runs]
                   if mapping == "separated" else [""] * 7)
            rows.append(out[(load, mapping)] + eff + [RUNS[(load, mapping)][0]])
    with OUT_CSV.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["agent_rps", "mapping", "overlap_pct", "human_mass_pct", "origin_rps",
                    "origin_se", "agent_hit", "effect", "effect_se", "t",
                    "prev_effect", "prev_effect_se", "prev_t", "prev_runs", "run"])
        w.writerows(rows)
    print(f"scritto {OUT_CSV}")


if __name__ == "__main__":
    main()
