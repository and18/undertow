#!/usr/bin/env python3
"""
fig01_data.py — genera data/derived/fig01_marginal_vs_workingset.csv (FIG-01, claim A1).

Prima il CSV era scritto a mano. Ora ogni colonna viene da una fonte rintracciabile:
  - marginale, SE, origin lo/hi: points.csv dei sei run dello sweep (via scope_ttest.py:
    stesse funzioni, stesso divisore beta*lambda configurato);
  - W_objects: capitoli DISTINTI del reachable set (scope_ttest.reachable: floor(corpus *
    scope) basi x AGENT_SESSION capitoli contigui, senza doppioni; a scope 0,20 10 020 su 10 170
    posizioni); W_positions: le posizioni, con i doppioni;
  - run: i sei run primari di scope_ttest.RUNS (TRAV_MODE=scen, claims v3.8), nelle colonne
    run_lo e run_hi;
  - W_over_capacity: W_objects / capienza media di data/derived/cache_capacity.csv
    (tools/cache_capacity.py, varnish_main_n_object da VictoriaMetrics).

Il lab resta in sola lettura: solo `ssh lab cat`.

Uso:
    python3 tools/fig01_data.py
"""
import csv
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope_ttest as st  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CAP_CSV = ROOT / "data" / "derived" / "cache_capacity.csv"
OUT_CSV = ROOT / "data" / "derived" / "fig01_marginal_vs_workingset.csv"


def capacity():
    if not CAP_CSV.exists():
        sys.exit(f"manca {CAP_CSV}: lancia prima tools/cache_capacity.py")
    with CAP_CSV.open() as f:
        return statistics.fmean(float(r["n_object_avg"]) for r in csv.DictReader(f))


def main():
    cap = capacity()
    rows = []
    for scope, (lo_id, hi_id) in st.RUNS.items():
        lo, hi = st.read_run(lo_id), st.read_run(hi_id)
        session = int(lo["env"].get("AGENT_SESSION", st.SESSION_DEFAULT))
        mul = int(lo["env"].get("AGENT_MUL", st.AGENT_MUL_DEFAULT))
        pos, w = st.reachable(scope, mul, session)
        d_rate = hi["agentic"] - lo["agentic"]
        m = (hi["mean"] - lo["mean"]) / d_rate
        se = math.sqrt(hi["var_mean"] + lo["var_mean"]) / d_rate
        rows.append([scope, w, pos, f"{w / cap:.4f}", f"{m:.5f}", f"{se:.5f}",
                     f"{lo['mean']:.4f}", f"{math.sqrt(lo['var_mean']):.4f}",
                     f"{hi['mean']:.4f}", f"{math.sqrt(hi['var_mean']):.4f}",
                     min(lo["n"], hi["n"]), lo_id, hi_id])
        print(f"  scope {scope}: W {w}  W/cap {w / cap:.4f}  marginale {m:+.5f} +/- {se:.5f}")
    with OUT_CSV.open("w", newline="") as f:
        wr = csv.writer(f, lineterminator="\n")
        wr.writerow(["scope", "W_objects", "W_positions", "W_over_capacity", "marginal", "marginal_se",
                     "origin_lo", "origin_lo_se", "origin_hi", "origin_hi_se", "reps",
                     "run_lo", "run_hi"])
        wr.writerows(rows)
    print(f"capienza usata: {cap:.1f} oggetti\nscritto {OUT_CSV}")


if __name__ == "__main__":
    main()
