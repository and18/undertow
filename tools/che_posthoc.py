#!/usr/bin/env python3
"""
che_posthoc.py — POST HOC, INTERPRETATIVO, NON PRE-REGISTRATO. Il marginale agentico di A1
(12 -> 36 req/s agentiche) previsto dall'approssimazione del tempo caratteristico (Che et al.
2002; Fagin 1977) per una cache LRU a capienza in byte, con la distribuzione degli accessi
del generatore (harness/load/workload.js) e le tre classi del disegno.

Modello, per ogni configurazione (punto S12 o S36 a scope 0,02 / 0,06 / 0,20):
  - oggetti: i 16 954 capitoli, footprint = byte di data/derived/chapter_sizes.csv + H (512),
    capienza C = 134 217 728 byte (come il simulatore validato nella fase 1);
  - umana, rate (1 - α - β)·λ: rango r = min(floor(N^u), N - 1), u uniforme, quindi
    P(r = k) = log((k+1)/k) / log N per 1 <= k <= N - 2 e P(r = N - 1) = 1 - log(N-1)/log N;
    oggetto = permute(r) = (r·2654435761 + 42) mod N;
  - agentica, rate β·λ: base di rango k con P(k) = ((k+1)/S)^0,4 - (k/S)^0,4 (skew 0,6,
    S = floor(N·scope)), base = (k·3266489917 + 42) mod N (mappatura separata); la sessione
    chiede base, base+1, base+2: ogni oggetto riceve β·λ/3 · somma delle P(k) dei blocchi che
    lo contengono (capitoli distinti: i blocchi che si sovrappongono si sommano);
  - esaustiva, rate α·λ, uno per capitolo ogni P = N/(α·λ) secondi.
  Due versioni dell'esaustiva, entrambe riportate:
  (A) Che stretto (IRM): l'esaustiva e' un processo di Poisson di rate α·λ/N per oggetto;
      per ogni oggetto μ = umana + agentica + esaustiva, hit = 1 - exp(-μT).
  (B) Esaustiva periodica (TRAV_MODE=scen, il processo misurato): estensione del tempo
      caratteristico a traffico di rinnovo. Con μ = umana + agentica (Poisson):
      occupazione e hit per le richieste di Poisson = 1 - exp(-μT)·max(0, 1 - T/P);
      hit per le richieste esaustive = 1 se T >= P, altrimenti 1 - exp(-μT).
  T si risolve dall'equazione di capienza  sum_j footprint_j · occupazione_j(T) = C  (bisezione).
  origin_rps = somma dei rate di miss; m = (O(S36) - O(S12)) / 23,9990.

Confronti: lab con TRAV_MODE=scen (28 e 29 set, copie locali ~/undertow-backup/lab-2026092*-own,
lettura diretta dei points.csv, lab spento) e simulatore SCEN LRU
(data/sim/esplorativo-artefatto/reps.csv).

Uso:  python3 tools/che_posthoc.py
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
LAB = {  # (scope, punto) -> run con TRAV_MODE=scen
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
    """T dall'equazione di capienza; restituisce T e le funzioni di hit."""
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
    miss = [0.0, 0.0, 0.0]      # umana, agentica, esaustiva (req/s)
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
    rows = list(csv.DictReader(open(Path.home() / "undertow-backup" / LAB[(scope, pt)] / "points.csv")))
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
    print("POST HOC, INTERPRETATIVO, non pre-registrato\n")
    for model in ("A", "B"):
        print(f"==== modello {model}: " + ("Che stretto (tutte le classi IRM)" if model == "A"
                                          else "esaustiva periodica (TRAV_MODE=scen), resto IRM"))
        for scope in ("0.02", "0.06", "0.20"):
            r = {pt: config(scope, pt, sizes, model) for pt in ("S12", "S36")}
            L = {pt: lab(scope, pt) for pt in ("S12", "S36")}
            m_che = (r["S36"]["O"] - r["S12"]["O"]) / D_RATE
            m_lab = (L["S36"][0] - L["S12"][0]) / D_RATE
            m_sim = (s_sim[SIM_POINT[(scope, "S36")]] - s_sim[SIM_POINT[(scope, "S12")]]) / D_RATE
            print(f"  scope {scope}:  m Che {m_che:+.4f}   lab {m_lab:+.4f}   simulatore {m_sim:+.4f}")
            for pt in ("S12", "S36"):
                x = r[pt]
                print(f"    {pt}: T {x['T']:7.1f} s  O Che {x['O']:6.2f}  lab {L[pt][0]:6.2f}   "
                      f"miss Che {x['miss_share'][0]:.3f}/{x['miss_share'][1]:.3f}/{x['miss_share'][2]:.3f}"
                      f"  lab {L[pt][2][0]:.3f}/{L[pt][2][1]:.3f}/{L[pt][2][2]:.3f}   "
                      f"oggetti agentici {x['agent_objects']}  λT agentico medio {x['lamT_mean']:.3f} "
                      f"(mediana {x['lamT_median']:.3f}, pesato per richiesta {x['lamT_reqweighted']:.3f})")
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
    print(f"scritto {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
