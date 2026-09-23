"""
figure_style.py — the Undertow figure design system (v4, definitive).

WHAT IS SHARED, WHAT IS NOT
  Shared by every figure: typography, colour semantics, spacing, the way
  uncertainty, axes, grids, markers and labels are drawn, and the build guards.
  NOT shared: the chart form. Each figure picks the form its message needs
  (ladder, slope chart, frontier, dumbbell, waterfall, scatter, small multiples).

RENDER TARGETS — one drawing function per figure, three outputs
  paper      4.80 in   canonical. Single-column text width (LaTeX article
                       default \\textwidth = 345 pt, Springer LNCS = 122 mm).
  narrow     3.33 in   two-column venues (ACM sigconf column). Same message and
                       concept; layout, sizes and label placement adapt.
  editorial  6.20 in   thesis, web, slides. Adds headline, deck and source line.
  A figure is always included at 100 % of its width: the point sizes below are
  the sizes printed on the page.

TYPOGRAPHY
  Source Sans 3 (Adobe, SIL OFL 1.1, bundled in analysis/fonts). A humanist
  sans: lighter on the page than a grotesque, narrow enough for 3.33 in
  columns, and complete for the symbols we print (− ± × – → ≈ ≤).
  Weights: 400 for text, 600 for the few things a reader must find first
  (values, keys, headline). Nothing heavier. Italic is not used.
  One base size per width; every role is a multiple of it; nothing under 6 pt.

COLOUR — semantic, never decorative
  Traffic classes keep one colour everywhere they appear:
      agentic     #0e7f62  deep teal   (L* 47)
      human       #4f8fdf  blue        (L* 59)
      exhaustive  #f39b52  orange      (L* 72)
  Validated with validate_palette.js --pairs all: worst CVD ΔE 17.1, worst
  normal-vision ΔE 20.0. The three lightness steps (47 / 59 / 72) keep the
  classes apart in grayscale. The orange sits under 3:1 contrast on white, so
  every class mark carries a direct label. Text is never set in a class colour.
  Anything that is not a traffic class (policies, models, totals, the real Web)
  is drawn in the neutral ramp, distinguished by marker shape and fill.

UNCERTAINTY — one treatment everywhere
  ± 1 standard error, drawn as a thin whisker (0.6 pt) in ink with short caps.
  Whiskers are always drawn, under point markers and over bars: a whisker
  shorter than its marker is hidden by it, and the caption says so. Uncertainty
  is never removed to tidy a figure. A pre-registered tolerance is a wash band.

AXES AND GRID
  No box. Value axes get hairline gridlines in `rule`; categorical axes none.
  A zero or baseline that carries meaning is drawn in ink. The y-axis title is
  set horizontally above the plot, left-aligned with the tick labels; the
  x-axis title sits under the tick labels.

MARKERS
  circle = default / measured · square = block policy · triangle = no policy ·
  diamond = model or reference · hollow = the "before" or the confounded state.
  Every marker carries a 1 pt white ring so it stays legible over lines.

BUILD GUARDS — a figure that fails one is not written
  glyphs   every character exists in the bundled font;
  bounds   no text crosses the canvas margin;
  overlap  no two texts overlap.
"""
from pathlib import Path
import itertools
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ft2font import FT2Font

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FONT_DIR = HERE / "fonts"

_ttf = sorted(FONT_DIR.glob("SourceSans3-*.ttf"))
if not _ttf:
    raise SystemExit("analysis/fonts/SourceSans3-*.ttf missing — the house font is part of the build")
for _f in _ttf:
    font_manager.fontManager.addfont(str(_f))
FONT = "Source Sans 3"
_CMAP = set(FT2Font(str(FONT_DIR / "SourceSans3-Regular.ttf")).get_charmap().keys())

REGULAR, SEMIBOLD = 400, 600


