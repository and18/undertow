#!/usr/bin/env python3
"""
figA_data.py — genera i CSV di FIG-A1 e FIG-A2 (prima scritti a mano).

Dai points.csv dei sei run dello sweep AGENT_SCOPE (stessi run di FIG-01, via
scope_ttest.py) e con la stessa capienza di fig01_data.py (media di n_object_avg in
data/derived/cache_capacity.csv):

  data/derived/figA1_human_externality.csv   (claim B5) — run a quota 30%:
      human_p99_ms / _se   media e SE di p99_zipf sulle ripetizioni
      human_hit            media di h_zipf
      origin_rps / _se     media e SE di origin_rps

  data/derived/figA2_elasticity_model.csv    (claim B3, B4):
      observed             elasticita' del miss agentico = media(1 - h_agent) a quota 13%
                           / media(1 - h_agent) a quota 30% (rapporto delle medie)
      prior, tolerance     previsione scritta prima dei primi risultati a scope 0,06 e 0,20
                           (docs/PREREGISTRAZIONE-scopesweep.md, tabella righe 61-62,
                           tolleranza riga 65): costanti copiate, non misure
      posthoc_realdist     ricalcolo a posteriori con la distribuzione reale del generatore
                           (docs/RISULTATO-scopesweep.md, righe 33-35): costanti copiate

Run: quelli primari di scope_ttest.RUNS (TRAV_MODE=scen, claims v3.8), scritti nelle colonne
run (A1) e run_lo / run_hi (A2); W_over_capacity con i capitoli distinti del reachable set
(scope_ttest.reachable).

Il lab resta in sola lettura: solo `ssh lab cat`.

Uso:
    python3 tools/figA_data.py
"""
import csv
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope_ttest as st  # noqa: E402
from fig01_data import capacity  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_A1 = ROOT / "data" / "derived" / "figA1_human_externality.csv"
OUT_A2 = ROOT / "data" / "derived" / "figA2_elasticity_model.csv"

# scope -> (prior, tolerance, posthoc_realdist, role)
MODEL = {
    "0.02": ("", "", "7.75", "anchor (measured before the prediction was written)"),
    "0.06": ("3.10", "0.30", "2.06", "prediction"),
    "0.20": ("1.40", "0.30", "1.29", "prediction"),
}


def points(run):
    rows = list(csv.DictReader(st.lab_cat(run, "points.csv").splitlines()))
    if not rows:
        sys.exit(f"points.csv vuoto: {run}")
    return rows


def mean_se(v):
    return statistics.fmean(v), statistics.stdev(v) / math.sqrt(len(v))


def main():
    cap = capacity()
    a1, a2 = [], []
    for scope, (lo_id, hi_id) in st.RUNS.items():
        lo, hi = points(lo_id), points(hi_id)
        env = st.read_env(lo_id)
        _, w = st.reachable(scope, int(env.get("AGENT_MUL", st.AGENT_MUL_DEFAULT)),
                            int(env.get("AGENT_SESSION", st.SESSION_DEFAULT)))
        ratio = f"{w / cap:.4f}"
        p99, p99_se = mean_se([float(r["p99_zipf"]) for r in hi])
        hit = statistics.fmean(float(r["h_zipf"]) for r in hi)
        org, org_se = mean_se([float(r["origin_rps"]) for r in hi])
        a1.append([scope, ratio, f"{p99:.3f}", f"{p99_se:.3f}", f"{hit:.4f}",
                   f"{org:.4f}", f"{org_se:.4f}", hi_id])
        miss_lo = statistics.fmean(1 - float(r["h_agent"]) for r in lo)
        miss_hi = statistics.fmean(1 - float(r["h_agent"]) for r in hi)
        obs = miss_lo / miss_hi
        a2.append([scope, ratio, f"{obs:.4f}", *MODEL[scope], lo_id, hi_id])
        print(f"  scope {scope}: W/cap {ratio}  p99 umano {p99:.3f} +/- {p99_se:.3f}  "
              f"hit umano {hit:.4f}  origin {org:.4f} +/- {org_se:.4f}  "
              f"miss agentico {miss_lo:.4f} -> {miss_hi:.4f}  elasticita' {obs:.4f}")
    for path, header, rows in (
        (OUT_A1, ["scope", "W_over_capacity", "human_p99_ms", "human_p99_se", "human_hit",
                  "origin_rps", "origin_se", "run"], a1),
        (OUT_A2, ["scope", "W_over_capacity", "observed", "prior", "tolerance",
                  "posthoc_realdist", "role", "run_lo", "run_hi"], a2),
    ):
        with path.open("w", newline="") as f:
            wr = csv.writer(f, lineterminator="\n")
            wr.writerow(header)
            wr.writerows(rows)
        print(f"scritto {path}")
    print(f"capienza usata: {cap:.1f} oggetti")


if __name__ == "__main__":
    main()
