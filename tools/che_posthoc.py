#!/usr/bin/env python3
"""
che_posthoc.py — POST HOC, INTERPRETIVE, NOT PRE-REGISTERED. The agentic marginal of A1
(12 -> 36 agentic req/s) predicted by the characteristic-time approximation (Che et al.
2002; Fagin 1977) for an LRU cache with byte capacity, with the access distribution
of the generator (harness/load/workload.js) and the three classes of the design.

Model, for each configuration (point S12 or S36 at scope 0.02 / 0.06 / 0.20):
  - objects: the 16,954 chapters, footprint = bytes of data/derived/chapter_sizes.csv + H (512),
    capacity C = 134,217,728 bytes (as the simulator validated in phase 1);
  - human, rate (1 - α - β)·λ: rank r = min(floor(N^u), N - 1), u uniform, hence
    P(r = k) = log((k+1)/k) / log N for 1 <= k <= N - 2 and P(r = N - 1) = 1 - log(N-1)/log N;
    object = permute(r) = (r·2654435761 + 42) mod N;
  - agentic, rate β·λ: rank base k with P(k) = ((k+1)/S)^0.4 - (k/S)^0.4 (skew 0.6,
    S = floor(N·scope)), base = (k·3266489917 + 42) mod N (separate mapping); the session
    asks for base, base+1, base+2: each object receives β·λ/3 · the sum of the P(k) of the blocks that
    contain it (distinct chapters: overlapping blocks add up);
  - exhaustive, rate α·λ, one per chapter every P = N/(α·λ) seconds.
  Two versions of the exhaustive class, both reported:
  (A) strict Che (IRM): the exhaustive class is a Poisson process of rate α·λ/N per object;
      for each object μ = human + agentic + exhaustive, hit = 1 - exp(-μT).
  (B) Periodic exhaustive (TRAV_MODE=scen, the measured process): extension of the characteristic
      time to renewal traffic. With μ = human + agentic (Poisson):
      occupancy and hit for the Poisson requests = 1 - exp(-μT)·max(0, 1 - T/P);
      hit for the exhaustive requests = 1 if T >= P, otherwise 1 - exp(-μT).
  T is solved from the capacity equation  sum_j footprint_j · occupancy_j(T) = C  (bisection).
  origin_rps = sum of the miss rates; m = (O(S36) - O(S12)) / 23.9990.

Comparisons: lab with TRAV_MODE=scen (28 and 29 Sep; the rows of points.csv it needs are in
data/derived/lab_reference.csv, series scen) and SCEN LRU simulator
(data/sim/esplorativo-artefatto/reps.csv).

Usage:  python3 tools/che_posthoc.py [--from-backup]
  --from-backup  read points.csv from the author's local copies ~/undertow-backup/lab-2026092*-own
                 instead of data/derived/lab_reference.csv (same values)
"""
import csv
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "sim"))
import fase1  # noqa: E402  (sizes(), POINTS)

N = 16954
C = 134_217_728
H = 512
D_RATE = 35.9975 - 11.9985
SEP, HUM = 3266489917, 2654435761
OUT = ROOT / "data" / "posthoc" / "che_posthoc.csv"
REF = ROOT / "data" / "derived" / "lab_reference.csv"
FROM_BACKUP = "--from-backup" in sys.argv[1:]
LAB = {  # (scope, point) -> run with TRAV_MODE=scen
    ("0.02", "S12"): "lab-20260928-own/results/tre-20260928-150154",
    ("0.02", "S36"): "lab-20260928-own/results/tre-20260928-162206",
    ("0.06", "S12"): "lab-20260929-own/results/tre-20260929-064412",
    ("0.06", "S36"): "lab-20260929-own/results/tre-20260929-080424",
    ("0.20", "S12"): "lab-20260929-own/results/tre-20260929-092436",
    ("0.20", "S36"): "lab-20260929-own/results/tre-20260929-104448",
}
SIM_POINT = {("0.02", "S12"): "S12", ("0.02", "S36"): "S36", ("0.06", "S12"): "S12_006",
             ("0.06", "S36"): "S36_006", ("0.20", "S12"): "S12_020", ("0.20", "S36"): "S36_020"}


def human_rates(rate):
    lam = [0.0] * N
    ln = math.log(N)
    for k in range(1, N - 1):
        lam[(k * HUM + 42) % N] += rate * math.log((k + 1) / k) / ln
    lam[((N - 1) * HUM + 42) % N] += rate * (1 - math.log(N - 1) / ln)
    return lam


def agent_rates(rate, scope, skew=0.6):
    lam = [0.0] * N
    s = max(1, math.floor(N * scope))
    e = 1 - skew
    for k in range(s):
        p = ((k + 1) / s) ** e - (k / s) ** e
        b = (k * SEP + 42) % N
        for off in range(3):
            lam[(b + off) % N] += rate * p / 3
    return lam


def solve(fp, mu, pe, period, model):
    """T from the capacity equation; returns T and the hit functions."""
    def occ(T):
        if model == "A":
            return sum(f * (1 - math.exp(-(m + pe) * T)) for f, m in zip(fp, mu))
        cut = max(0.0, 1 - T / period)
        return sum(f * (1 - math.exp(-m * T) * cut) for f, m in zip(fp, mu))
    lo, hi = 0.0, 1.0
    while occ(hi) < C:
        hi *= 2
        if hi > 1e7:
            return float("inf")
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if occ(mid) < C else (lo, mid)
    return (lo + hi) / 2


