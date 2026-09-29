"""
FIG-01 — The marginal origin cost of the agentic class changes sign with its reachable set.

CLAIM     A1 (MISURATO). Cross-references C2 (capacity), C3 (honeypot).
DATA      data/derived/fig01_marginal_vs_workingset.csv
RUNS      primary (claims v3.8, TRAV_MODE=scen): tre-20260928-150154/-162206 (scope 0.02),
          tre-20260929-064412/-080424 (0.06), tre-20260929-092436/-104448 (0.20);
          AGENT_MUL=3266489917 in env.txt. The CSV names the run of every row.

DESIGN PASS
  Reader    the same traffic class costs the origin less, then more, as only its
            reachable set grows.
  Encoding  a ladder: one row per reachable set (each step ~x3), a bar from a zero
            line, keys left and values right. Sign is read from the side of the
            zero line before any number is read.
  Dominant  the zero line and the three bars.
  Secondary values and SE in their own column; object counts under the keys;
            the honeypot reference as a short tag on the row it refers to.
            Load range, runs and the net-effect caveat go to the caption.
  Prevent   "agentic traffic reduces origin work" (retracted, R2): the bar is the
            12->36 req/s marginal, the axis says "marginal, not net", the header
            names the direction of the origin rate and not "work"; the net 0->36
            effect (A9) is in the text, and the caption says so. No line joins the rows (3 points, no functional form).
            No "working set = capacity" boundary (retracted, R4).
"""
import figure_style as S
from figure_style import C, T, PT, SEMIBOLD

STEM = "FIG-01_marginal-cost-vs-working-set"
CLAIMS = "A1 (MISURATO); refs C2, C3"
DATA = ["fig01_marginal_vs_workingset.csv"]
RUNS = ["tre-20260928-150154", "tre-20260928-162206", "tre-20260929-064412",
        "tre-20260929-080424", "tre-20260929-092436", "tre-20260929-104448"]

EDITORIAL = dict(
    headline="What an extra agentic request costs the origin\ndepends on its reachable set",
    deck="Origin requests caused by each added agentic request, at three reachable-set sizes. "
         "Traffic\nvolumes, cache and corpus are held fixed; only the reachable set changes.",
    source="Source: Undertow testbed, mean of 5 runs per row, whiskers ± 1 SE; agentic "
           "load raised from 12 to 36 req/s.\nReal agents: theslowshelf.org honeypot, p90 of "
           "distinct objects per 143 s window, 12 Aug – 21 Sep 2026.",
)

CAPTION = (
    "Marginal origin cost of the agentic class at three reachable-set sizes. In each row the "
    "agentic class is raised from 12 to 36 req/s (13% to 30% of load) while the human and "
    "exhaustive classes stay fixed at 55 and 28 req/s; only the scope from which agentic "
    "sessions are drawn changes. Rows give the reachable set (the distinct chapters the "
    "generator can request for the class) as a multiple of the measured cache capacity of "
    "5,263 objects. Bars: mean of 5 runs; whiskers: ± 1 SE, smaller than the bar ends. The "
    "values are marginal between 12 and 36 req/s, not the net effect of adding the class, "
    "which is reported in the text. The tag marks the row closest to real agents by windowed "
    "working set (distinct objects within 143 s: honeypot 90th percentile 670, about 693 for "
    "that row), not by the size of the reachable set. Reachable sets are separated across "
    "classes (AGENT_MUL = 3266489917); the exhaustive class runs as its own k6 scenario."
)

XMIN, XMAX = -0.10, 0.50
TICKS = [-0.1, 0, 0.1, 0.2, 0.3, 0.4, 0.5]


