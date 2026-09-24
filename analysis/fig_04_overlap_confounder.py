"""
FIG-04 — Sharing the popular head with human traffic makes the agentic class look cheaper.

CLAIM     A3 (MISURATO).
DATA      data/derived/fig04_overlap.csv
RUNS      shared mapping: tre-20260920-114026 / -130038 of 20 Sep (AGENT_MUL not passed to
          k6, so the default permutation: same permutation as the human class; before env.txt)
          separated mapping: tre-20260921-150237 / -162248 (AGENT_MUL=3266489917)

DESIGN PASS
  Reader    removing the overlap raises measured origin work at both agentic loads:
            a measurement that ignores overlap underestimates the class's cost.
  Encoding  a dumbbell per load: hollow = shared (confounded), filled = separated;
            the shift between them is the effect, labelled with its size and t.
  Dominant  the two shifts to the right.
  Secondary agentic hit ratios under the row keys; mapping details in the key line;
            overlap statistics and run IDs in the caption.
  Prevent   reading the shift as "agents are cheaper in the real world": it is a
            bias of the experimental characterisation, and the headline and caption
            say "look cheaper"; not claiming to have discovered free-riding.
"""
import figure_style as S
from figure_style import C, T, PT, SEMIBOLD

STEM = "FIG-04_overlap-confounder"
CLAIMS = "A3 (MISURATO)"
DATA = ["fig04_overlap.csv"]
RUNS = ["tre-20260920-114026", "tre-20260920-130038", "tre-20260921-150237",
        "tre-20260921-162248"]

EDITORIAL = dict(
    headline="Sharing the popular head with human traffic\nmakes the agentic class look cheaper",
    deck="Origin requests per second with the agentic working set inside the human popular "
         "head\n(shared) and decorrelated from it (separated), at two agentic loads.",
    source="Source: Undertow testbed, mean of 5 runs per point, whiskers ± 1 SE; "
           "human 55 req/s and exhaustive 28 req/s fixed.",
)

def _row(rows, load, mapping):
    return next(r for r in rows if int(r["agent_rps"]) == load and r["mapping"] == mapping)


def _caption():
    """Every number in the caption is computed from the CSV the figure draws."""
    r = S.read_csv(DATA[0])
    sh, se = _row(r, 12, "shared"), _row(r, 12, "separated")
    e12, e36 = se, _row(r, 36, "separated")
    h = {k: S.num(float(_row(r, *k)["agent_hit"]), 3)
         for k in ((12, "shared"), (12, "separated"), (36, "shared"), (36, "separated"))}
    return (
        "Effect of working-set overlap on measured origin work. Shared: the agentic working "
        "set is drawn with the same permutation as the human one, so its bases coincide with "
        f"the human popular head (overlap {S.num(float(sh['overlap_pct']), 1)}%; the human "
        "generator never draws rank 0); "
        f"{S.num(float(sh['human_mass_pct']), 1)}% of human traffic falls on agentic bases. "
        "Separated: a different permutation (AGENT_MUL = 3266489917) reduces the overlap to "
        f"{S.num(float(se['overlap_pct']), 1)}% and that share of human traffic to "
        f"{S.num(float(se['human_mass_pct']), 1)}%. Removing the overlap raises origin work by "
        f"{S.num(float(e12['effect']), 3, sign=True)} req/s (t = {S.num(float(e12['t']), 2)}) "
        f"at 12 agentic req/s and {S.num(float(e36['effect']), 3, sign=True)} req/s "
        f"(t = {S.num(float(e36['t']), 2)}) at 36, and lowers the agentic hit ratio from "
        f"{h[(12, 'shared')]} to {h[(12, 'separated')]} and from {h[(36, 'shared')]} to "
        f"{h[(36, 'separated')]}. Mean of 5 runs; whiskers ± 1 SE. The shared runs are of "
        "20 Sep 2026, the separated runs of 21 Sep. The overlap is a bias of the "
        "experimental characterisation of a class's cost, not a property of the class."
    )