# ── colour tokens ─────────────────────────────────────────────────────────
class C:
    agentic      = "#0e7f62"
    agentic_tint = "#b9ddd1"    # connecting segments, bands for the agentic class
    human        = "#4f8fdf"
    exhaustive   = "#f39b52"

    ink          = "#1b1b1a"    # values, keys, marks that are not a class
    ink_soft     = "#4e4e4a"    # deck, axis titles, direction labels
    ink_faint    = "#86867f"    # ticks, secondary lines, source
    neutral      = "#a9a9a2"    # neutral marks: totals, models, context
    rule         = "#e5e5df"    # gridlines
    rule_mid     = "#c4c4bd"    # leaders, table rules, connectors
    baseline     = "#2b2b29"    # a zero or baseline that means something
    wash         = "#f3f3ee"    # bands (tolerance, regions)
    surface      = "#ffffff"

CLASS = {"agentic": C.agentic, "human": C.human, "exhaustive": C.exhaustive}


# ── render targets ────────────────────────────────────────────────────────
VARIANTS = {            # variant: (width in, mode)
    "paper":     (4.80, "paper"),
    "narrow":    (3.33, "paper"),
    "editorial": (6.20, "editorial"),
}


class T:
    """Type roles as multiples of the base size (set per width). Floor 6 pt."""
    headline = 1.55
    deck     = 1.04
    panel    = 1.00    # small-multiple panel titles
    key      = 1.00    # what a row / series is
    value    = 1.02    # a direct value label (semibold)
    label    = 0.94    # direct labels, annotations
    axis     = 0.92    # axis titles
    tick     = 0.86
    sub      = 0.84    # second line under a key or value
    source   = 0.82
    base     = 8.4

    @classmethod
    def s(cls, role):
        return max(6.0, cls.base * role)


def base_size(width_in):
    # 8.4 pt at the canonical 4.80 in; 7.7 at 3.33 in; 9.0 at 6.20 in.
    return round(8.4 * (width_in / 4.80) ** 0.24, 2)


PT = 1 / 72.0          # one point in inches


def _rc(width_in):
    T.base = base_size(width_in)
    return {
        "font.family": FONT, "font.size": T.base, "font.weight": REGULAR,
        "text.color": C.ink, "axes.labelcolor": C.ink_soft,
        "figure.facecolor": C.surface, "savefig.facecolor": C.surface,
        "axes.facecolor": "none", "axes.grid": False, "legend.frameon": False,
        "lines.solid_capstyle": "butt", "lines.dash_capstyle": "butt",
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
        "figure.dpi": 100, "savefig.dpi": 400,
        "savefig.bbox": None, "savefig.pad_inches": 0,
        "path.simplify": False,
    }


MINUS = "−"


def num(x, dec=3, sign=False, thousands=False):
    """
    Number as printed in the paper: decimal half-up rounding from the decimal
    string (0.0055 -> 0.006 on every machine, never binary-float 0.005), a true
    minus sign, '+' only when asked, optional thousands separator.
    """
    from decimal import Decimal, ROUND_HALF_UP
    q = Decimal(str(x)).quantize(Decimal(1).scaleb(-dec), rounding=ROUND_HALF_UP)
    s = f"{abs(q):,.{dec}f}" if thousands else f"{abs(q):.{dec}f}"
    if q < 0:
        return MINUS + s
    return ("+" + s) if (sign and q > 0) else s


class Spec:
    """What a figure needs to know about the target it is drawing for."""
    def __init__(self, variant):
        self.variant = variant
        self.w, self.mode = VARIANTS[variant]
        self.narrow = self.w < 4.0
        self.editorial = self.mode == "editorial"
        mpl.rcParams.update(_rc(self.w))
        self.base = T.base

    def pick(self, narrow, paper, editorial=None):
        """Choose a layout value by target."""
        if self.narrow:
            return narrow
        if self.editorial and editorial is not None:
            return editorial
        return paper


