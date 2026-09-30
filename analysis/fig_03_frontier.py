"""
FIG-03 — Blocking and deferring lie on one work/latency frontier; blocking the
agentic class as well costs served requests and buys no measurable latency.

CLAIMS    A6 (MISURATO) the single convex curve · A4 (MISURATO) B versus C.
DATA      data/derived/fig03_frontier.csv
RUNS      frontier campaign at lambda = 185, alpha = 0.35, beta = 0.10, 3 reps per policy
          (tre-20260919-072040 / -080920 / -085754 / -094627 / -103501,
           tre-20260920-061512 / -070346 / -075220).

DESIGN PASS
  Reader    every policy trades served requests for human latency along ONE curve;
            B and C are at the same latency, and C serves fewer requests.
  Encoding  a frontier: requests served (x) against human p99 (y), points joined in
            order because A6 is a claim about that ordered curve. Linear y, so the
            convexity the claim is about is visible; the no-policy point (555 ms)
            leaves the scale through the top edge instead of flattening the rest.
            Marker shape carries the policy family (square block, circle defer).
  Dominant  the curve.
  Secondary the B-C comparison as one bracketed annotation; point codes explained
            in a small key; the off-scale point as an arrow with its value.
  Prevent   "B dominates C" (retracted, R5): the annotation gives the latency
            difference with its SE and the words say "no measurable difference";
            "deferring dominates blocking" (retracted, R1): one line, one family
            of trade-offs.
"""
import figure_style as S
from figure_style import C, T, PT, SEMIBOLD

STEM = "FIG-03_work-latency-frontier"
CLAIMS = "A6 (MISURATO); A4 (MISURATO)"
DATA = ["fig03_frontier.csv"]
RUNS = ["tre-20260919-072040", "tre-20260919-080920", "tre-20260919-085754",
        "tre-20260919-094627", "tre-20260919-103501", "tre-20260920-061512",
        "tre-20260920-070346", "tre-20260920-075220"]

EDITORIAL = dict(
    headline="Blocking the agentic class as well costs 2,807 served requests\n"
             "and buys no measurable latency",
    deck="Requests served and human p99 latency under eight admission policies at the knee "
         "of the\ntestbed (185 req/s). Blocking and deferring trace a single convex frontier.",
    source="Source: Undertow testbed, 620 s windows, mean of 3 repetitions per policy, whiskers "
           "± 1 SE.\nB versus C: 95% confidence interval of the latency difference "
           "−1.99 to +2.05 ms.",
)

CAPTION = (
    "Work/latency frontier at the knee of the testbed (185 req/s; α = 0.35, "
    "β = 0.10). Each point is an admission policy: squares block classes at the origin "
    "(C blocks the exhaustive and agentic classes, B the exhaustive class only), circles "
    "defer exhaustive requests with a budget of 1 to 6, and the no-policy point lies "
    "above the plotted range. Points are joined "
    "in order of requests served. Mean of 3 repetitions; whiskers ± 1 SE, some smaller than "
    "the markers. The marginal slope rises monotonically from 0.01 to 102.25 ms per 1,000 "
    "additional requests served. B serves 2,807 ± 185 more requests than C "
    "(t = 15.19) with a human p99 difference of +0.03 ± 0.73 ms (95% CI −1.99 to "
    "+2.05 ms), which is not distinguishable from zero."
)

YMAX = 240


