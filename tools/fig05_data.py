#!/usr/bin/env python3
"""
fig05_data.py — genera data/derived/fig05_accounting.csv (FIG-05, claim B2, A9).

Prima il CSV era scritto a mano, con miss arrotondati a 3 decimali e rate nominali
(12 / 24 / 55 / 28 req/s). Ora dalle medie non arrotondate e dai rate configurati.

Tre run a scope 0,02, 5 ripetizioni ciascuno:
  0 req/s agentici   tre-20260920-102015 (β = 0; anteriore a env.txt: λ = 83 come
                     ricostruito in tools/net_agentic.py dai conteggi per classe dei JSON
                     di k6, controllato qui entro l'1%)
  12 req/s           tre-20260921-150237 (mappatura separata, λ da env.txt)
  36 req/s           tre-20260921-162248 (mappatura separata, λ da env.txt)

Per ogni run: rate configurato di classe (umana (1−α−β)·λ, esaustiva α·λ, agentica β·λ)
e miss medio di classe m = media(1 − h) sulle ripetizioni (h_zipf, h_trav, h_agent di
points.csv). Scomposizione di Δ(Σ rate·miss) fra un punto basso (0) e uno alto (1):
  new agentic requests               (g1 − g0) · m_agent1
  agentic requests already present   g0 · (m_agent1 − m_agent0)
  human class                        u1 · m_human1 − u0 · m_human0
  exhaustive class                   e1 · m_exh1 − e0 · m_exh0
  sum of terms                       somma dei quattro termini
  measured / measured_se             media(origin_rps) alto − basso, SE combinato
  closure_pct                        |somma − misurato| / |misurato|, in %, dai valori
                                     non arrotondati
Le righe 0-36 (net, net_se, net_ci95_lo/hi) sono lo stesso netto di tools/net_agentic.py
(claim A9): SE combinato, IC 95% con il t di Student ai gradi di liberta' di Welch.
Le righe 0-36-replica sono lo stesso netto nella replica pre-registrata nello stesso giorno
(docs/PREREG-replica-20260924.md, R3; 25-26 set): P0 tre-20260926-013602 e S36
tre-20260926-001550, λ da env.txt. I due netti non si uniscono (claim A9).

Il lab resta in sola lettura: solo `ssh lab cat`.

Uso:
    python3 tools/fig05_data.py
"""
import csv
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import net_agentic  # noqa: E402
import scope_ttest as st  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "derived" / "fig05_accounting.csv"

# agentica nominale -> (run, λ configurato o None per leggerlo da env.txt)
RUNS = {0: ("tre-20260920-102015", 83.0), 12: ("tre-20260921-150237", None),
        36: ("tre-20260921-162248", None)}
STEPS = ((0, 12), (12, 36))
# replica pre-registrata (R3): agentica nominale -> (run, λ da env.txt)
REPLICA = {0: ("tre-20260926-013602", None), 36: ("tre-20260926-001550", None)}


def read_run(run, lam):
    rows = list(csv.DictReader(st.lab_cat(run, "points.csv").splitlines()))
    if not rows or len({(r["alpha"], r["beta"]) for r in rows}) != 1:
        sys.exit(f"{run}: points.csv vuoto o con piu' di un punto")
    if lam is None:
        lam = float(st.read_env(run)["LAMBDA"])
    else:
        measured = statistics.fmean(x["lambda"] for x in net_agentic.read_run(run))
        if abs(measured - lam) / lam > 0.01:
            sys.exit(f"{run}: λ misurato {measured:.2f} lontano da {lam}")
    a, b = float(rows[0]["alpha"]), float(rows[0]["beta"])
    o = [float(r["origin_rps"]) for r in rows]

    def miss(col):
        return statistics.fmean(1 - float(r[col]) for r in rows)

    return {"u": (1 - a - b) * lam, "e": a * lam, "g": b * lam,
            "mu": miss("h_zipf"), "me": miss("h_trav"), "mg": miss("h_agent") if b > 0 else 0.0,
            "mean": statistics.fmean(o), "var_mean": statistics.variance(o) / len(o), "n": len(o)}


def main():
    r = {k: read_run(run, lam) for k, (run, lam) in RUNS.items()}
    for k, x in r.items():
        print(f"  {k:2d} req/s: rate umana {x['u']:.4f} esaustiva {x['e']:.4f} agentica {x['g']:.4f}  "
              f"miss {x['mu']:.4f} / {x['me']:.4f} / {x['mg']:.4f}  "
              f"origin {x['mean']:.4f} +/- {math.sqrt(x['var_mean']):.4f}  (n = {x['n']})")
    out = []
    for lo, hi in STEPS:
        p, q = r[lo], r[hi]
        terms = [("new agentic requests", (q["g"] - p["g"]) * q["mg"]),
                 ("agentic requests already present", p["g"] * (q["mg"] - p["mg"])),
                 ("human class", q["u"] * q["mu"] - p["u"] * p["mu"]),
                 ("exhaustive class", q["e"] * q["me"] - p["e"] * p["me"])]
        total = sum(v for _, v in terms)
        meas = q["mean"] - p["mean"]
        se = math.sqrt(p["var_mean"] + q["var_mean"])
        step = f"{lo}-{hi}"
        out += [[step, t, f"{v:.3f}"] for t, v in terms]
        out += [[step, "sum of terms", f"{total:.3f}"], [step, "measured", f"{meas:.3f}"],
                [step, "measured_se", f"{se:.3f}"],
                [step, "closure_pct", f"{100 * abs(total - meas) / abs(meas):.2f}"]]
        print(f"  {step}: " + "  ".join(f"{t} {v:+.4f}" for t, v in terms))
        print(f"        somma {total:+.4f}  misurato {meas:+.4f} +/- {se:.4f}  "
              f"scarto {100 * (total - meas) / abs(meas):+.1f}%")
    rep = {k: read_run(run, lam) for k, (run, lam) in REPLICA.items()}
    for step, (a, b) in (("0-36", (r[0], r[36])), ("0-36-replica", (rep[0], rep[36]))):
        va, vb = a["var_mean"], b["var_mean"]
        net, se = b["mean"] - a["mean"], math.sqrt(va + vb)
        df = (va + vb) ** 2 / (va ** 2 / (a["n"] - 1) + vb ** 2 / (b["n"] - 1))
        q = net_agentic.t_quantile(0.975, df)
        out += [[step, "net", f"{net:.3f}"], [step, "net_se", f"{se:.3f}"],
                [step, "net_ci95_lo", f"{net - q * se:.3f}"],
                [step, "net_ci95_hi", f"{net + q * se:.3f}"]]
        print(f"  netto {step}: {net:+.4f} +/- {se:.4f}  IC 95% [{net - q * se:+.4f}, "
              f"{net + q * se:+.4f}]  (df di Welch {df:.2f})")
    with OUT_CSV.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["step", "term", "value"])
        w.writerows(out)
    print(f"scritto {OUT_CSV}")


if __name__ == "__main__":
    main()