# ── canvas: an exact-size page, positions in inches from the top-left ─────
class Canvas:
    MARGIN = {"paper": 0.02, "editorial": 0.30}
    GAP_BODY = 0.22
    GAP_FOOT = 0.20

    @staticmethod
    def _n(s):
        return s.count("\n") + 1 if s else 0

    @classmethod
    def head_h(cls, headline, deck):
        return (0.12 + cls._n(headline) * T.s(T.headline) * 1.16 * PT
                + 0.10 + cls._n(deck) * T.s(T.deck) * 1.38 * PT)

    @classmethod
    def foot_h(cls, source):
        return cls.GAP_FOOT + 0.09 + cls._n(source) * T.s(T.source) * 1.38 * PT

    def __init__(self, spec, body_h, headline="", deck="", source=""):
        self.spec = spec
        self.w = spec.w
        self.m = self.MARGIN[spec.mode]
        ed = spec.editorial
        self.h = round(self.m + (self.head_h(headline, deck) + self.GAP_BODY if ed else 0)
                       + body_h + (self.foot_h(source) if ed else 0) + self.m, 3)
        self.fig = plt.figure(figsize=(self.w, self.h))
        self.top = self.m
        if ed:
            self.top = self._header(headline, deck)
            self._footer(source)
        self.body_h = body_h

    # geometry
    @property
    def left(self): return self.m
    @property
    def right(self): return self.w - self.m
    @property
    def width(self): return self.w - 2 * self.m

    def fx(self, x): return x / self.w
    def fy(self, y): return 1 - y / self.h

    def text(self, x, y, s, role=None, size=None, weight=REGULAR, color=C.ink, **kw):
        fs = size if size is not None else T.s(role if role is not None else T.label)
        return self.fig.text(self.fx(x), self.fy(y), s, fontsize=fs, fontweight=weight,
                             color=color, **kw)

    def line(self, xs, ys, color=C.rule_mid, lw=0.5, **kw):
        ln = mpl.lines.Line2D([self.fx(x) for x in xs], [self.fy(y) for y in ys],
                              color=color, lw=lw, solid_capstyle="butt", **kw)
        self.fig.add_artist(ln)
        return ln

    def axes(self, x, y, w, h):
        ax = self.fig.add_axes([self.fx(x), self.fy(y + h), w / self.w, h / self.h])
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(which="both", left=False, bottom=False, labelleft=False,
                       labelbottom=False)
        ax.patch.set_visible(False)
        return ax

    def frame(self, x, y, w, h, xlim, ylim, xlog=False, ylog=False):
        return Frame(self, x, y, w, h, xlim, ylim, xlog, ylog)

    def panel_title(self, x, y, letter, title):
        """'a  Title' — letter semibold, title regular. y is the baseline."""
        t1 = self.text(x, y, letter, T.panel, weight=SEMIBOLD, va="baseline")
        self.text(x + 0.13 * T.base / 8.4, y, title, T.panel, color=C.ink_soft, va="baseline")
        return t1

    # editorial frame
    def _header(self, headline, deck):
        y = self.m
        self.line([self.left, self.left + 0.30], [y, y], color=C.ink, lw=2.4)
        y += 0.12
        self.text(self.left, y, headline, T.headline, weight=SEMIBOLD, va="top",
                  linespacing=1.12)
        y += self._n(headline) * T.s(T.headline) * 1.16 * PT + 0.10
        self.text(self.left, y, deck, T.deck, color=C.ink_soft, va="top", linespacing=1.36)
        y += self._n(deck) * T.s(T.deck) * 1.38 * PT
        return y + self.GAP_BODY

    def _footer(self, source):
        y = self.h - self.m - self.foot_h(source) + self.GAP_FOOT
        self.line([self.left, self.right], [y, y], color=C.rule, lw=0.6)
        self.text(self.left, y + 0.09, source, T.source, color=C.ink_faint, va="top",
                  linespacing=1.36)

    # guards and output
    def check(self):
        self.fig.canvas.draw()
        r = self.fig.canvas.get_renderer()
        texts = [t for t in self.fig.findobj(mpl.text.Text)
                 if t.get_visible() and t.get_text().strip()]
        missing = {}
        for t in texts:
            for ch in t.get_text():
                if ch not in "\n\t" and ord(ch) not in _CMAP:
                    missing.setdefault(ch, t.get_text()[:40])
        errs = [f"  glyph U+{ord(c):04X} {c!r} missing in {ctx!r}" for c, ctx in missing.items()]
        dpi = self.fig.dpi
        lo_x, hi_x = self.m * dpi - 0.5, (self.w - self.m) * dpi + 0.5
        lo_y, hi_y = self.m * dpi - 0.5, (self.h - self.m) * dpi + 0.5
        boxes = [(t, t.get_window_extent(r)) for t in texts]
        for t, b in boxes:
            if b.x0 < lo_x or b.x1 > hi_x or b.y0 < lo_y or b.y1 > hi_y:
                errs.append(f"  outside margin: {t.get_text()[:48]!r}")
        for (t1, b1), (t2, b2) in itertools.combinations(boxes, 2):
            if b1.overlaps(b2):
                errs.append(f"  overlap: {t1.get_text()[:30]!r} x {t2.get_text()[:30]!r}")
        if errs:
            raise RuntimeError("layout guard failed:\n" + "\n".join(errs))

    def save(self, stem):
        self.check()
        out = ROOT / "figures" / self.spec.variant
        out.mkdir(parents=True, exist_ok=True)
        paths = []
        for ext in ("pdf", "png"):
            p = out / f"{stem}.{ext}"
            self.fig.savefig(p, format=ext,
                             metadata={"CreationDate": None, "Producer": None}
                             if ext == "pdf" else None)
            paths.append(p)
        plt.close(self.fig)
        return paths


