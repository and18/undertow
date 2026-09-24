"""
FIG-06 — Origin requests are a validated proxy for backend CPU on this testbed.

CLAIM     C1 (MISURATO): CPU = 0.021 + 0.0368 x origin_rps, R^2 = 0.997, max residual
          3.1%, five policy windows over a 4.5x load range.
DATA      data/derived/fig06_cpu_validation.csv   columns: policy,origin_rps,cpu_cores,reps
          (one row per policy, averaged over 3 measurement-window repetitions; CPU in
          cores = CPU-seconds per second for PostgreSQL, node_cpu_seconds_total{cpu=~"3|4|5",
          mode!="idle"}, produced by tools/cpu_validation.py from VictoriaMetrics).
          The build refits the line and stops if it does not reproduce C1.

DESIGN PASS
  Reader    backend CPU is a straight-line function of origin requests, so the
            figures that count origin requests are counting backend work.
  Encoding  a scatter with the least-squares line, both axes from zero so the
            intercept is honest; a slim residual strip underneath, because a
            validation is judged by its residuals, not by R^2.
  Dominant  the five points on the line.
  Secondary the equation and R^2 as one label on the line; policy codes on points.
  Prevent   "origin requests = backend load in general" (E: to qualify): the
            headline, the label and the caption all say "on this testbed".
"""
import figure_style as S
from figure_style import C, T, PT, SEMIBOLD

STEM = "FIG-06_cpu-validation"
CLAIMS = "C1 (MISURATO)"
DATA = ["fig06_cpu_validation.csv"]
RUNS = ["five policy windows of the frontier campaign (A, B, C, D4, D6)"]

EDITORIAL = dict(
    headline="On this testbed, origin requests track backend CPU\nalong a straight line",
    deck="PostgreSQL CPU against origin requests per second in five admission-policy "
         "windows,\nspanning a 4.5× range of load.",
    source="Source: Undertow testbed; one point per policy, averaged over 3 repetitions; "
           "least-squares fit.",
)

CAPTION = (
    "Validation of origin requests as a proxy for backend load on this testbed. Each point "
    "is one admission policy, averaged over 3 measurement-window repetitions; the line is "
    "the least-squares fit CPU = 0.021 + 0.0368 × origin req/s (R² = 0.997), i.e. about "
    "36.8 ms of PostgreSQL CPU per origin request. The lower strip shows the residuals as a "
    "percentage of the fitted value (largest 3.1%). The relation is established for this "
    "testbed only and is not claimed for backend load in general."
)

FROZEN = dict(intercept=0.021, slope=0.0368, r2=0.997, max_resid_pct=3.1)


def _fit(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = my - b * mx
    ss_res = sum((y - a - b * x) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    return a, b, 1 - ss_res / ss_tot


def _check(a, b, r2, resid):
    bad = []
    if abs(b - FROZEN["slope"]) > 0.0006: bad.append(f"slope {b:.4f}")
    if abs(a - FROZEN["intercept"]) > 0.02: bad.append(f"intercept {a:.3f}")
    if r2 < 0.996: bad.append(f"R2 {r2:.4f}")
    if max(abs(r) for r in resid) > 3.3: bad.append(f"max residual {max(map(abs, resid)):.1f}%")
    if bad:
        raise ValueError("fig06 data do not reproduce claim C1: " + ", ".join(bad))


def render(variant):
    sp = S.Spec(variant)
    rows = S.read_csv(DATA[0])
    xs = [float(r["origin_rps"]) for r in rows]
    ys = [float(r["cpu_cores"]) for r in rows]
    a, b, r2 = _fit(xs, ys)
    resid = [(y - (a + b * x)) / (a + b * x) * 100 for x, y in zip(xs, ys)]
    _check(a, b, r2, resid)

    tick_w = sp.pick(0.26, 0.30, 0.32)
    fh = sp.pick(1.75, 1.95, 2.10)
    rh = sp.pick(0.46, 0.50, 0.54)
    title_h = T.s(T.axis) * 1.2 * PT + 0.10
    gap = 0.12 + T.s(T.axis) * 1.2 * PT + 0.08
    below = 0.05 + T.s(T.tick) * 1.25 * PT + 0.06 + T.s(T.axis) * 1.3 * PT
    cv = S.Canvas(sp, title_h + fh + gap + rh + below, **EDITORIAL)
    fx, fw = cv.left + tick_w, cv.width - tick_w - 0.10
    xmax = 90
    ymax = 3.4
    f = cv.frame(fx, cv.top + title_h, fw, fh, (0, xmax), (0, ymax))
    yt = [0, 1, 2, 3]
    f.hgrid(yt[1:])
    f.hbase(0, color=C.rule_mid, lw=0.6)
    f.yticks(yt, [str(v) for v in yt])
    f.ytitle("PostgreSQL CPU, cores", x=cv.left)

    # B and C sit almost on top of each other (18.8 vs 18.0 req/s): their
    # labels get opposite offsets so they don't collide.
    LABEL_POS = {
        "B": dict(dx=6, dy=4, ha="left", va="bottom"),
        "C": dict(dx=-6, dy=-4, ha="right", va="top"),
    }
    f.ax.plot([0, xmax], [a, a + b * xmax], color=C.neutral, lw=1.1, zorder=2)
    for r, x, y in zip(rows, xs, ys):
        f.dot(x, y, C.ink)
        pos = LABEL_POS.get(r["policy"], dict(dx=-5, dy=4, ha="right", va="bottom"))
        f.label(x, y, r["policy"], T.sub, color=C.ink_soft, **pos)
    # the fit, stated once, in the empty top-left corner
    cv.text(f.x + 0.06, f.y + 0.06, f"CPU = {S.num(a, 3)} + {S.num(b, 4)} × origin req/s\n"
            f"R² = {S.num(r2, 3)}", T.label, ha="left", va="top", color=C.ink,
            linespacing=1.3)

    # residual strip
    ry = f.bottom + gap
    g = cv.frame(fx, ry, fw, rh, (0, xmax), (-5, 5))
    g.hgrid([-4, 4])
    g.hbase(0, color=C.rule_mid, lw=0.6)
    g.yticks([-4, 0, 4], [S.num(-4, 0, sign=True) + "%", "0", "+4%"])
    g.ytitle("Residual, % of fit", x=cv.left)
    for x, e in zip(xs, resid):
        g.ax.plot([x, x], [0, e], color=C.ink_soft, lw=0.8, zorder=3)
        g.dot(x, e, C.ink, size=4.2 * T.base / 8.4)
    xt = [0, 15, 30, 45, 60, 75, 90]
    g.xticks(xt, [str(v) for v in xt])
    g.xtitle("Origin requests per second")
    return cv.save(STEM)
