"""
FIG-01 — Marginal origin cost of the agentic class, at three working-set sizes.

CLAIM           A1 (MISURATO). Cross-references: C2 (capacity), C3 (honeypot).
RUNS            tre-20260921-150237 / -162248   scope 0.02
                tre-20260921-214946 / -230947   scope 0.06
                tre-20260922-002958 / -015010   scope 0.20
                AGENT_MUL=3266489917 verified in env.txt for all six.
ROWS            nominal working set of the agentic class (scope x corpus x 3
                contiguous chapters) / cache capacity (5,274 objects, measured
                with varnish_main_n_object on a full cache).
BARS            origin requests induced per agentic request added between 12 and
                36 req/s (13% -> 30% of load); human and exhaustive classes fixed
                at 55 and 28 req/s. Mean of 5 runs; whisker = +/- 1 SE.

DESIGN (v3, "ladder")
  One focal point: the zero line. Rows read top to bottom as the working set
  grows (each step is about x3); bars grow from zero, so the change of sign
  is seen before any number is read. Values sit in their own right-aligned
  column, keys in a left column: the figure reads as a table with a picture
  in it. Error whiskers are drawn but quiet (they are ~2% of the bar).
  The honeypot reference is a tag on the row it refers to.

MANDATORY CAVEATS (carried into the caption / source line)
  1. Whiskers are +/- 1 SE; they are smaller than the bar ends.
  2. The values are the marginal over 12 -> 36 req/s. At the smallest working
     set the first 12 req/s cost +0.103 each and the NET effect 0 -> 36 req/s
     is positive (+0.392 +/- 0.158). The figure must never be read as
     "agentic traffic reduces origin work" (retracted, R2).
  3. The tag places real agents by WINDOWED working set (distinct objects in
     143 s: p90 = 670 observed, ~693 for the first row), not by nominal size.

DELIBERATELY NOT DRAWN
  A "working set = cache capacity" boundary labelled fits / exceeds: it would
  re-introduce the residency-boundary interpretation retracted in R4.
  A line joining the rows: three points do not measure a functional form.

Usage:  python3 analysis/fig_01_marginal_vs_workingset.py
"""
import csv, sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import figure_style as S
from figure_style import C, T, PT

STEM = "FIG-01_marginal-vs-working-set"
DATA = S.ROOT / "data/derived/fig01_marginal_vs_workingset.csv"

rows = list(csv.DictReader(open(DATA)))
ratio = [float(r["W_over_capacity"]) for r in rows]
objs  = [int(r["W_nominal"]) for r in rows]
y     = [float(r["marginal"]) for r in rows]
se    = [float(r["marginal_se"]) for r in rows]

def r3(v):   # explicit half-up rounding, identical on every machine
    return float(Decimal(str(v)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))

TEXT = {
    "headline": "What an extra agentic request costs the origin\n"
                "depends on its working set",
    "deck":     "Origin requests caused by each added agentic request, at three working-set "
                "sizes.\nTraffic volumes, cache and corpus are held fixed; only the working "
                "set changes.",
    "source":   "Source: Undertow testbed, mean of 5 runs per row; whiskers ± 1 standard "
                "error. Added load: 12 to 36 req/s.\nReal agents: theslowshelf.org honeypot, "
                "p90 of distinct objects per 143 s window, 12 Aug – 21 Sep 2026.",
    "col_key":  "WORKING SET",
    "col_val":  "MEAN ± SE",
    "less":     "reduces origin work",
    "less_short": "reduces",
    "more":     "adds origin work",
    "tag":      "closest to real agents",
    "axis":     "Origin requests per added agentic request (12–36 req/s)",
}

XMIN, XMAX = -0.10, 0.50
TICKS = [-0.1, 0, 0.1, 0.2, 0.3, 0.4, 0.5]

# Column widths in inches, per width. Everything else is derived.
GRID = {                 # key col, value col, row height, gutter
    "editorial": (1.30, 0.78, 0.50, 0.14),
    "lncs":      (1.10, 0.66, 0.44, 0.12),
    "acm-col":   (0.80, 0.50, 0.38, 0.08),
}


