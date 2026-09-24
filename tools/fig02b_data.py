#!/usr/bin/env python3
"""
fig02b_data.py — genera data/derived/fig02b_exhaustive_marginal.csv (FIG-02 b, claim A7).

Prima il CSV era scritto a mano. Serie crawler del 16 settembre (blocco B di
harness/load/marginale2.sh: umana 55 e agentica 12 req/s fisse, esaustiva 0 → 42,
mappatura condivisa, finestra 1211 s, 3 ripetizioni per punto):
  marginal / marginal_se  (media origin_rps del punto alto − media del punto basso)
                          / (α·λ alto − α·λ basso), SE combinato dalle due medie;
                          α da points.csv, λ configurato in marginale2.sh (i run sono
                          anteriori a env.txt), controllato contro il rate misurato
                          di k6 (http_reqs / measure)
  elasticity              miss esaustivo a 42 req/s / miss esaustivo a 14 req/s,
                          media(1 − h_trav) sulle ripetizioni (rapporto delle medie);
                          a 0 req/s il miss esaustivo non esiste
  from_rps, to_rps        etichette nominali del passo (0, 14, 28, 42)

Il lab resta in sola lettura: solo `ssh lab cat`.

Uso:
    python3 tools/fig02b_data.py
"""
import csv
import json
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope_ttest as st  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "derived" / "fig02b_exhaustive_marginal.csv"
SERIES = "crawler series 16 Sep 2026 (shared mapping; 1211 s window; 3 reps)"

# esaustiva nominale -> (run, λ configurato in marginale2.sh, blocco B)
POINTS = {
    0: ("tre-20260916-013722", 67),
    14: ("tre-20260916-025527", 81),
    28: ("tre-20260916-041332", 95),
    42: ("tre-20260916-053137", 109),
}


def read_point(run, lam):
    rows = list(csv.DictReader(st.lab_cat(run, "points.csv").splitlines()))
    if not rows or len({r["alpha"] for r in rows}) != 1:
        sys.exit(f"{run}: points.csv vuoto o con piu' di un punto")
    origin = [float(r["origin_rps"]) for r in rows]
    measured = []
    for r in rows:
        m = json.loads(st.lab_cat(run, f"m-a{r['alpha']}-b{r['beta']}-{r['rep']}.json"))["metrics"]
        measured.append(m["http_reqs"]["values"]["count"] / float(r["measure"]))
    rate = statistics.fmean(measured)
    if abs(rate - lam) / lam > 0.01:
        sys.exit(f"{run}: λ misurato {rate:.2f} lontano dal configurato {lam}")
    return {
        "exh": float(rows[0]["alpha"]) * lam,
        "mean": statistics.fmean(origin),
        "var_mean": statistics.variance(origin) / len(origin),
        "miss": statistics.fmean(1 - float(r["h_trav"]) for r in rows),
        "n": len(rows), "lam_measured": rate,
    }


def main():
    pts = {k: read_point(run, lam) for k, (run, lam) in POINTS.items()}
    for k, p in pts.items():
        print(f"  esaustiva {k:2d}: α·λ {p['exh']:.4f}  λ misurato {p['lam_measured']:.3f}  "
              f"origin {p['mean']:.4f} +/- {math.sqrt(p['var_mean']):.4f}  "
              f"miss esaustivo {p['miss']:.4f}  (n = {p['n']})")
    elast = pts[42]["miss"] / pts[14]["miss"]
    print(f"  elasticita' 14 -> 42: {elast:.4f}")
    rows = []
    keys = list(pts)
    for lo, hi in zip(keys, keys[1:]):
        d = pts[hi]["exh"] - pts[lo]["exh"]
        m = (pts[hi]["mean"] - pts[lo]["mean"]) / d
        se = math.sqrt(pts[hi]["var_mean"] + pts[lo]["var_mean"]) / d
        print(f"  {lo} -> {hi}: marginale {m:.5f} +/- {se:.5f}")
        rows.append([lo, hi, f"{m:.4f}", f"{se:.4f}", f"{elast:.4f}", SERIES])
    with OUT_CSV.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["from_rps", "to_rps", "marginal", "marginal_se", "elasticity", "series"])
        w.writerows(rows)
    print(f"scritto {OUT_CSV}")


if __name__ == "__main__":
    main()
