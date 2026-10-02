"""
FIG-07 — Why the sign of the agentic marginal flips.

CLAIM     B7 (INTERPRETATIVO, post hoc): with the generator's access distribution the
          characteristic-time approximation reproduces the sign change of A1; refs A1.
DATA      data/posthoc/che_posthoc.csv (tools/che_posthoc.py, version B: periodic
          exhaustive class), columns lamT_agent_mean per point S12 / S36 and scope;
          data/derived/fig01_marginal_vs_workingset.csv for the measured marginal and the
          reachable set as a multiple of the cache capacity.

DESIGN PASS
  Reader    an object's miss rate rises and then falls with its request rate; at the
            narrowest reachable set, tripling the agentic rate carries the typical agentic
            object past the maximum, where more requests mean fewer misses per object.
  Encoding  the curve x·e^(−x) on a log x axis (λT spans two decades), the maximum at
            λT = 1 labelled; one arrow per reachable set from the mean λT at
            12 req/s to that at 36 req/s, in the agentic colour.
  Dominant  the arrow that crosses the maximum.
  Secondary the measured marginal as a label on each arrow; the maximum labelled once.
  Prevent   reading the arrows as a fit or a measurement: the positions are means over
            agentic objects from a post-hoc calculation; the caption says so, and that the
            marginal of the table is computed object by object; no fitted parameters.
"""
import csv
import math

import figure_style as S
from figure_style import C, T, PT, SEMIBOLD

STEM = "FIG-07_why-sign-flips"
CLAIMS = "B7 (INTERPRETATIVO, post hoc); refs A1"
DATA = ["../posthoc/che_posthoc.csv", "fig01_marginal_vs_workingset.csv"]
RUNS = ["post-hoc calculation (tools/che_posthoc.py, version B); measured marginals as FIG-01"]

EDITORIAL = dict(
    headline="Past λT = 1, more requests mean fewer misses per object",
    deck="Misses of one object per characteristic time, λT·exp(−λT), and where the agentic "
         "objects sit\nat 12 and 36 agentic req/s, for three reachable-set sizes.",
    source="Source: post-hoc characteristic-time calculation with the generator's access "
           "distribution;\nmeasured marginals from the testbed, mean of 5 repetitions.",
)

XMIN, XMAX = 0.05, 10.0
YMAX = 0.42


def _posthoc():
    """(scope -> (λT at 12 req/s, λT at 36 req/s)), version B; comment lines skipped."""
    path = S.data_file(DATA[0])
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(l for l in f if not l.startswith("#")))
    out = {}
    for r in rows:
        if r["model"] != "B":
            continue
        lo, hi = out.get(r["scope"], (None, None))
        v = float(r["lamT_agent_mean"])
        out[r["scope"]] = (v, hi) if r["point"] == "S12" else (lo, v)
    return out


def _rows():
    lt = _posthoc()
    meas = S.read_csv(DATA[1])
    rows = []
    for m in meas:
        sc = m["scope"]
        a, b = lt[sc]
        rows.append(dict(scope=sc, ratio=float(m["W_over_capacity"]),
                         marginal=float(m["marginal"]), lt12=a, lt36=b))
    return rows


def _caption():
    """Every number in the caption is computed from the CSVs the figure draws."""
    return (
        "Why the sign of the agentic marginal flips, computed post hoc with the "
        "characteristic-time approximation. The curve is λT·exp(−λT), the misses of one object "
        "per characteristic time T for an object requested at rate λ; it peaks at λT = 1. For "
        "each reachable set, the arrow goes from the mean λT of the agentic objects at 12 "
        "agentic req/s to that at 36 req/s (periodic exhaustive class, Section 5.2), and the "
        "label gives the measured marginal. The positions are means over agentic objects, "
        "whereas the marginal in the table of Section 5.2 is computed object by object, so the "
        "arrows illustrate the mechanism and do not reproduce the values. Computed after the "
        "measurements, with T solved from the cache capacity and no fitted parameters."
    )


CAPTION = _caption()


def render(variant):
    sp = S.Spec(variant)
    rows = _rows()
    tick_w = sp.pick(0.30, 0.34, 0.36)
    fh = sp.pick(1.80, 2.05, 2.25)
    title_h = T.s(T.axis) * 1.2 * PT + 0.12
    below = 0.05 + T.s(T.tick) * 1.25 * PT + 0.06 + T.s(T.axis) * 1.3 * PT
    cv = S.Canvas(sp, title_h + fh + below, **EDITORIAL)
    fx, fw = cv.left + tick_w, cv.width - tick_w - 0.08
    f = cv.frame(fx, cv.top + title_h, fw, fh, (XMIN, XMAX), (0, YMAX), xlog=True)
    yt = [0, 0.1, 0.2, 0.3, 0.4]
    f.hgrid(yt[1:])
    f.hbase(0, color=C.rule_mid, lw=0.6)
    f.yticks(yt, ["0" if v == 0 else S.num(v, 1) for v in yt])
    f.ytitle("Misses per object per characteristic time, λT·exp(−λT)", x=cv.left)
    xt = [0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10]
    f.xticks(xt, [S.num(v, 2) if v < 0.1 else S.num(v, 1) if v < 1 else str(int(v)) for v in xt])
    f.xtitle(sp.pick("λT, mean over agentic objects (log)",
                     "λT, mean over agentic objects (log scale)"))

    # the curve and its maximum
    n = 400
    xs = [XMIN * (XMAX / XMIN) ** (i / (n - 1)) for i in range(n)]
    f.ax.plot(xs, [x * math.exp(-x) for x in xs], color=C.neutral, lw=1.3, zorder=2)
    peak = math.exp(-1)
    f.label(1, peak, "maximum at λT = 1", T.sub, dy=7, ha="center", va="bottom",
            color=C.ink_soft)

    # one arrow per reachable set, label at the start of the arrow
    place = {"0.02": dict(at="end", dx=-7, dy=-3, ha="right", va="top"),
             "0.06": dict(at="start", dx=4, dy=-9, ha="left", va="top"),
             "0.20": dict(at="start", dx=-2, dy=-9, ha="left", va="top")}
    for r in rows:
        a, b = r["lt12"], r["lt36"]
        ya, yb = a * math.exp(-a), b * math.exp(-b)
        f.ax.annotate("", xy=(b, yb), xytext=(a, ya), zorder=4,
                      arrowprops=dict(arrowstyle="-|>", color=C.agentic, lw=1.3,
                                      shrinkA=2, shrinkB=2, mutation_scale=9))
        f.dot(a, ya, C.agentic, hollow=True, size=4.4 * T.base / 8.4)
        f.dot(b, yb, C.agentic, size=4.4 * T.base / 8.4)
        p = place[r["scope"]]
        xv, yv = (a, ya) if p["at"] == "start" else (b, yb)
        f.label(xv, yv, f"{S.num(r['ratio'], 2)}× cache: {S.num(r['marginal'], 3, sign=True)}",
                T.label, dx=p["dx"], dy=p["dy"], ha=p["ha"], va=p["va"], color=C.ink,
                weight=SEMIBOLD)
    return cv.save(STEM)
