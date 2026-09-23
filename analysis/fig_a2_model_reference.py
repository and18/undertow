"""
FIG-A2 — The pre-registered characteristic-time prediction got the direction right
and the size wrong.

CLAIMS    B3 (RESPINTO): quantitative prediction failed (criterion 3).
          B4 (INTERPRETATIVO): ordering and direction hold (4.05 > 1.63 > 1.16).
DATA      data/derived/figA2_elasticity_model.csv
SOURCES   docs/PREREGISTRAZIONE-scopesweep.md (written before the runs, unmodified);
          docs/RISULTATO-scopesweep.md (post-hoc computation, labelled as such).

DESIGN PASS
  Reader    observed elasticity falls with the working set, as the model said, but
            at 0.58x cache it falls outside the registered +/-30% tolerance.
  Encoding  a dot plot per working set on a log axis (elasticity is a ratio):
            observed = filled, class colour; pre-registered = hollow, with its
            tolerance as a wash band; post-hoc model = grey diamond.
  Dominant  the observed dots against the tolerance bands.
  Secondary numeric values next to each mark; a verdict at the end of each row.
  Prevent   passing the post-hoc curve off as a prediction (it is labelled post hoc
            everywhere), and reading the model as validated (the failed row says so).
"""
import figure_style as S
from figure_style import C, T, PT, SEMIBOLD

STEM = "FIG-A2_model-reference"
CLAIMS = "B3 (RESPINTO); B4 (INTERPRETATIVO)"
DATA = ["figA2_elasticity_model.csv"]
RUNS = ["as FIG-01 (observed values)"]

EDITORIAL = dict(
    headline="The pre-registered model got the direction right\nand the size wrong",
    deck="Elasticity of the agentic miss ratio (miss at 12 req/s over miss at 36 req/s) at "
         "three working-set\nsizes: observed, pre-registered prediction, and a post-hoc "
         "recomputation of the same model.",
    source="Source: Undertow testbed, mean of 5 runs; pre-registration of 21 Sep 2026, "
           "written before the runs.",
)

CAPTION = (
    "Characteristic-time approximation (Fagin 1977; Che et al. 2002; formalised by Fricker "
    "et al. 2012) against observed elasticity of the agentic miss ratio, defined as the miss "
    "ratio at 12 req/s over that at 36 req/s. Hollow circles: predictions registered before "
    "the runs with a uniform access approximation, with the registered ±30% tolerance "
    "(band); the first row was measured before registration and serves as anchor. Grey "
    "diamonds: post-hoc recomputation with the generator's actual access distribution, not a "
    "prediction. Filled circles: observed, mean of 5 runs. The ordering predicted by the "
    "model holds; the quantitative criterion fails at 0.58× cache (1.63 against 3.1, "
    "−47%)."
)


def render(variant):
    sp = S.Spec(variant)
    rows = S.read_csv(DATA[0])
    key_w = sp.pick(0.62, 0.86, 0.96)
    ver_w = sp.pick(0.66, 0.92, 1.02)
    row_h = sp.pick(0.50, 0.52, 0.56)
    leg_h = (2 if sp.narrow else 1) * T.s(T.sub) * 1.45 * PT + 0.14
    below = 0.05 + T.s(T.tick) * 1.25 * PT + 0.06 + T.s(T.axis) * 1.3 * PT
    cv = S.Canvas(sp, leg_h + 3 * row_h + below, **EDITORIAL)
    top = cv.top
    fx = cv.left + key_w
    fw = cv.right - ver_w - fx
    f = cv.frame(fx, top + leg_h, fw, 3 * row_h, (0.9, 11), (3 * row_h, 0), xlog=True)
    xt = [1, 2, 3, 5, 10]
    f.vgrid(xt)
    f.xticks(xt, [str(v) for v in xt])
    f.xtitle(sp.pick("Miss at 12 req/s ÷ miss at 36 req/s (log)",
                     "Elasticity: miss at 12 req/s ÷ miss at 36 req/s (log scale)"))

    ms = 5.6 * T.base / 8.4
    for i, r in enumerate(rows):
        yc = (i + 0.5) * row_h
        obs, post = float(r["observed"]), float(r["posthoc_realdist"])
        pre = float(r["preregistered"]) if r["preregistered"] else None
        if pre:
            tol = float(r["tolerance"])
            f.ax.fill_betweenx([yc - row_h * 0.24, yc + row_h * 0.24], pre * (1 - tol),
                               pre * (1 + tol), color=C.wash, lw=0, zorder=1)
            f.dot(pre, yc, C.ink_soft, hollow=True, size=ms * 0.95)
            # the registered value sits at the end of its own band, clear of the others
            f.label(pre * (1 + tol), yc, S.num(pre, 1), T.sub, dx=4, ha="left",
                    va="center", color=C.ink_faint)
        f.dot(post, yc, C.neutral, marker="D", size=ms * 0.85)
        f.label(post, yc, S.num(post, 2), T.sub, dy=-6, ha="center", va="top",
                color=C.ink_faint)
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
               (C.ink_soft, "o", True, "pre-registered, ±30% band"),
               (C.neutral, "D", False, "post-hoc recomputation")]
    x = fx
    for i, (col, mk, hollow, text) in enumerate(entries):
        if sp.narrow and i == 2:
            x, ky = fx, ky + T.s(T.sub) * 1.45 * PT
        cv.fig.add_artist(S.mpl.lines.Line2D(
            [cv.fx(x + 0.04)], [cv.fy(ky)], marker=mk, ms=4.6 * T.base / 8.4, ls="none",
            mfc=C.surface if hollow else col, mec=col, mew=1.2 if hollow else 0))
        cv.text(x + 0.11, ky, text, T.sub, color=C.ink_soft, ha="left", va="center")
        x += 0.11 + S.text_w(text, T.sub) + 0.18
    return cv.save(STEM)
