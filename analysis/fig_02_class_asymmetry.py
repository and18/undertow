"""
FIG-02 — Composition moves the agentic class's cost per request; the others barely move.

CLAIMS    A2 (MISURATO) panel a · A7 (MISURATO, secondary series) panel b.
DATA      data/derived/fig02a_miss_by_class.csv, fig02b_exhaustive_marginal.csv
RUNS      a: tre-20260921-150237/-162248 (separated mapping, 5 reps)
          b: crawler series of 16 Sep 2026 (shared mapping, 1211 s window, 3 reps)

DESIGN PASS
  Reader    raising the agentic share changes the agentic miss ratio fourfold and
            the other two classes' by 2-3%; and when the exhaustive class varies its
            OWN volume, its marginal cost stays flat.
  Encoding  a: slope chart on a log axis, so equal slopes mean equal ratios and the
            4.05x reads as a steep line against two flat ones.
            b: dots with whiskers on a linear axis from zero, so "flat near 1" is
            seen honestly.
  Dominant  the steep agentic line.
  Secondary end values and ratios as direct labels; the secondary-series caveat as
            a one-line note under panel b.
  Prevent   reading panel a as "three classes under the same stimulus" (only the
            agentic volume changes: the panel title says what moved), and reading
            b as primary evidence (it is labelled secondary).
"""
import figure_style as S
from figure_style import C, T, PT, SEMIBOLD

STEM = "FIG-02_class-asymmetry"
CLAIMS = "A2 (MISURATO); A7 (MISURATO, secondary series)"
DATA = ["fig02a_miss_by_class.csv", "fig02b_exhaustive_marginal.csv"]
RUNS = ["tre-20260921-150237", "tre-20260921-162248", "crawler series 2026-09-16"]

EDITORIAL = dict(
    headline="A larger agentic share moves the agentic class’s cost fourfold,\n"
             "the other classes’ by 2–3%",
    deck="(a) Miss ratio of each class as the agentic share of load rises from 13% to 30%. "
         "(b) Marginal\norigin cost of the exhaustive class as its own volume rises.",
    source="Source: Undertow testbed. (a) separated working sets, mean of 5 runs. (b) "
           "secondary series of 16 Sep 2026:\nshared mapping, 1,211 s window, mean of 3 "
           "runs, whiskers ± 1 SE.",
)

CAPTION = (
    "Sensitivity of per-request cost to traffic composition, by class. (a) Miss ratio of "
    "each class at 13% and 30% agentic share of load (log scale); only the agentic volume "
    "changes (12 to 36 req/s), human and exhaustive volumes are fixed at 55 and 28 req/s, "
    "working sets are separated; labels give the ratio between the two mean miss ratios. "
    "Mean of 5 runs; whiskers \u00b1 1 SE, smaller than the markers. (b) Marginal origin requests per added exhaustive request as the exhaustive "
    "volume rises from 0 to 42 req/s with the human and agentic volumes fixed; its miss "
    "ratio changes by 1.09× over the range. This is a secondary series (16 Sep 2026: "
    "shared mapping, 1,211 s measurement window, 3 runs) and is not paired with the primary "
    "design. Whiskers: ± 1 SE."
)

LABEL = {"agentic": "Agentic", "human": "Human", "exhaustive": "Exhaustive"}


