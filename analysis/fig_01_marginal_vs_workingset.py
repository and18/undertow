"""
FIG-01 — Marginal origin cost of one traffic class, versus its working-set size.

CLAIM           A1 (MISURATO). Cross-references: C2 (capacity), C3 (honeypot).
RUNS            tre-20260921-150237 / -162248   scope 0.02
                tre-20260921-214946 / -230947   scope 0.06
                tre-20260922-002958 / -015010   scope 0.20
                AGENT_MUL=3266489917 verified in env.txt for all six.
X               nominal working set of the agentic class (scope x corpus x 3
                contiguous chapters) / cache capacity (5,274 objects, measured
                with varnish_main_n_object on a full cache). Log scale.
Y               origin requests induced per agentic request added between
                12 and 36 req/s (13% -> 30% of load), human and exhaustive
                classes fixed at 55 and 28 req/s.
AGGREGATION     mean of 5 runs per point; SE propagated from the two means.

MANDATORY CAVEATS (carried into the caption)
  1. Error bars are smaller than the markers; values are labelled directly.
  2. The segment between points shows ORDER, not a measured functional form.
  3. The y value is the marginal over 12 -> 36 req/s. At the smallest working
     set the first 12 req/s cost +0.103 each, and the NET effect from 0 to
     36 req/s is positive (+0.392 +/- 0.158). The figure must never be read as
     "agentic traffic reduces origin work" — that claim is retracted (R2).
  4. The honeypot marker places real agents by WINDOWED working set (distinct
     objects in 143 s: p90 = 670 observed, ~693 for this point), not by
     nominal working set.

DELIBERATELY NOT DRAWN
  A vertical rule at "working set = cache capacity" labelled fits / exceeds.
  It would re-introduce the residency-boundary interpretation retracted in R4.

Usage:  python3 analysis/fig_01_marginal_vs_workingset.py
"""
import csv, sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import figure_style as S
from figure_style import C, T

STEM = "FIG-01_marginal-vs-working-set"
DATA = S.ROOT / "data/derived/fig01_marginal_vs_workingset.csv"

rows = list(csv.DictReader(open(DATA)))
x  = np.array([float(r["W_over_capacity"]) for r in rows])
y  = np.array([float(r["marginal"])        for r in rows])
se = np.array([float(r["marginal_se"])     for r in rows])

def se3(v):  # explicit half-up rounding, so 0.0055 -> 0.006 on every machine
    return float(Decimal(str(v)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))

TEXT = {
    "x_long":  "Working set of the class / cache capacity  (log scale)",
    "x_short": "Working set / cache capacity  (log)",
    "y_long":  "Origin requests per agentic\nrequest added (12–36 req/s)",
    "y_short": "Origin requests per\nadded agentic request",
    "hp_long": "Real agents’ working set\n(honeypot p90, 143 s window)",
    "hp_short":"Real agents\n(honeypot p90)",
    "adds":    "adds origin work",
    "reduces": "reduces origin work",
    "headline":"What an extra agentic request costs the origin\ndepends on its working set",
    "deck":    "Origin requests caused by each added agentic request, at three working-set sizes.\n"
               "Traffic volumes, cache and corpus are held fixed; only the working set changes.",
    "source":  "Source: Undertow testbed, mean of 5 runs per point; ± standard error.\n"
               "Real-agent reference: theslowshelf.org honeypot, 12 Aug – 21 Sep 2026.",
}


