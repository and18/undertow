"""
FIG-A3 — The synthetic agent matches real agents on working-set width, not on contiguity.

CLAIMS    C3 (MISURATO): lowest testbed point ~693 distinct objects in 143 s;
          honeypot agent-class p90 = 670.
          C5 (MISURATO, declared divergence): contiguity 4.3% observed vs 100% assumed.
DATA      data/derived/figA3_honeypot.csv (aggregates only; no client identifiers)
SOURCE    theslowshelf.org honeypot, 12 Aug - 21 Sep 2026; tools/honeypot_window.py.

DESIGN PASS
  Reader    on the dimension the cache cares about (distinct objects within one
            characteristic time) the lowest testbed point sits at the real agents'
            90th percentile; on contiguity the generator is far from reality.
  Encoding  a: a range strip on a log axis for the 31 real agent clients (median,
            p90, max) with the testbed point on its own row below;
            b: two bars on a 0-100% axis.
  Dominant  the testbed dot landing under the real agents' p90.
  Secondary summary statistics as labels; sample sizes in the row keys.
  Prevent   "real agents are benign / all below the testbed" (E: not supported):
            the strip shows the whole summary (median 4, p90 670, max 678) and the
            caption states one honeypot, 31 clients, one period.
"""
import figure_style as S
from figure_style import C, T, PT, SEMIBOLD

STEM = "FIG-A3_honeypot-calibration"
CLAIMS = "C3 (MISURATO); C5 (MISURATO, declared divergence)"
DATA = ["figA3_honeypot.csv"]
RUNS = ["honeypot theslowshelf.org 2026-08-12..2026-09-21 (aggregates)",
        "generator calculation for scope 0.02 at 12 req/s"]

EDITORIAL = dict(
    headline="The synthetic agent matches real agents on working-set width,\nnot on contiguity",
    deck="Agent-class clients observed on a honeypot compared with the testbed’s agentic "
         "class at its\nlowest setting (scope 0.02, 12 req/s).",
    source="Source: theslowshelf.org honeypot, 12 Aug – 21 Sep 2026, 31 agent-class "
           "clients, 1,929 sessions; Undertow testbed generator.",
)

CAPTION = (
    "Calibration of the synthetic agentic class against agent-class clients observed on the "
    "theslowshelf.org honeypot (12 Aug – 21 Sep 2026). (a) Distinct objects requested "
    "within a 143 s window, the characteristic time of the testbed cache: median 4, 90th "
    "percentile 670 and maximum 678 across 31 clients (mean 240), against about 693 for "
    "the lowest testbed setting. (b) Share of agent sessions that read three contiguous "
    "chapters: 4.3% observed across 1,929 sessions, against 100% assumed by the generator. "
    "One honeypot, one population and one period; the comparison does not characterise "
    "agentic traffic on the Web in general."
)


def _v(rows, k):
    return float(next(r for r in rows if r["quantity"] == k)["value"])


def _keys(cv, f, x, rows_):
    for y, k, sub in rows_:
        yi = f.at(f.ax.get_xlim()[0], y)[1]
        cv.text(x, yi - 0.01, k, T.key, ha="left", va="bottom")
        cv.text(x, yi + 0.026, sub, T.sub, color=C.ink_faint, ha="left", va="top")


def render(variant):
    sp = S.Spec(variant)
    rows = S.read_csv(DATA[0])
    key_w = sp.pick(0.92, 1.12, 1.26)
    row_h = sp.pick(0.42, 0.44, 0.48)
    title_h = T.s(T.panel) * 1.2 * PT + 0.14
    axis_h = 0.05 + T.s(T.tick) * 1.25 * PT + 0.06 + T.s(T.axis) * 1.3 * PT
    gap = 0.24
    body_h = 2 * (title_h + 2 * row_h + axis_h) + gap
    cv = S.Canvas(sp, body_h, **EDITORIAL)
    L, top = cv.left, cv.top
    fx, fw = L + key_w, cv.width - key_w - 0.14
    ms = 5.6 * T.base / 8.4
    y1, y2 = 0.5 * row_h, 1.5 * row_h

    # a — working-set width
    cv.panel_title(L, top + T.s(T.panel) * 0.95 * PT, "a",
                   sp.pick("Working-set width: matched",
                           "Working-set width: matched at the 90th percentile"))
    fa = cv.frame(fx, top + title_h, fw, 2 * row_h, (1, 2000), (2 * row_h, 0), xlog=True)
    xt = [1, 10, 100, 1000]
    fa.vgrid(xt)
    fa.xticks(xt, ["1", "10", "100", "1,000"])
    fa.xtitle(sp.pick("Distinct objects in 143 s (log scale)",
                      "Distinct objects requested in a 143 s window (log scale)"))
    med, p90, mx = _v(rows, "agent_ws_median"), _v(rows, "agent_ws_p90"), _v(rows, "agent_ws_max")
    tb = _v(rows, "testbed_ws")
    fa.ax.plot([med, mx], [y1, y1], color=C.rule_mid, lw=2.2, zorder=2, solid_capstyle="butt")
    fa.dot(med, y1, C.ink, hollow=True, size=ms * 0.9)
    fa.dot(p90, y1, C.ink, size=ms)
    fa.label(med, y1, f"median {S.num(med, 0)}", T.sub, dy=6, ha="center", va="bottom",
             color=C.ink_soft)
    fa.label(p90, y1, f"p90 {S.num(p90, 0)}", T.sub, dx=-3, dy=6, ha="right", va="bottom",
             weight=SEMIBOLD)
    fa.label(mx, y1, f"max {S.num(mx, 0)}", T.sub, dx=3, dy=6, ha="left", va="bottom",
             color=C.ink_soft)
    fa.ax.plot([p90, p90], [y1, y2], color=C.rule_mid, lw=0.6, ls=(0, (1.5, 1.5)), zorder=1)
    fa.dot(tb, y2, C.agentic, size=ms)
    fa.label(tb, y2, f"about {S.num(tb, 0)}", T.sub, dx=-6, ha="right", va="center",
             weight=SEMIBOLD)
    _keys(cv, fa, L, ((y1, "Real agents", "31 honeypot clients"),
                      (y2, "Testbed agent", "scope 0.02, 12 req/s")))

    # b — contiguity
    tb_top = top + title_h + 2 * row_h + axis_h + gap
    cv.panel_title(L, tb_top + T.s(T.panel) * 0.95 * PT, "b", "Contiguity: not matched")
    fb = cv.frame(fx, tb_top + title_h, fw, 2 * row_h, (0, 100), (2 * row_h, 0))
    xt = [0, 25, 50, 75, 100]
    fb.vgrid(xt[1:])
    fb.vbase(0, color=C.rule_mid, lw=0.6)
    fb.xticks(xt, [f"{v}%" for v in xt])
    fb.xtitle("Sessions reading three contiguous chapters")
    obs, gen = _v(rows, "contiguity_observed"), _v(rows, "contiguity_generator")
    bh = row_h * 0.40
    fb.ax.barh(y1, obs, height=bh, color=C.ink, lw=0, zorder=2)
    fb.ax.barh(y2, gen, height=bh, color=C.agentic, lw=0, zorder=2)
    fb.label(obs, y1, f"{S.num(obs, 1)}%", T.sub, dx=4, ha="left", va="center",
             weight=SEMIBOLD)
    fb.label(gen, y2, "100%", T.sub, dx=-4, ha="right", va="center", color=C.surface,
             weight=SEMIBOLD)
    _keys(cv, fb, L, ((y1, "Real agents", "1,929 sessions"),
                      (y2, "Generator", "assumed by design")))
    return cv.save(STEM)
