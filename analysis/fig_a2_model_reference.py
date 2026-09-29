"""
FIG-A2 — The prior characteristic-time prediction got the direction right
and the size wrong.

CLAIMS    B3 (RESPINTO): quantitative prediction failed (criterion 3).
          B4 (INTERPRETATIVO): ordering and direction hold (4.05 > 1.62 > 1.16).
DATA      data/derived/figA2_elasticity_model.csv
SOURCES   docs/PREREGISTRAZIONE-scopesweep.md (a prediction written before the first
          results at scopes 0.06 and 0.20 were available, not independently timestamped);
          docs/RISULTATO-scopesweep.md. The post-hoc recomputation (column
          posthoc_realdist of the CSV) is no longer drawn: it has no row in claims.md
          (28 Sep 2026).

DESIGN PASS
  Reader    observed elasticity falls with the reachable set, as the model said, but
            at 0.58x cache it falls outside the +/-30% tolerance stated with the prediction.
  Encoding  a dot plot per reachable set on a log axis (elasticity is a ratio):
            observed = filled, class colour; prior prediction = hollow, with its
            tolerance as a wash band.
  Dominant  the observed dots against the tolerance bands.
  Secondary numeric values next to each mark; a verdict at the end of each row.
  Prevent   showing values without a row in claims.md (the post-hoc recomputation),
            and reading the model as validated (the failed row says so).
"""
import figure_style as S
from figure_style import C, T, PT, SEMIBOLD

STEM = "FIG-A2_model-reference"
CLAIMS = "B3 (RESPINTO); B4 (INTERPRETATIVO)"
DATA = ["figA2_elasticity_model.csv"]
RUNS = ["tre-20260928-150154", "tre-20260928-162206", "tre-20260929-064412",
        "tre-20260929-080424", "tre-20260929-092436", "tre-20260929-104448"]

EDITORIAL = dict(
    headline="The prior model got the direction right\nand the size wrong",
    deck="Elasticity of the agentic miss ratio (miss at 12 req/s over miss at 36 req/s) at "
         "three reachable-set\nsizes: observed against the prior prediction of the model.",
    source="Source: Undertow testbed, mean of 5 runs; prior prediction of 21 Sep 2026, written "
           "before the first results\nat scopes 0.06 and 0.20 were available, not independently "
           "timestamped.",
)

def _caption():
    """Every number in the caption is computed from the CSV the figure draws."""
    rows = S.read_csv(DATA[0])
    fail = [r for r in rows if r["prior"]
            and abs(float(r["observed"]) / float(r["prior"]) - 1) > float(r["tolerance"])]
    r = fail[0]
    obs, pri = float(r["observed"]), float(r["prior"])
    return (
        "Characteristic-time approximation (Fagin 1977; Che et al. 2002; formalised by Fricker "
        "et al. 2012) against observed elasticity of the agentic miss ratio, defined as the miss "
        "ratio at 12 req/s over that at 36 req/s. Hollow circles: a prior prediction with a "
        "uniform access approximation, written before the first results at scopes 0.06 and "
        "0.20 were available and not independently timestamped, with the \u00b130% tolerance "
        "stated with it (band); the first row is the anchor: that scope had already been "
        "measured, in earlier runs, when the prediction was written. Filled circles: observed "
        "with the exhaustive class in its own k6 scenario, mean of 5 runs. The ordering predicted by the "
        f"model holds; the quantitative criterion fails at {S.num(float(r['W_over_capacity']), 2)}\u00d7 "
        f"cache ({S.num(obs, 2)} against {S.num(pri, 1)}, "
        f"{S.num(100 * (obs / pri - 1), 0)}%).")


CAPTION = _caption()


def render(variant):
    sp = S.Spec(variant)
    rows = S.read_csv(DATA[0])
    key_w = sp.pick(0.62, 0.86, 0.96)
    ver_w = sp.pick(0.66, 0.92, 1.02)
    row_h = sp.pick(0.50, 0.52, 0.56)
    leg_h = T.s(T.sub) * 1.45 * PT + 0.14
    below = 0.05 + T.s(T.tick) * 1.25 * PT + 0.06 + T.s(T.axis) * 1.3 * PT
    cv = S.Canvas(sp, leg_h + 3 * row_h + below, **EDITORIAL)
    top = cv.top
    fx = cv.left + key_w
    fw = cv.right - ver_w - fx
    f = cv.frame(fx, top + leg_h, fw, 3 * row_h, (0.9, 6), (3 * row_h, 0), xlog=True)
    xt = [1, 2, 3, 5]
    f.vgrid(xt)
    f.xticks(xt, [str(v) for v in xt])
    f.xtitle(sp.pick("Miss at 12 req/s ÷ miss at 36 req/s (log)",
                     "Elasticity: miss at 12 req/s ÷ miss at 36 req/s (log scale)"))

    ms = 5.6 * T.base / 8.4
    for i, r in enumerate(rows):
        yc = (i + 0.5) * row_h
        obs = float(r["observed"])
        pre = float(r["prior"]) if r["prior"] else None
        if pre:
            tol = float(r["tolerance"])
            f.ax.fill_betweenx([yc - row_h * 0.24, yc + row_h * 0.24], pre * (1 - tol),
                               pre * (1 + tol), color=C.wash, lw=0, zorder=1)
            f.dot(pre, yc, C.ink_soft, hollow=True, size=ms * 0.95)
            # the predicted value sits at the end of its own band, clear of the others
            f.label(pre * (1 + tol), yc, S.num(pre, 1), T.sub, dx=4, ha="left",
                    va="center", color=C.ink_faint)
        f.dot(obs, yc, C.agentic, size=ms * 1.15)
        f.label(obs, yc, S.num(obs, 2), T.value, dy=6, ha="center", va="bottom",
                weight=SEMIBOLD)
        y_in = f.at(1, yc)[1]
        cv.text(cv.left, y_in, f"{float(r['W_over_capacity']):.2f}× cache", T.key,
                ha="left", va="center")
        if not pre:
            verdict, wt = "anchor", 400
        else:
            inside = abs(obs / pre - 1) <= float(r["tolerance"])
            verdict, wt = ("within ±30%", 400) if inside else ("outside ±30%", SEMIBOLD)
        cv.text(cv.right, y_in, verdict, T.label, ha="right", va="center", weight=wt,
                color=C.ink if wt == SEMIBOLD else C.ink_soft)

    # key
    ky = top + T.s(T.sub) * 0.7 * PT
    entries = [(C.agentic, "o", False, "observed"),
               (C.ink_soft, "o", True, "prior prediction, ±30% band")]
    x = fx
    for col, mk, hollow, text in entries:
        cv.fig.add_artist(S.mpl.lines.Line2D(
            [cv.fx(x + 0.04)], [cv.fy(ky)], marker=mk, ms=4.6 * T.base / 8.4, ls="none",
            mfc=C.surface if hollow else col, mec=col, mew=1.2 if hollow else 0))
        cv.text(x + 0.11, ky, text, T.sub, color=C.ink_soft, ha="left", va="center")
        x += 0.11 + S.text_w(text, T.sub) + 0.18
    return cv.save(STEM)
