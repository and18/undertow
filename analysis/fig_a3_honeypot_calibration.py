"""
FIG-A3 — The synthetic agent is close to observed agents in windowed working set, not in contiguity.

CLAIMS    C3 (MISURATO): lowest testbed point ~693 distinct objects in 143 s;
          honeypot agent-class p90 = 670.
          C5 (MISURATO, declared divergence): contiguity with the same metric on both sides,
          honeypot agent class 4.25% of consecutive pairs vs generator 66.9%.
DATA      data/derived/figA3_honeypot.csv (tools/figA3_data.py; aggregates only, no client
          identifiers), from tools/honeypot_aggregate.py on the fixed window
          [2026-08-12, 2026-09-22) UTC and tools/generator_contiguity.py.

DESIGN PASS
  Reader    on the dimension the cache cares about (distinct objects within one
            characteristic time) the lowest testbed point sits at the real agents'
            90th percentile; on contiguity the generator is far from reality.
  Encoding  a: a range strip on a log axis for the real agent clients (median,
            p90, max) with the testbed point on its own row below;
            b: two bars on a 0-100% axis.
  Dominant  the testbed dot landing under the real agents' p90.
  Secondary summary statistics as labels; sample sizes in the row keys.
  Prevent   "real agents are benign / all below the testbed" (E: not supported):
            the strip shows the whole summary (median 4, p90 670, max 678) and the
            caption states one honeypot, the number of clients, one period.
            On b, not "the generator is 100% contiguous": the same pair metric gives
            about two thirds, because the pair between two sessions is rarely contiguous.
"""
import figure_style as S
from figure_style import C, T, PT, SEMIBOLD

STEM = "FIG-A3_honeypot-calibration"
CLAIMS = "C3 (MISURATO); C5 (MISURATO, declared divergence)"
DATA = ["figA3_honeypot.csv"]
RUNS = ["honeypot theslowshelf.org, fixed window [2026-08-12, 2026-09-22) UTC (aggregates)",
        "generator calculation for scope 0.02 at 12 req/s"]


def _v(rows, k):
    return float(_s(rows, k))


def _s(rows, k):
    return next(r for r in rows if r["quantity"] == k)["value"]


def _period(rows):
    """'12 Aug – 21 Sep 2026' from the window in the CSV (end excluded)."""
    from datetime import datetime, timedelta
    a = datetime.fromisoformat(_s(rows, "window_from_utc"))
    b = datetime.fromisoformat(_s(rows, "window_to_utc_excluded")) - timedelta(days=1)
    return f"{a.day} {a:%b} – {b.day} {b:%b %Y}"


def _texts():
    """Source line and caption: every number is computed from the CSV the figure draws."""
    r = S.read_csv(DATA[0])
    n, per = S.num(_v(r, "agent_clients"), 0), _period(r)
    pairs = S.num(_v(r, "pairs_observed"), 0, thousands=True)
    source = (f"Source: theslowshelf.org honeypot, {per}, {n} agent-class clients, {pairs} "
              "request pairs; Undertow testbed generator.")
    caption = (
        "Calibration of the synthetic agentic class against agent-class clients observed on "
        f"a honeypot on a public measurement site ({per}, UTC). (a) Distinct objects requested within "
        "a 143 s window, the characteristic time of the testbed cache: median "
        f"{S.num(_v(r, 'agent_ws_median'), 0)}, 90th percentile {S.num(_v(r, 'agent_ws_p90'), 0)} "
        f"and maximum {S.num(_v(r, 'agent_ws_max'), 0)} across {n} clients (mean "
        f"{S.num(_v(r, 'agent_ws_mean'), 0)}), against about {S.num(_v(r, 'testbed_ws'), 0)} "
        "for the lowest testbed setting. (b) Contiguity, with the same metric on both sides: "
        "the share of consecutive request pairs within one session that read adjacent "
        "chapters of the same book. On the honeypot a session is a TCP connection: "
        f"{S.num(_v(r, 'contiguity_observed'), 2)}% of {pairs} pairs "
        f"({S.num(_v(r, 'connections_observed'), 0)} connections, "
        f"{S.num(_v(r, 'clients_observed'), 0)} clients), and "
        f"{S.num(_v(r, 'repeated_observed'), 1)}% repeat the same chapter. On the generator a "
        f"session is a k6 virtual user: {S.num(_v(r, 'contiguity_generator'), 1)}% of "
        f"{S.num(_v(r, 'pairs_generator'), 0, thousands=True)} pairs (mean of "
        f"{S.num(_v(r, 'seeds_generator'), 0)} seeds), "
        f"{S.num(_v(r, 'repeated_generator'), 0)}% repeated: two of the three chapters of a "
        "session follow a contiguous one, while the pair between two sessions almost never "
        "does. One honeypot, one "
        "population and one period; the comparison does not characterise agentic traffic on "
        "the Web in general.")
    return source, caption


_SOURCE, CAPTION = _texts()

EDITORIAL = dict(
    headline="The synthetic agent is close to observed agents in windowed\nworking set, not in contiguity",
    deck="Agent-class clients observed on a honeypot compared with the testbed’s agentic "
         "class at its\nlowest setting (scope 0.02, 12 req/s).",
    source=_SOURCE,
)




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
                   sp.pick("Windowed working set: close",
                           "Windowed working set: close at the 90th percentile"))
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
    _keys(cv, fa, L, ((y1, "Honeypot agents", f"{S.num(_v(rows, 'agent_clients'), 0)} honeypot clients"),
                      (y2, "Testbed agent", "scope 0.02, 12 req/s")))

    # b — contiguity
    tb_top = top + title_h + 2 * row_h + axis_h + gap
    cv.panel_title(L, tb_top + T.s(T.panel) * 0.95 * PT, "b", "Contiguity: not close")
    fb = cv.frame(fx, tb_top + title_h, fw, 2 * row_h, (0, 100), (2 * row_h, 0))
    xt = [0, 25, 50, 75, 100]
    fb.vgrid(xt[1:])
    fb.vbase(0, color=C.rule_mid, lw=0.6)
    fb.xticks(xt, [f"{v}%" for v in xt])
    fb.xtitle(sp.pick("Consecutive pairs on adjacent chapters",
                      "Consecutive request pairs on adjacent chapters, within one session"))
    obs, gen = _v(rows, "contiguity_observed"), _v(rows, "contiguity_generator")
    bh = row_h * 0.40
    fb.ax.barh(y1, obs, height=bh, color=C.ink, lw=0, zorder=2)
    fb.ax.barh(y2, gen, height=bh, color=C.agentic, lw=0, zorder=2)
    fb.label(obs, y1, f"{S.num(obs, 2)}%", T.sub, dx=4, ha="left", va="center",
             weight=SEMIBOLD)
    fb.label(gen, y2, f"{S.num(gen, 1)}%", T.sub, dx=-4, ha="right", va="center", color=C.surface,
             weight=SEMIBOLD)
    _keys(cv, fb, L, ((y1, "Honeypot agents", "per TCP connection"),
                      (y2, "Generator", "per k6 virtual user")))
    return cv.save(STEM)