# ── frame: a plot area in inches, with house-style marks and labels ──────
class Frame:
    """
    An axes placed by its top-left corner (inches), plus helpers that draw marks
    in data space and put every text on the canvas, so the guards see all text.
    """
    def __init__(self, cv, x, y, w, h, xlim, ylim, xlog=False, ylog=False):
        self.cv, self.x, self.y, self.w, self.h = cv, x, y, w, h
        self.ax = cv.axes(x, y, w, h)
        if xlog: self.ax.set_xscale("log")
        if ylog: self.ax.set_yscale("log")
        self.ax.set_xlim(*xlim)
        self.ax.set_ylim(*ylim)
        self.ax.set_clip_on(False)

    # data -> canvas inches
    def at(self, xv, yv):
        px, py = self.ax.transData.transform((xv, yv))
        dpi = self.cv.fig.dpi
        return px / dpi, self.cv.h - py / dpi

    def X(self, xv):
        return self.at(xv, self.ax.get_ylim()[0])[0]

    def Y(self, yv):
        return self.at(self.ax.get_xlim()[0], yv)[1]

    @property
    def bottom(self): return self.y + self.h
    @property
    def right(self): return self.x + self.w

    # grid and rules
    def hgrid(self, ticks, color=C.rule, lw=0.5):
        x0, x1 = self.ax.get_xlim()
        for v in ticks:
            self.ax.plot([x0, x1], [v, v], color=color, lw=lw, zorder=0, clip_on=False)

    def vgrid(self, ticks, color=C.rule, lw=0.5, y0=None, y1=None):
        lo, hi = self.ax.get_ylim()
        for v in ticks:
            self.ax.plot([v, v], [lo if y0 is None else y0, hi if y1 is None else y1],
                         color=color, lw=lw, zorder=0, clip_on=False)

    def hbase(self, v, color=C.baseline, lw=0.9, z=3):
        x0, x1 = self.ax.get_xlim()
        self.ax.plot([x0, x1], [v, v], color=color, lw=lw, zorder=z, clip_on=False)

    def vbase(self, v, color=C.baseline, lw=0.9, z=3):
        y0, y1 = self.ax.get_ylim()
        self.ax.plot([v, v], [y0, y1], color=color, lw=lw, zorder=z, clip_on=False)

    # tick labels (canvas text)
    def yticks(self, ticks, labels=None, pad=0.05, color=C.ink_faint):
        labels = labels or [str(t) for t in ticks]
        for v, s in zip(ticks, labels):
            self.cv.text(self.x - pad, self.Y(v), s, T.tick, color=color,
                         ha="right", va="center")

    def xticks(self, ticks, labels=None, pad=0.05, color=C.ink_faint, marks=False):
        labels = labels or [str(t) for t in ticks]
        for v, s in zip(ticks, labels):
            self.cv.text(self.X(v), self.bottom + pad, s, T.tick, color=color,
                         ha="center", va="top")
            if marks:
                self.cv.line([self.X(v)] * 2, [self.bottom, self.bottom + 0.035],
                             color=C.rule_mid, lw=0.5)

    def ytitle(self, s, x=None, gap=0.09):
        """Horizontal y-axis title above the plot's top-left."""
        return self.cv.text(self.x if x is None else x, self.y - gap, s, T.axis,
                            color=C.ink_soft, ha="left", va="baseline")

    def xtitle(self, s, dy=None, ha="center"):
        dy = dy if dy is not None else 0.07 + T.s(T.tick) * 1.25 * PT
        x = {"center": self.x + self.w / 2, "right": self.right, "left": self.x}[ha]
        return self.cv.text(x, self.bottom + dy, s, T.axis, color=C.ink_soft,
                            ha=ha, va="top")

    # marks
    def dot(self, xv, yv, color, hollow=False, marker="o", size=None, z=5, ring=True):
        ms = size if size is not None else 5.6 * T.base / 8.4
        kw = dict(ms=ms, marker=marker, zorder=z, clip_on=False, ls="none")
        if hollow:
            self.ax.plot([xv], [yv], mfc=C.surface, mec=color, mew=1.1, **kw)
        else:
            self.ax.plot([xv], [yv], mfc=color, mec=C.surface if ring else color,
                         mew=1.0 if ring else 0, **kw)

    def whisker(self, xv, yv, err, axis="y", color=C.ink, lw=0.6, cap=1.7, z=4):
        """
        ± err around (xv, yv); cap = half-length of the caps in points.
        Drawn UNDER markers (z=4 < 5): a whisker shorter than the marker is hidden
        by it, and the caption says so. Over bars (z=4 > 2) it stays visible.
        """
        if axis == "y":
            xs, ys, m = [xv, xv], [yv - err, yv + err], "_"
        else:
            xs, ys, m = [xv - err, xv + err], [yv, yv], "|"
        self.ax.plot(xs, ys, color=color, lw=lw, zorder=z, clip_on=False,
                     marker=m, ms=2 * cap, mew=lw, solid_capstyle="butt")

    def label(self, xv, yv, s, role=None, dx=0.0, dy=0.0, ha="left", va="center",
              color=C.ink, weight=REGULAR, **kw):
        """Text anchored at a data point, offset in points (dy > 0 moves up)."""
        x_in, y_in = self.at(xv, yv)
        return self.cv.text(x_in + dx * PT, y_in - dy * PT, s, role, color=color,
                            weight=weight, ha=ha, va=va, **kw)


_T2P = None
def text_w(s, role, weight=REGULAR):
    """Rendered width of a one-line string, in inches (for composing labels)."""
    global _T2P
    from matplotlib.textpath import TextToPath
    from matplotlib.font_manager import FontProperties
    _T2P = _T2P or TextToPath()
    fp = FontProperties(family=FONT, weight=weight, size=T.s(role))
    w, _, _ = _T2P.get_text_width_height_descent(s, fp, ismath=False)
    return w * PT


KNOCKOUT = dict(boxstyle="square,pad=0.12", fc=C.surface, ec="none")


def data_file(name):
    import os
    base = Path(os.environ.get("UNDERTOW_DATA", ROOT / "data" / "derived"))
    p = base / name
    if not p.exists():
        raise FileNotFoundError(f"missing data file: data/derived/{name}")
    return p


def read_csv(name):
    import csv
    with open(data_file(name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