def build(variant):
    narrow = variant == "paper-acm"
    width  = {"paper": "lncs", "paper-acm": "acm-col", "editorial": "editorial"}[variant]
    ratio  = {"paper": 0.64,  "paper-acm": 0.80,      "editorial": 0.56}[variant]
    mode   = "editorial" if variant == "editorial" else "paper"

    fig, ax = S.figure(width, ratio=ratio, mode=mode)

    # ── semantic ground ───────────────────────────────────────────────────
    ax.axhspan(-0.10, 0, color=C.wash, lw=0, zorder=0)
    ax.axhline(0, color=C.rule_dark, lw=0.9, zorder=2)

    # ── data ──────────────────────────────────────────────────────────────
    ax.plot(x, y, color=C.agentic, lw=1.3, alpha=0.55, ls=(0, (1.2, 2.2)),
            dash_capstyle="round", zorder=3)                       # order, not form
    ax.errorbar(x, y, yerr=se, fmt="none", ecolor=C.agentic, elinewidth=1.2,
                capsize=2.2, capthick=1.0, zorder=4)
    ax.plot(x, y, "o", ms=8.0 if not narrow else 6.6, color=C.agentic, zorder=5,
            mec="white", mew=1.6)

    # ── scales ────────────────────────────────────────────────────────────
    ax.set_xscale("log")
    ax.set_xlim(0.148, 3.2)
    ax.set_ylim(-0.10, 0.58)
    ax.set_xticks([0.2, 0.5, 1, 2])
    ax.set_xticklabels([S.num(v, 1) if v < 1 else f"{v:g}" for v in (0.2, 0.5, 1, 2)])
    ax.xaxis.set_minor_formatter(__import__("matplotlib").ticker.NullFormatter())
    ax.set_yticks([0, 0.1, 0.2, 0.3, 0.4, 0.5])
    ax.set_yticklabels(["0"] + [S.num(v, 1) for v in (0.1, 0.2, 0.3, 0.4, 0.5)])
    S.spine_offset(ax)
    ax.set_xlabel(TEXT["x_short" if narrow else "x_long"])
    ax.set_ylabel(TEXT["y_short" if narrow else "y_long"])

    # ── direct value labels (mandatory: aqua is below 3:1 on white) ──────
    for i, where in enumerate(("right", "below-right", "above")):
        S.value_label(ax, x[i], y[i], S.num(y[i], 3, sign=True),
                      "± " + S.num(se3(se[i]), 3), where=where,
                      gap=7 if not narrow else 6)

    # ── the two regimes of the y axis, right-aligned, off the data ───────
    S.note(ax, 3.1, 0.024, TEXT["adds"], ha="right", va="bottom")
    S.note(ax, 3.1, -0.050, TEXT["reduces"], ha="right", va="center")

    # ── honeypot reference: a short vertical leader to the first point ───
    # A flag: vertical leader from the point, label left-aligned on the leader
    # (never runs into the y-axis label, never crosses the data).
    y_top = 0.20
    ax.plot([x[0], x[0]], [y[0] + 0.032, y_top], color=C.rule_dark, lw=0.7,
            alpha=0.45, solid_capstyle="butt", zorder=2.5)
    ax.annotate(TEXT["hp_short" if narrow else "hp_long"], (x[0], y_top),
                xytext=(-0.5, 3), textcoords="offset points", ha="left", va="bottom",
                fontsize=T.s(T.note), color=C.ink_faint, linespacing=1.3)

    if mode == "editorial":
        S.editorial_frame(fig, ax, TEXT["headline"], TEXT["deck"], TEXT["source"])

    sub = {"paper": "paper", "paper-acm": "paper-acm", "editorial": "editorial"}[variant]
    return S.save(fig, STEM, sub)


def provenance():
    p = S.ROOT / "figures" / "paper" / f"{STEM}.provenance.txt"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        "FIG-01 — marginal origin cost versus working-set size\n"
        "claim     A1 (MISURATO); refs C2, C3\n"
        "data      data/derived/fig01_marginal_vs_workingset.csv\n"
        "runs      tre-20260921-150237 -162248 -214946 -230947\n"
        "          tre-20260922-002958 -015010\n"
        "variants  paper (4.80in), paper-acm (3.33in), editorial (6.20in)\n"
        "rebuild   python3 analysis/fig_01_marginal_vs_workingset.py\n")
    c = S.ROOT / "figures" / "paper" / f"{STEM}.caption.txt"
    c.write_text(
        "Figure 1. Marginal origin cost of the agentic class at three working-set sizes. "
        "At each point the agentic class is raised from 12 to 36 req/s (13% to 30% of load) "
        "while the human and exhaustive classes stay fixed at 55 and 28 req/s; only the "
        "scope from which the agentic class draws its sessions changes. The x axis gives the "
        "nominal working set (scope × corpus × 3 contiguous chapters) over the measured "
        "cache capacity of 5,274 objects. Mean of 5 runs per point; error bars (± SE) are "
        "smaller than the markers. The dotted segment indicates order, not a measured "
        "functional form. The y value is the marginal between 12 and 36 req/s: at the smallest "
        "working set the first 12 req/s cost +0.103 origin requests each, and the net effect "
        "from 0 to 36 req/s is positive (+0.392 ± 0.158). The honeypot marker locates real "
        "agents by windowed working set (distinct objects within 143 s; observed 90th "
        "percentile 670, against about 693 for this point), not by nominal working set. "
        "Working sets are decorrelated across classes (AGENT_MUL = 3266489917).\n")


if __name__ == "__main__":
    for v in ("paper", "paper-acm", "editorial"):
        for p in build(v):
            print("wrote", p.relative_to(S.ROOT))
    provenance()