def render(variant):
    sp = S.Spec(variant)
    rows = {r["policy"]: r for r in S.read_csv(DATA[0])}
    tick_w = sp.pick(0.28, 0.32, 0.34)
    fh = sp.pick(2.05, 2.35, 2.55)
    title_h = T.s(T.axis) * 1.2 * PT + 0.10
    below = 0.05 + T.s(T.tick) * 1.25 * PT + 0.06 + T.s(T.axis) * 1.3 * PT
    cv = S.Canvas(sp, title_h + fh + below, **EDITORIAL)
    f = cv.frame(cv.left + tick_w, cv.top + title_h, cv.width - tick_w - 0.04, fh,
                 (83.0, 116.5), (30, YMAX))

    yt = [50, 100, 150, 200]
    f.hgrid(yt)
    f.yticks(yt, [str(v) for v in yt])
    f.ytitle("Human p99 latency, ms", x=cv.left)
    xt = [85, 90, 95, 100, 105, 110, 115]
    f.xticks(xt, [str(v) for v in xt], marks=True)
    f.xtitle("Requests served in 620 s, thousands")
    f.hbase(30, color=C.rule_mid, lw=0.6)

    order = ["C", "B", "D1", "D2", "D3", "D4", "D6"]
    xs = [float(rows[p]["served"]) / 1000 for p in order]
    ys = [float(rows[p]["p99_ms"]) for p in order]
    # the frontier, and its exit through the top edge towards A
    a = rows["A"]
    ax_, ay_ = float(a["served"]) / 1000, float(a["p99_ms"])
    x_exit = xs[-1] + (YMAX - ys[-1]) / (ay_ - ys[-1]) * (ax_ - xs[-1])
    f.ax.plot(xs + [x_exit], ys + [YMAX], color=C.neutral, lw=1.2, zorder=3,
              solid_joinstyle="round", clip_on=False)
    f.ax.annotate("", xy=(x_exit + 0.08, YMAX + 4), xytext=(x_exit - 0.02, YMAX - 2),
                  arrowprops=dict(arrowstyle="-|>,head_length=0.45,head_width=0.22",
                                  color=C.neutral, lw=1.2, shrinkA=0, shrinkB=0),
                  annotation_clip=False, zorder=3)
    a_txt = f"{S.num(ay_, 0)} ± {S.num(float(a['p99_se']), 0)} ms"
    f.label(x_exit, YMAX, sp.pick(f"A  no policy\n{a_txt}", f"A  no policy: {a_txt}"),
            T.label, dx=-5, dy=-1, ha="right", va="top", color=C.ink_soft, linespacing=1.2)

    for p, x, y in zip(order, xs, ys):
        r = rows[p]
        block = r["family"] == "block"
        f.whisker(x, y, float(r["p99_se"]), axis="y")
        f.whisker(x, y, float(r["served_se"]) / 1000, axis="x")
        f.dot(x, y, C.ink, marker="s" if block else "o",
              size=(5.2 if block else 5.6) * T.base / 8.4)
        code = p if block else p[1:]
        if block:
            f.label(x, y, code, T.label, dy=6, ha="center", va="bottom", weight=SEMIBOLD)
        elif p == "D6":          # the last point: label to the right, clear of A's label
            f.label(x, y, code, T.label, dx=6, ha="left", va="center", color=C.ink_soft)
        else:
            f.label(x, y, code, T.label, dx=-5, dy=3, ha="right", va="bottom",
                    color=C.ink_soft)

    # B versus C: one bracket, one sentence
    xc, xb = xs[0], xs[1]
    yb = 47.0
    f.ax.plot([xc, xc, xb, xb], [yb + 2.6, yb, yb, yb + 2.6], color=C.ink_soft, lw=0.6,
              zorder=3, solid_joinstyle="miter")
    d_served = float(rows["B"]["served"]) - float(rows["C"]["served"])
    f.label(xb, yb, sp.pick(
        f"B serves {S.num(d_served, 0, thousands=True)} ± 185 more;\n"
        "p99 difference +0.03 ± 0.73 ms",
        f"B serves {S.num(d_served, 0, thousands=True)} ± 185 more requests than C; "
        "p99 difference +0.03 ± 0.73 ms"),
        T.label, dx=5, dy=sp.pick(-4, 0), ha="left", va="center", color=C.ink,
        linespacing=1.2, bbox=dict(boxstyle="square,pad=0.1", fc=C.surface, ec="none"))

    # key for the point codes, top-left where the frontier never goes
    kx, ky = f.x + 0.06, f.y + 0.08
    step = T.s(T.sub) * 1.5 * PT
    entries = [("s", "C", "block exhaustive + agentic"),
               ("s", "B", "block exhaustive"),
               ("o", "1–6", "defer exhaustive, budget")]
    for i, (mk, code, text) in enumerate(entries):
        yy = ky + i * step
        cv.fig.add_artist(S.mpl.lines.Line2D([cv.fx(kx + 0.03)], [cv.fy(yy)], marker=mk,
                          ms=3.8 * T.base / 8.4, mfc=C.ink, mec=C.ink, ls="none"))
        cv.text(kx + 0.10, yy, code, T.sub, weight=SEMIBOLD, ha="left", va="center")
        cv.text(kx + 0.10 + S.text_w("1–6 ", T.sub, SEMIBOLD), yy, text, T.sub,
                color=C.ink_soft, ha="left", va="center")
    return cv.save(STEM)