def _panel_a(cv, sp, x, y, w, h, rows):
    tick_w = 0.30
    lab_w = sp.pick(0.86, 0.92, 1.02)
    fx0, fw = x + tick_w, w - tick_w - lab_w
    title_h = T.s(T.panel) * 1.2 * PT + 0.16
    cv.panel_title(x, y + T.s(T.panel) * 0.95 * PT, "a", "Agentic share, 13% → 30%")
    top = y + title_h + 0.10
    fh = h - title_h - 0.10 - 0.05 - T.s(T.tick) * 1.25 * PT - 0.06 - T.s(T.axis) * 1.3 * PT
    f = cv.frame(fx0, top, fw, fh, (-0.08, 1.08), (0.03, 1.25), ylog=True)
    ticks = [0.05, 0.1, 0.2, 0.5, 1]
    f.hgrid(ticks)
    f.yticks(ticks, ["0.05", "0.1", "0.2", "0.5", "1"])
    f.ytitle("Miss ratio, log scale", x=x)
    f.xticks([0, 1], ["13%", "30%"])
    f.xtitle("Agentic share of load")
    order = ["human", "exhaustive", "agentic"]          # agentic drawn last, on top
    for cls in order:
        r = next(r for r in rows if r["class"] == cls)
        a, b = float(r["miss_share13"]), float(r["miss_share30"])
        ratio = max(a, b) / min(a, b)             # ratio of the means, not of rounded values
        lw = 2.1 if cls == "agentic" else 1.2
        f.ax.plot([0, 1], [a, b], color=S.CLASS[cls], lw=lw, zorder=4,
                  solid_capstyle="round")
        f.whisker(0, a, float(r["se13"])); f.whisker(1, b, float(r["se30"]))
        f.dot(0, a, S.CLASS[cls]); f.dot(1, b, S.CLASS[cls])
        # direct label: name + ratio, then the two values
        f.label(1, b, LABEL[cls], T.key, dx=8, dy=3.2, va="bottom")
        nm_w = S.text_w(LABEL[cls] + " ", T.key)
        f.label(1, b, f"{S.num(ratio, 2)}×", T.value, dx=8 + nm_w / PT, dy=3.2,
                va="bottom", weight=SEMIBOLD)
        f.label(1, b, f"{S.num(a, 3)} → {S.num(b, 3)}", T.sub, dx=8, dy=1.2,
                va="top", color=C.ink_faint)
    return f


def _panel_b(cv, sp, x, y, w, h, rows):
    tick_w = 0.28
    title_h = T.s(T.panel) * 1.2 * PT + 0.16
    cv.panel_title(x, y + T.s(T.panel) * 0.95 * PT, "b", "Exhaustive volume, 0 → 42 req/s")
    top = y + title_h + 0.10
    note_h = 0.06 + T.s(T.sub) * 1.3 * PT * (1 if sp.narrow else 2)
    fh = (h - title_h - 0.10 - 0.05 - T.s(T.tick) * 1.25 * PT - 0.06 - T.s(T.axis) * 1.3 * PT
          - note_h)
    f = cv.frame(x + tick_w, top, w - tick_w - 0.05, fh, (-0.5, 2.5), (0, 1.2))
    f.hgrid([0.25, 0.5, 0.75, 1.0])
    f.hbase(0, lw=0.8)
    f.yticks([0, 0.25, 0.5, 0.75, 1.0], ["0", "0.25", "0.50", "0.75", "1.00"])
    f.ytitle("Origin requests per added request", x=x)
    labels = [f"{int(r['from_rps'])}–{int(r['to_rps'])}" for r in rows]
    f.xticks([0, 1, 2], labels)
    f.xtitle("Exhaustive volume step, req/s")
    for i, r in enumerate(rows):
        v, se = float(r["marginal"]), float(r["marginal_se"])
        f.whisker(i, v, se)
        f.dot(i, v, C.exhaustive)
        f.label(i, v, S.num(v, 3), T.value, dy=7, ha="center", va="bottom", weight=SEMIBOLD)
    cv.text(x, f.bottom + 0.05 + T.s(T.tick) * 1.25 * PT + 0.06 + T.s(T.axis) * 1.3 * PT + 0.06,
            sp.pick("Secondary series: shared mapping, 1,211 s window, 3 runs",
                    "Secondary series: shared mapping,\n1,211 s window, 3 runs"),
            T.sub, linespacing=1.25,
            color=C.ink_faint, ha="left", va="top")
    return f


def render(variant):
    sp = S.Spec(variant)
    a_rows = S.read_csv(DATA[0])
    b_rows = S.read_csv(DATA[1])
    if sp.narrow:
        ph, ph_b = 2.05, 1.60          # panel b needs less height: three dots near 1
        body_h = ph + ph_b + 0.30
    else:
        ph = sp.pick(None, 2.30, 2.45)
        body_h = ph
    cv = S.Canvas(sp, body_h, **EDITORIAL)
    top, L, W = cv.top, cv.left, cv.width
    if sp.narrow:
        _panel_a(cv, sp, L, top, W, ph, a_rows)
        _panel_b(cv, sp, L, top + ph + 0.30, W, ph_b, b_rows)
    else:
        wa = W * 0.55
        gap = sp.pick(None, 0.34, 0.44)
        _panel_a(cv, sp, L, top, wa, ph, a_rows)
        _panel_b(cv, sp, L + wa + gap, top, W - wa - gap, ph, b_rows)
    return cv.save(STEM)
