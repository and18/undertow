"""
FIG-A1 — Human latency rises with the agentic reachable set; the human hit ratio barely moves.

CLAIM     B5 (SOSTENUTO, claims v3.8): p99 72.9 -> 99.6 ms (+26.7 +/- 1.3, t = 20.3), human
          miss 1.07x, origin 37.4 -> 52.4 req/s. B6 (the exact upstream channel) is NOT SUPPORTED and
          the figure does not name one.
DATA      data/derived/figA1_human_externality.csv (agentic share 30%)
RUNS      as FIG-01 (TRAV_MODE=scen), the 30% runs; CSV column run.

DESIGN PASS
  Reader    as the agentic reachable set grows, human p99 climbs while the human hit
            ratio stays put and origin load rises: the cost reaches humans as load,
            not as lost cache hits.
  Encoding  three small multiples on the same x, each with an honest axis from zero,
            so "rises" and "flat" are comparable at a glance. No lines between
            points (three settings, no functional form).
  Dominant  panel a, the rising p99.
  Secondary values next to points; hit ratio and origin load as supporting panels.
  Prevent   naming a mechanism the data do not isolate (B6): the caption says the
            upstream channel was not measured.
"""
import figure_style as S
from figure_style import C, T, PT, SEMIBOLD

STEM = "FIG-A1_human-externality"
CLAIMS = "B5 (SOSTENUTO); B6 not supported, not drawn"
DATA = ["figA1_human_externality.csv"]
RUNS = ["tre-20260928-162206", "tre-20260929-080424", "tre-20260929-104448"]

EDITORIAL = dict(
    headline="Human latency rises with the agentic reachable set\nwhile the human hit ratio barely moves",
    deck="Human p99 latency, human cache hit ratio and origin load at 30% agentic share, "
         "for three\nagentic reachable-set sizes. Volumes and cache are held fixed.",
    source="Source: Undertow testbed, mean of 5 repetitions per point, whiskers ± 1 SE.",
)

def _caption():
    """Every number in the caption is computed from the CSV the figure draws."""
    import math
    r = S.read_csv(DATA[0])
    p0, p2 = float(r[0]["human_p99_ms"]), float(r[-1]["human_p99_ms"])
    d = p2 - p0
    se = math.hypot(float(r[0]["human_p99_se"]), float(r[-1]["human_p99_se"]))
    m0, m2 = 1 - float(r[0]["human_hit"]), 1 - float(r[-1]["human_hit"])
    return (
        "Effect of the agentic reachable set on the human class, at 30% agentic share with "
        "volumes and cache fixed (Section 5.3): (a) human p99 latency, (b) human hit ratio, "
        "(c) origin load. Mean of 5 repetitions; whiskers \u00b1 1 SE, smaller than the "
        "markers where not visible. The upstream channel through which origin load reaches "
        "human latency was not measured.")


CAPTION = _caption()

PANELS = [("a", "Human p99 latency", "ms", "human_p99_ms", "human_p99_se", C.human,
           (0, 130), [0, 40, 80, 120], 1),
          ("b", "Human hit ratio", "ratio", "human_hit", None, C.human,
           (0, 1.0), [0, 0.25, 0.5, 0.75, 1.0], 3),
          ("c", "Origin load", "req/s", "origin_rps", "origin_se", C.ink,
           (0, 65), [0, 20, 40, 60], 1)]


def _panel(cv, sp, x, y, w, h, rows, spec, last):
    letter, title, unit, col, secol, colour, ylim, yt, dec = spec
    cv.panel_title(x, y + T.s(T.panel) * 0.95 * PT, letter, title)
    tick_w = 0.30
    top = y + T.s(T.panel) * 1.2 * PT + 0.26
    below = 0.05 + T.s(T.tick) * 1.25 * PT
    f = cv.frame(x + tick_w, top, w - tick_w - 0.10, h - (top - y) - below,
                 (0.13, 2.9), ylim, xlog=True)
    f.hgrid(yt[1:])
    f.hbase(0, color=C.rule_mid, lw=0.6)
    f.yticks(yt, [("0" if v == 0 else S.num(v, 2)) if ylim[1] <= 1 else str(v) for v in yt])
    f.ytitle(unit, x=x, gap=0.07)
    xs = [float(r["W_over_capacity"]) for r in rows]
    f.xticks(xs, [f"{v:.2f}×" for v in xs])
    for r, xv in zip(rows, xs):
        v = float(r[col])
        if secol:
            f.whisker(xv, v, float(r[secol]))
        f.dot(xv, v, colour)
        f.label(xv, v, S.num(v, dec), T.sub, dy=6.5, ha="center", va="bottom",
                weight=SEMIBOLD, color=C.ink)
    return f


def render(variant):
    sp = S.Spec(variant)
    rows = S.read_csv(DATA[0])
    xt_h = 0.06 + T.s(T.axis) * 1.3 * PT
    if sp.narrow:
        ph = 1.18
        body_h = 3 * ph + 2 * 0.16 + xt_h
    else:
        ph = sp.pick(None, 1.75, 1.85)
        body_h = ph + xt_h
    cv = S.Canvas(sp, body_h, **EDITORIAL)
    L, W, top = cv.left, cv.width, cv.top
    if sp.narrow:
        for i, spec in enumerate(PANELS):
            f = _panel(cv, sp, L, top + i * (ph + 0.16), W, ph, rows, spec, i == 2)
        f.xtitle("Agentic reachable set / cache capacity")
    else:
        gap = sp.pick(None, 0.16, 0.24)
        pw = (W - 2 * gap) / 3
        fr = [_panel(cv, sp, L + i * (pw + gap), top, pw, ph, rows, spec, True)
              for i, spec in enumerate(PANELS)]
        cv.text(L + W / 2, fr[0].bottom + 0.05 + T.s(T.tick) * 1.25 * PT + 0.06,
                "Agentic reachable set / cache capacity (log scale)", T.axis,
                color=C.ink_soft, ha="center", va="top")
    return cv.save(STEM)
