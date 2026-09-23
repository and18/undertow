"""
FIG-05 — Where the change in origin work comes from, term by term.

CLAIM     B2 (MISURATO). Supports A1 (sign of the 12->36 step) without restating it.
DATA      data/derived/fig05_accounting.csv
RUNS      tre-20260921-150237 / -162248 (separated mapping, scope 0.02) and the
          agentic = 0 baseline of 20 Sep (inter-day, see caption).

DESIGN PASS
  Reader    in the second step the largest term is the agentic requests already
            present becoming cheaper; the terms add up to what was measured.
  Encoding  a horizontal waterfall per step: each term floats from where the
            previous one ended, the sum is a neutral bar from zero, the measurement
            a marker with its whisker right under it. Same scale in both panels.
  Dominant  the long negative bar of "agentic requests already present" in step b.
  Secondary term values on the bars; the net 0->36 effect as one line under the
            panels.
  Prevent   "adding agentic traffic reduces origin work" (retracted, R2): step a is
            shown next to step b and the net 0->36 effect (+0.392) is printed.
"""
import figure_style as S
from figure_style import C, T, PT, SEMIBOLD

STEM = "FIG-05_accounting-decomposition"
CLAIMS = "B2 (MISURATO)"
DATA = ["fig05_accounting.csv"]
RUNS = ["tre-20260921-150237", "tre-20260921-162248", "agentic=0 baseline 2026-09-20"]

EDITORIAL = dict(
    headline="Past 12 req/s, the largest term is the agentic requests\nalready present becoming cheaper",
    deck="Change in origin requests per second, split by the class that causes it, for two "
         "steps of\nagentic load at the smallest working set. Terms add up to the measured change.",
    source="Source: Undertow testbed, separated working sets, scope 0.02; measured change: mean "
           "of 5 runs, whisker ± 1 SE.",
)

CAPTION = (
    "Accounting decomposition of the change in origin work at the smallest agentic working "
    "set (scope 0.02, separated mapping), for the steps 0 → 12 and 12 → 36 agentic "
    "req/s with human and exhaustive volumes fixed. Each bar is the contribution of one term "
    "to the change in origin requests per second and starts where the previous one ends; "
    "the grey bar is their sum and the marker the measured change (mean of 5 runs, ± 1 "
    "SE). The sum matches the measurement to within 0% (step a) and 5% (step b). In step b "
    "the largest term is the lower miss ratio of the 12 agentic req/s already present "
    "(−1.632). The net effect from 0 to 36 req/s is positive (+0.392 ± 0.158); the "
    "0 req/s point is an inter-day baseline."
)

TERMS = [("new agentic requests", "New agentic requests", "New agentic", C.agentic),
         ("agentic requests already present", "Agentic already present", "Agentic present", C.agentic),
         ("human class", "Human class", "Human", C.human),
         ("exhaustive class", "Exhaustive class", "Exhaustive", C.exhaustive)]
XLIM = (-1.25, 2.75)


def _vals(rows, step):
    return {r["term"]: float(r["value"]) for r in rows if r["step"] == step}


def _panel(cv, sp, x, y, w, rows_h, step, v, letter, title, show_keys, key_w):
    cv.panel_title(x if show_keys else x + key_w, y + T.s(T.panel) * 0.95 * PT, letter, title)
    top = y + T.s(T.panel) * 1.2 * PT + 0.14
    n = 6
    rh = rows_h / n
    f = cv.frame(x + key_w, top, w - key_w, rows_h, XLIM, (rows_h, 0))
    f.vgrid([-1, 1, 2])
    f.vbase(0, lw=0.9, z=1.5)          # under the bars that cross it
    bh = rh * 0.56
    cum = 0.0
    for i, (term, long, short, col) in enumerate(TERMS):
        yc = (i + 0.5) * rh
        d = v[term]
        a, b = cum, cum + d
        if d != 0:
            f.ax.barh(yc, b - a, left=a, height=bh, color=col, lw=0, zorder=2)
        # connector to the next row
        f.ax.plot([b, b], [yc + bh / 2, yc + rh - bh / 2], color=C.rule_mid, lw=0.5,
                  zorder=1)
        _value(f, sp, a, b, yc, d, col)
        if show_keys:
            cv.text(x, f.at(0, yc)[1], sp.pick(short, long), T.key, ha="left", va="center")
        cum = b
    # sum of terms
    yc = 4.5 * rh
    tot = v["sum of terms"]
    f.ax.barh(yc, tot, left=0, height=bh, color=C.neutral, lw=0, zorder=2)
    _value(f, sp, 0, tot, yc, tot, C.neutral)
    # measured
    yc = 5.5 * rh
    m, se = v["measured"], v["measured_se"]
    f.whisker(m, yc, se, axis="x")
    f.dot(m, yc, C.ink, marker="D", size=4.4 * T.base / 8.4, ring=False)
    f.label(m + se, yc, f"{S.num(m, 3, sign=True)} ± {S.num(se, 3)}", T.sub,
            dx=4, ha="left", va="center", color=C.ink, bbox=S.KNOCKOUT)
    if show_keys:
        for i, (lab_l, lab_s) in ((4, ("Sum of terms", "Sum")), (5, ("Measured", "Measured"))):
            cv.text(x, f.at(0, (i + 0.5) * rh)[1], sp.pick(lab_s, lab_l), T.key,
                    ha="left", va="center", weight=SEMIBOLD if i == 5 else 400)
    return f