def render(variant):
    sp = S.Spec(variant)
    rows = S.read_csv(DATA[0])
    key_w = sp.pick(0.74, 1.00, 1.16)
    val_w = sp.pick(0.46, 0.58, 0.66)
    row_h = sp.pick(0.34, 0.40, 0.44)
    gut   = sp.pick(0.08, 0.12, 0.14)

    head_h = T.s(T.sub) * 1.2 * PT + 0.06
    tick_h = 0.05 + T.s(T.tick) * 1.25 * PT
    xt_h   = 0.0 if sp.editorial else 0.06 + T.s(T.axis) * 1.3 * PT
    body_h = head_h + 0.04 + 3 * row_h + tick_h + xt_h

    cv = S.Canvas(sp, body_h, **EDITORIAL)
    top = cv.top
    bx = cv.left + key_w + gut
    bw = cv.right - val_w - gut - bx

    y_rule = top + head_h
    y_rows = y_rule + 0.04
    y_end = y_rows + 3 * row_h
    f = cv.frame(bx, y_rule, bw, y_end - y_rule, (XMIN, XMAX), (y_end, y_rule))
    x0 = f.X(0)

    # header: column heads, and the direction of the axis flanking its zero line
    y_head = top + T.s(T.sub) * 0.95 * PT
    hd = dict(color=C.ink_soft, va="baseline")
    cv.text(cv.left, y_head, "Reachable set", T.sub, weight=SEMIBOLD, ha="left", **hd)
    cv.text(cv.right, y_head, "Mean ± SE", T.sub, weight=SEMIBOLD, ha="right", **hd)
    cv.text(x0 - 0.06, y_head, sp.pick("lower", "lower origin rate"), T.sub,
            ha="right", **hd)
    cv.text(x0 + 0.06, y_head, sp.pick("higher", "higher origin rate"), T.sub, ha="left", **hd)
    cv.line([cv.left, cv.right], [y_rule, y_rule], color=C.rule_mid, lw=0.5)
    cv.line([x0, x0], [y_head - T.s(T.sub) * 0.8 * PT, y_rule], color=C.baseline, lw=1.0)

    # plot layer (y unit = inches from the top)
    f.vgrid([t for t in TICKS if t != 0], y0=y_end, y1=y_rule)
    f.vbase(0, lw=1.0)
    bar_h = row_h * 0.40
    for i, r in enumerate(rows):
        yc = y_rows + (i + 0.5) * row_h
        v, se = float(r["marginal"]), float(r["marginal_se"])
        f.ax.barh(yc, v, height=bar_h, color=C.agentic, lw=0, zorder=2)
        f.whisker(v, yc, se, axis="x", cap=bar_h / PT * 0.22)

        cv.text(cv.left, yc - 0.01, f"{float(r['W_over_capacity']):.2f}× cache",
                T.key, ha="left", va="bottom")
        cv.text(cv.left, yc + 0.028, f"{int(r['W_objects']):,} objects", T.sub,
                color=C.ink_faint, ha="left", va="top")
        cv.text(cv.right, yc - 0.01, S.num(v, 3, sign=True), T.value, weight=SEMIBOLD,
                ha="right", va="bottom")
        cv.text(cv.right, yc + 0.028, "± " + S.num(se, 3), T.sub,
                color=C.ink_faint, ha="right", va="top")

    # the single annotation: a tag on the row it refers to
    yc0 = y_rows + 0.5 * row_h
    cv.text(x0 + 0.08, yc0, "closest to real agents", T.sub, color=C.ink_soft,
            ha="left", va="center",
            bbox=dict(boxstyle="square,pad=0.15", fc=C.surface, ec="none"))

    # scale
    for t in TICKS:
        cv.text(f.X(t), y_end + 0.05, "0" if t == 0 else S.num(t, 1, sign=True), T.tick,
                color=C.ink_faint, ha="center", va="top")
    if not sp.editorial:
        cv.text(bx + bw / 2, y_end + tick_h + 0.05,
                "Origin requests per added agentic request (marginal, not net)", T.axis,
                color=C.ink_soft, ha="center", va="top")
    return cv.save(STEM)