CAPTION = _caption()


def render(variant):
    sp = S.Spec(variant)
    rows = S.read_csv(DATA[0])
    key_w = sp.pick(0.86, 1.06, 1.20)
    row_h = sp.pick(0.50, 0.54, 0.58)
    ov = {m: S.num(float(_row(rows, 12, m)["overlap_pct"]), 1) for m in ("shared", "separated")}
    keys = ((True, f"shared popular head, overlap {ov['shared']}%"),
            (False, f"separated, overlap {ov['separated']}%"))
    one_line = (0.11 + S.text_w(keys[0][1], T.sub) + 0.20 + 0.11
                + S.text_w(keys[1][1], T.sub)) < (sp.w - 2 * S.Canvas.MARGIN[sp.mode] - key_w)
    n_key = 1 if one_line else 2
    legend_h = n_key * T.s(T.sub) * 1.4 * PT + 0.12
    below = 0.05 + T.s(T.tick) * 1.25 * PT + 0.06 + T.s(T.axis) * 1.3 * PT
    body_h = legend_h + 2 * row_h + below
    cv = S.Canvas(sp, body_h, **EDITORIAL)
    top = cv.top
    fx = cv.left + key_w
    f = cv.frame(fx, top + legend_h, cv.right - fx - 0.06, 2 * row_h, (35.4, 38.1),
                 (2 * row_h, 0))
    xt = [35.5, 36.0, 36.5, 37.0, 37.5, 38.0]
    f.vgrid(xt)
    f.xticks(xt, [S.num(v, 1) for v in xt])
    f.xtitle("Origin requests per second")

    # key line
    ky = top + T.s(T.sub) * 0.7 * PT
    x = fx
    for hollow, text in keys:
        cv.fig.add_artist(S.mpl.lines.Line2D(
            [cv.fx(x + 0.04)], [cv.fy(ky)], marker="o", ms=5.0 * T.base / 8.4, ls="none",
            mfc=C.surface if hollow else C.agentic, mec=C.agentic,
            mew=1.25 if hollow else 0))
        t = cv.text(x + 0.11, ky, text, T.sub, color=C.ink_soft, ha="left", va="center")
        if one_line:
            x += 0.11 + S.text_w(text, T.sub) + 0.20
        else:
            ky += T.s(T.sub) * 1.4 * PT

    for i, load in enumerate((12, 36)):
        yc = (i + 0.5) * row_h
        sh, se = _row(rows, load, "shared"), _row(rows, load, "separated")
        a, b = float(sh["origin_rps"]), float(se["origin_rps"])
        f.ax.plot([a, b], [yc, yc], color=C.agentic_tint, lw=3.2, zorder=2,
                  solid_capstyle="butt")
        for r, hollow in ((sh, True), (se, False)):
            v = float(r["origin_rps"])
            f.whisker(v, yc, float(r["origin_se"]), axis="x")
            f.dot(v, yc, C.agentic, hollow=hollow, size=6.2 * T.base / 8.4)
        d = float(se["effect"])            # from the unrounded means (tools/fig04_data.py)
        f.label((a + b) / 2, yc, f"{S.num(d, 3, sign=True)} req/s", T.value, dy=7,
                      ha="center", va="bottom", weight=SEMIBOLD)
        f.label((a + b) / 2, yc, f"t = {S.num(float(se['t']), 2)}", T.sub, dy=-7, ha="center",
                va="top", color=C.ink_faint)
        # row key
        y_in = f.at(a, yc)[1]
        share = "13%" if load == 12 else "30%"
        cv.text(cv.left, y_in - 0.012, f"{load} agentic req/s", T.key, ha="left",
                va="bottom")
        cv.text(cv.left, y_in + 0.03,
                f"hit {S.num(float(sh['agent_hit']), 3)} → {S.num(float(se['agent_hit']), 3)}",
                T.sub, color=C.ink_faint, ha="left", va="top")
    return cv.save(STEM)