def _value(f, sp, a, b, yc, d, col):
    """Value on the bar if it fits (white or ink by fill lightness), else outside."""
    s = "0" if d == 0 else S.num(d, 3, sign=True)
    w_in = abs(f.X(b) - f.X(a))
    tw = S.text_w(s, T.sub) + 0.06
    if w_in >= tw:
        colour = C.surface if col == C.agentic else C.ink
        f.label((a + b) / 2, yc, s, T.sub, ha="center", va="center", color=colour)
    elif d >= 0:
        f.label(max(a, b), yc, s, T.sub, dx=3, ha="left", va="center", color=C.ink,
                bbox=S.KNOCKOUT)
    else:
        f.label(min(a, b), yc, s, T.sub, dx=-3, ha="right", va="center", color=C.ink,
                bbox=S.KNOCKOUT)


def render(variant):
    sp = S.Spec(variant)
    rows = S.read_csv(DATA[0])
    va_, vb_ = _vals(rows, "0-12"), _vals(rows, "12-36")
    net = _vals(rows, "0-36")
    key_w = sp.pick(0.82, 1.18, 1.34)
    rows_h = sp.pick(1.30, 1.40, 1.50)
    title_h = T.s(T.panel) * 1.2 * PT + 0.14
    axis_h = 0.05 + T.s(T.tick) * 1.25 * PT + 0.06 + T.s(T.axis) * 1.3 * PT
    net_h = 0.10 + T.s(T.label) * 1.3 * PT
    if sp.narrow:
        body_h = 2 * (title_h + rows_h + axis_h) + 0.18 + net_h
    else:
        body_h = title_h + rows_h + axis_h + net_h
    cv = S.Canvas(sp, body_h, **EDITORIAL)
    L, W, top = cv.left, cv.width, cv.top
    panels = []
    if sp.narrow:
        y = top
        for letter, title, v in (("a", "0 → 12 agentic req/s", va_),
                                 ("b", "12 → 36 agentic req/s", vb_)):
            panels.append(_panel(cv, sp, L, y, W, rows_h, None, v, letter, title, True, key_w))
            y += title_h + rows_h + axis_h + 0.18
        y_net = y - 0.18 + 0.04
    else:
        gap = sp.pick(None, 0.22, 0.30)
        pw = (W - key_w - gap) / 2
        panels.append(_panel(cv, sp, L, top, key_w + pw, rows_h, None, va_, "a",
                             "0 → 12 agentic req/s", True, key_w))
        panels.append(_panel(cv, sp, L + key_w + pw + gap, top, pw, rows_h, None, vb_, "b",
                             "12 → 36 agentic req/s", False, 0))
        y_net = top + title_h + rows_h + axis_h + 0.04
    for f in panels:
        f.xticks([-1, 0, 1, 2], [S.num(t, 0, sign=True) if t else "0" for t in (-1, 0, 1, 2)])
        f.xtitle("Change in origin req/s")
    cv.text(L, y_net + 0.06, f"Net change from 0 to 36 agentic req/s: "
            f"{S.num(net['net'], 3, sign=True)} ± {S.num(net['net_se'], 3)} origin req/s",
            T.label, color=C.ink_soft, ha="left", va="top")
    return cv.save(STEM)