def build(variant):
    width, mode = {"paper": ("lncs", "paper"), "paper-acm": ("acm-col", "paper"),
                   "editorial": ("editorial", "editorial")}[variant]
    key_w, val_w, row_h, gut = GRID[width]
    narrow = width == "acm-col"
    S._rc(S.WIDTH[width])                       # sets T.base for the arithmetic below

    head_h = T.s(T.caps) * 1.3 * PT + 0.07      # column headers + gap to the rule
    tick_h = 0.05 + T.s(T.tick) * 1.2 * PT
    axis_h = (0.06 + T.s(T.label) * 1.25 * PT) if mode == "paper" else 0
    body_h = head_h + 0.05 + 3 * row_h + tick_h + axis_h

    H  = S.Canvas.height(body_h, width, mode, TEXT["headline"], TEXT["deck"], TEXT["source"])
    cv = S.Canvas(width, mode, H)
    top = cv.header(TEXT["headline"], TEXT["deck"])

    bx = cv.left + key_w + gut                  # bar column, inches
    bw = cv.right - val_w - gut - bx
    X  = lambda v: bx + (v - XMIN) / (XMAX - XMIN) * bw
    x0 = X(0)

    # ── column headers + direction, one baseline, table rule under it ─────
    y_head = top + T.s(T.caps) * 1.0 * PT
    caps = dict(ha="left", va="baseline", color=C.ink_faint, fontweight=600)
    cv.text(cv.left, y_head, TEXT["col_key"], T.caps, **caps)
    cv.text(cv.right, y_head, TEXT["col_val"], T.caps, **{**caps, "ha": "right"})
    cv.text(x0 - 0.07, y_head, TEXT["less" if mode == "editorial" else "less_short"], T.label,
            ha="right", va="baseline", color=C.ink_soft)
    cv.text(x0 + 0.07, y_head, TEXT["more"], T.label, ha="left", va="baseline",
            color=C.ink_soft)
    y_rule = top + head_h
    cv.hline(cv.left, cv.right, y_rule, color=C.rule_dark, lw=0.6)

    # ── plot layer: an axes whose y unit is inches from the top ──────────
    y_rows = y_rule + 0.05
    y_end  = y_rows + 3 * row_h
    ax = cv.axes(bx, y_rule, bw, y_end - y_rule)
    ax.set_xlim(XMIN, XMAX); ax.set_ylim(y_end, y_rule)
    for v in TICKS:
        if v != 0:
            ax.plot([v, v], [y_rule, y_end], color=C.rule, lw=0.6, zorder=0)
    ax.plot([0, 0], [y_rule, y_end], color=C.ink, lw=1.3, zorder=4)
    # the zero line rises through the header, between its two direction labels
    cv.fig.add_artist(S.mpl.lines.Line2D([cv.fx(x0)] * 2,
                      [cv.fy(y_head - T.s(T.label) * 0.95 * PT), cv.fy(y_rule)],
                      color=C.ink, lw=1.3, solid_capstyle="butt"))

    bar_h = row_h * 0.42
    cap_h = bar_h * 0.20
    for i in range(3):
        yc = y_rows + (i + 0.5) * row_h
        ax.barh(yc, y[i], height=bar_h, color=C.agentic, lw=0, zorder=2)
        lo, hi = y[i] - se[i], y[i] + se[i]
        ax.plot([lo, hi], [yc, yc], color=C.ink, lw=0.55, zorder=5)
        for e in (lo, hi):
            ax.plot([e, e], [yc - cap_h, yc + cap_h], color=C.ink, lw=0.55, zorder=5)

        # key column: what the row is
        cv.text(cv.left, yc - 0.012, f"{ratio[i]:.2f}× cache", T.key,
                ha="left", va="bottom", fontweight=600)
        cv.text(cv.left, yc + 0.030, f"{objs[i]:,} objects", T.sub,
                ha="left", va="top", color=C.ink_faint)
        # value column: what it costs
        cv.text(cv.right, yc - 0.012, S.num(r3(y[i]), 3, sign=True), T.value,
                ha="right", va="bottom", fontweight=600)
        cv.text(cv.right, yc + 0.030, "± " + S.num(r3(se[i]), 3), T.sub,
                ha="right", va="top", color=C.ink_faint)

    # ── the one annotation: a tag on the row it refers to ────────────────
    yc0 = y_rows + 0.5 * row_h
    cv.text(x0 + 0.10 + 0.04, yc0, TEXT["tag"], T.label, ha="left", va="center",
            color=C.ink_soft,
            bbox=dict(boxstyle="round,pad=0.38,rounding_size=0.75", fc=C.surface,
                      ec="#c9c9c2", lw=0.6))

    # ── scale ────────────────────────────────────────────────────────────
    y_tick = y_end + 0.05
    for v in TICKS:
        cv.text(X(v), y_tick, "0" if v == 0 else S.num(v, 1, sign=True), T.tick,
                ha="center", va="top", color=C.ink_faint)
    if mode == "paper":
        cv.text(bx + bw / 2, y_tick + T.s(T.tick) * 1.2 * PT + 0.06, TEXT["axis"],
                T.label, ha="center", va="top", color=C.ink_soft)

    cv.footer(TEXT["source"])
    return cv.save(STEM, variant)


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
        "In each row the agentic class is raised from 12 to 36 req/s (13% to 30% of load) "
        "while the human and exhaustive classes stay fixed at 55 and 28 req/s; only the "
        "scope from which the agentic class draws its sessions changes. Rows give the "
        "nominal working set (scope × corpus × 3 contiguous chapters) as a multiple of the "
        "measured cache capacity of 5,274 objects. Bars: mean of 5 runs; whiskers: ± 1 SE. "
        "The values are marginal between 12 and 36 req/s: in the first row the first "
        "12 req/s cost +0.103 origin requests each, and the net effect from 0 to 36 req/s "
        "is positive (+0.392 ± 0.158). The tag marks the row closest to real agents by "
        "windowed working set (distinct objects within 143 s; honeypot 90th percentile 670, "
        "against about 693 for that row), not by nominal working set. Working sets are "
        "decorrelated across classes (AGENT_MUL = 3266489917).\n")


if __name__ == "__main__":
    for v in ("paper", "paper-acm", "editorial"):
        for p in build(v):
            print("wrote", p.relative_to(S.ROOT))
    provenance()
