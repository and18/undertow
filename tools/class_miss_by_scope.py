#!/usr/bin/env python3
"""
class_miss_by_scope.py — per-class miss factors, agentic share 13% -> 30%, at the three
scopes of the AGENT_SCOPE sweep (claim A2; FIG-02 panel a).

For each scope and class, from the points.csv of the two runs (same runs as FIG-01, via
scope_ttest.py; separate mapping, 5 repetitions each):
    miss = mean(1 - h) over the repetitions, SE = stdev / sqrt(n)
    factor = miss at 13% share / miss at 30% share  (ratio of the means, rule v3)
    fold    = max / min of the two means, with the direction (down if the miss falls):
              it is the «factor» of A2 and the label of FIG-02 a
Columns of points.csv: h_zipf (human), h_trav (exhaustive), h_agent (agentic).

Writes:
    data/derived/fig02a_miss_by_class.csv        (scope 0.02, the one of FIG-02 a)
    data/derived/class_miss_by_scope.csv         (all three scopes)
For the agentic class the factor coincides with the elasticity of figA_data.py (B3, B4).

The lab stays read-only: only `ssh lab cat`.

Usage:
    python3 tools/class_miss_by_scope.py
"""
import csv
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scope_ttest as st  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_ALL = ROOT / "data" / "derived" / "class_miss_by_scope.csv"
OUT_FIG02A = ROOT / "data" / "derived" / "fig02a_miss_by_class.csv"
CLASSES = (("human", "h_zipf"), ("exhaustive", "h_trav"), ("agentic", "h_agent"))


def points(run):
    rows = list(csv.DictReader(st.lab_cat(run, "points.csv").splitlines()))
    if not rows:
        sys.exit(f"points.csv empty: {run}")
    return rows


def miss(rows, col):
    v = [1 - float(r[col]) for r in rows]
    return statistics.fmean(v), statistics.stdev(v) / math.sqrt(len(v))


def main():
    out, fig02a = [], []
    for scope, (lo_id, hi_id) in st.RUNS.items():
        lo, hi = points(lo_id), points(hi_id)
        for cls, col in CLASSES:
            m13, s13 = miss(lo, col)
            m30, s30 = miss(hi, col)
            f = m13 / m30
            fold, way = max(m13, m30) / min(m13, m30), ("down" if m30 < m13 else "up")
            out.append([scope, cls, f"{m13:.4f}", f"{s13:.4f}", f"{m30:.4f}", f"{s30:.4f}",
                        f"{f:.4f}", f"{fold:.4f}", way, len(lo), len(hi), f"{lo_id}+{hi_id}"])
            if scope == "0.02":
                fig02a.append([cls, f"{m13:.4f}", f"{s13:.4f}", f"{m30:.4f}", f"{s30:.4f}",
                               f"{fold:.4f}", way, f"{lo_id}+{hi_id}"])
            print(f"  scope {scope} {cls:10s} miss {m13:.4f} +/- {s13:.4f} -> "
                  f"{m30:.4f} +/- {s30:.4f}   factor {f:.4f}   fold {fold:.4f} {way}")
    with OUT_ALL.open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["scope", "class", "miss_share13", "se13", "miss_share30", "se30",
                    "factor", "fold", "direction", "reps13", "reps30", "runs"])
        w.writerows(out)
    with OUT_FIG02A.open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["class", "miss_share13", "se13", "miss_share30", "se30", "fold",
                    "direction", "runs"])
        w.writerows(fig02a)
    print(f"written {OUT_ALL} and {OUT_FIG02A}")


if __name__ == "__main__":
    main()