def config(scope, pt, sizes, model):
    lam, alpha, beta, _, _ = fase1.POINTS[pt]
    rh, ra, re = (1 - alpha - beta) * lam, beta * lam, alpha * lam
    h, a = human_rates(rh), agent_rates(ra, float(scope))
    pe, period = re / N, N / re
    mu = [x + y for x, y in zip(h, a)]
    fp = [s + H for s in sizes]
    T = solve(fp, mu, pe, period, model)
    miss = [0.0, 0.0, 0.0]      # human, agentic, exhaustive (req/s)
    for j in range(N):
        if model == "A":
            q = math.exp(-(mu[j] + pe) * T)
            qe = q
        else:
            q = math.exp(-mu[j] * T) * max(0.0, 1 - T / period)
            qe = 0.0 if T >= period else math.exp(-mu[j] * T)
        miss[0] += h[j] * q
        miss[1] += a[j] * q
        miss[2] += pe * qe
    ag = [j for j in range(N) if a[j] > 0]
    lt = [a[j] * T for j in ag]
    lt_w = sum(a[j] * a[j] * T for j in ag) / ra
    return {"T": T, "O": sum(miss), "miss_share": (miss[0] / rh, miss[1] / ra, miss[2] / re),
            "agent_objects": len(ag), "lamT_mean": statistics.fmean(lt),
            "lamT_median": statistics.median(lt), "lamT_reqweighted": lt_w}


def lab(scope, pt):
    if FROM_BACKUP:
        rows = list(csv.DictReader(open(Path.home() / "undertow-backup" / LAB[(scope, pt)] / "points.csv")))
    else:
        run = LAB[(scope, pt)].rsplit("/", 1)[1]
        rows = [r for r in csv.DictReader(open(REF)) if r["series"] == "scen" and r["run"] == run]
    o = [float(r["origin_rps"]) for r in rows]
    return (statistics.fmean(o), statistics.stdev(o) / math.sqrt(len(o)),
            tuple(statistics.fmean(1 - float(r[c]) for r in rows) for c in ("h_zipf", "h_agent", "h_trav")))


def sim():
    rows = [r for r in csv.DictReader(l for l in open(ROOT / "data" / "sim" / "esplorativo-artefatto" / "reps.csv")
                                      if not l.startswith("#")) if r["variant"] == "SCEN"]
    return {p: statistics.fmean(float(r["origin_rps"]) for r in rows if r["point"] == p)
            for p in set(SIM_POINT.values())}


def main():
    sizes = fase1.sizes()
    s_sim = sim()
    out = []
    print("POST HOC, INTERPRETIVE, not pre-registered\n")
    for model in ("A", "B"):
        print(f"==== model {model}: " + ("strict Che (all classes IRM)" if model == "A"
                                          else "periodic exhaustive (TRAV_MODE=scen), rest IRM"))
        for scope in ("0.02", "0.06", "0.20"):
            r = {pt: config(scope, pt, sizes, model) for pt in ("S12", "S36")}
            L = {pt: lab(scope, pt) for pt in ("S12", "S36")}
            m_che = (r["S36"]["O"] - r["S12"]["O"]) / D_RATE
            m_lab = (L["S36"][0] - L["S12"][0]) / D_RATE
            m_sim = (s_sim[SIM_POINT[(scope, "S36")]] - s_sim[SIM_POINT[(scope, "S12")]]) / D_RATE
            print(f"  scope {scope}:  m Che {m_che:+.4f}   lab {m_lab:+.4f}   simulator {m_sim:+.4f}")
            for pt in ("S12", "S36"):
                x = r[pt]
                print(f"    {pt}: T {x['T']:7.1f} s  O Che {x['O']:6.2f}  lab {L[pt][0]:6.2f}   "
                      f"miss Che {x['miss_share'][0]:.3f}/{x['miss_share'][1]:.3f}/{x['miss_share'][2]:.3f}"
                      f"  lab {L[pt][2][0]:.3f}/{L[pt][2][1]:.3f}/{L[pt][2][2]:.3f}   "
                      f"agentic objects {x['agent_objects']}  agentic λT mean {x['lamT_mean']:.3f} "
                      f"(median {x['lamT_median']:.3f}, request-weighted {x['lamT_reqweighted']:.3f})")
                out.append([model, scope, pt, f"{x['T']:.3f}", f"{x['O']:.6f}", f"{L[pt][0]:.6f}",
                            *(f"{v:.6f}" for v in x["miss_share"]), *(f"{v:.6f}" for v in L[pt][2]),
                            x["agent_objects"], f"{x['lamT_mean']:.6f}", f"{x['lamT_median']:.6f}",
                            f"{x['lamT_reqweighted']:.6f}", f"{m_che:.6f}", f"{m_lab:.6f}", f"{m_sim:.6f}"])
        print()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as f:
        f.write("# POST HOC, INTERPRETATIVO, non pre-registrato; tools/che_posthoc.py; "
                "docs/RISULTATO-che-posthoc.md\n")
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["model", "scope", "point", "T_s", "origin_che", "origin_lab", "miss_h_che",
                    "miss_a_che", "miss_e_che", "miss_h_lab", "miss_a_lab", "miss_e_lab",
                    "agent_objects", "lamT_agent_mean", "lamT_agent_median",
                    "lamT_agent_reqweighted", "m_che", "m_lab", "m_sim_scen"])
        w.writerows(out)
    print(f"written {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
