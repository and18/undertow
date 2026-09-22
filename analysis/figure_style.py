"""
figure_style.py — the single visual identity for every Undertow figure (v3).

No figure sets its own style. If a figure needs a colour, a size or a string
that is not here, it is added here.

LAYOUT MODEL
  Every figure is drawn on a Canvas of EXACT size: width from the venue
  template, height computed by the figure from its own content. Positions are
  given in inches from the top-left corner, like a page layout, and nothing is
  cropped afterwards (no bbox="tight"). Two consequences:
    - every figure of the same width has the same margins, header and footer;
    - whitespace is designed, not left over.

TWO RENDER MODES, ONE SPECIFICATION
  paper      Venue-ready. No headline (the caption carries it), minimal margin,
             exact column width. This is what goes in the PDF.
  editorial  Thesis, web, slides. Adds the grammar of editorial charts:
             an accent rule, a headline that STATES THE FINDING, a deck that
             gives the setup, and a source line under a hairline.
             The data layer is identical in both modes.

  The headline must be a claim marked MISURATO or SOSTENUTO in docs/claims.md.
  It may be shorter than the claim; it may never be stronger.

BUILD GUARDS (a figure that fails one does not get written)
  glyphs    every character must exist in Inter — no tofu boxes in a PDF;
  bounds    no text may cross the canvas margin;
  overlap   no two texts may overlap.

COLOUR
  Three traffic classes, validated with validate_palette.js across ALL pairs:
  worst deutan Delta-E 9.2 (target 8), worst normal-vision Delta-E 24.0 (floor
  15). Known warning: the agentic aqua is below 3:1 contrast on white, so an
  agentic mark ALWAYS carries a direct value label. Colour follows the entity,
  never its state or rank. Text never takes a series colour.

WIDTHS (inches, from the venue templates)
  acm-col   3.33   ACM sigconf single column (HotNets, IMC)   — the severe case
  lncs      4.80   Springer LNCS text width, 122 mm (PAM)     — default
  acm-full  7.00   ACM sigconf full width
  editorial 6.20   thesis, web, slides

FONT
  Inter (SIL Open Font License 1.1, see fonts/OFL.txt), bundled in the repo.
  Embedded in PDFs as TrueType (fonttype 42): text stays selectable text.
"""
from pathlib import Path
import itertools
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ft2font import FT2Font

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# ── typography ────────────────────────────────────────────────────────────
_FONTS = HERE / "fonts"
for _f in sorted(_FONTS.glob("Inter-*.ttf")):
    font_manager.fontManager.addfont(str(_f))
if not list(_FONTS.glob("Inter-*.ttf")):
    raise SystemExit("analysis/fonts/Inter-*.ttf missing — the house font is part of the build")
FONT = "Inter"

# ── colour tokens ─────────────────────────────────────────────────────────
class C:
    human      = "#2a78d6"   # blue    — human class
    exhaustive = "#eb6834"   # orange  — exhaustive class
    agentic    = "#1baf7a"   # aqua    — agentic class (direct label required)

    ink        = "#121212"   # headline, values, key labels
    ink_soft   = "#55554f"   # deck, direction labels
    ink_faint  = "#8a8a83"   # secondary lines, ticks, source
    rule       = "#e4e4de"   # gridlines
    rule_dark  = "#5f5f59"   # table rules
    wash       = "#f6f6f2"   # background regions, very sparingly
    surface    = "#ffffff"
    reference  = "#6f6f69"   # model curves, baselines — never a result

CLASS_COLOR = {"human": C.human, "exhaustive": C.exhaustive, "agentic": C.agentic}

WIDTH = {"acm-col": 3.33, "lncs": 4.80, "acm-full": 7.00, "editorial": 6.20}

MINUS = "−"
def num(x, dec=3, sign=False):
    """Number with a true minus sign; '+' only when asked."""
    s = f"{abs(x):.{dec}f}"
    if x < 0 and float(s) != 0:
        return MINUS + s
    return ("+" + s) if (sign and x > 0) else s

# ── type scale: one base per width, every size a multiple of it ───────────
def base_size(width_in):
    # 7.4 pt at the severe 3.33" column, up to +16% when there is room.
    return 7.4 * max(1.0, min(1.16, (width_in / 3.33) ** 0.22))

class T:
    """Type roles, as multiples of the base size. Nothing prints under 6 pt."""
    headline = 1.65   # editorial headline, bold
    deck     = 1.02   # editorial deck
    key      = 1.13   # the row / series key a reader looks up ("0.19× cache")
    value    = 1.18   # a direct value label, semibold
    sub      = 0.82   # second line under a key or a value
    caps     = 0.78   # column headers, uppercase
    label    = 0.86   # direction labels, axis titles, tags
    tick     = 0.78   # tick labels
    source   = 0.81   # source line
    base     = 7.4
    @classmethod
    def s(cls, role): return max(6.0, cls.base * role)

def _rc(width_in):
    T.base = base_size(width_in)
    return {
        "font.family": FONT, "font.size": T.base,
        "text.color": C.ink, "axes.labelcolor": C.ink_soft,
        "figure.facecolor": C.surface, "axes.facecolor": "none",
        "savefig.facecolor": C.surface,
        "axes.edgecolor": C.ink_soft, "axes.linewidth": 0.7,
        "xtick.color": C.ink_faint, "ytick.color": C.ink_faint,
        "axes.grid": False, "legend.frameon": False,
        "lines.solid_capstyle": "butt",
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
        "figure.dpi": 110, "savefig.dpi": 400,
        "savefig.bbox": None, "savefig.pad_inches": 0,
    }

PT = 1 / 72.0   # one point, in inches


# ── canvas ────────────────────────────────────────────────────────────────
class Canvas:
    """
    An exact-size page. All positions in INCHES FROM THE TOP-LEFT corner.

        H = Canvas.height(body_h, width, mode, headline, deck, source)
        cv = Canvas(width, mode, H)
        y  = cv.header(headline, deck)   # editorial only; returns the body top
        ... draw the body between y and cv.body_bottom ...
        cv.footer(source)                # editorial only
        cv.save(stem, subdir)
    """
    MARGIN = {"paper": 0.03, "editorial": 0.30}
    GAP_BODY = 0.24       # header -> body
    GAP_FOOT = 0.20       # body -> footer rule

    def __init__(self, width, mode, height):
        self.w = WIDTH[width] if isinstance(width, str) else width
        self.mode, self.h = mode, height
        self.m = self.MARGIN[mode]
        mpl.rcParams.update(_rc(self.w))
        self.fig = plt.figure(figsize=(self.w, self.h))
        self.body_bottom = self.h - self.m - (self._foot_h(None) if mode == "editorial" else 0)

    # geometry ------------------------------------------------------------
    def fx(self, x): return x / self.w
    def fy(self, y): return 1 - y / self.h
    @property
    def left(self): return self.m
    @property
    def right(self): return self.w - self.m

    def text(self, x, y, s, role, **kw):
        kw.setdefault("color", C.ink)
        return self.fig.text(self.fx(x), self.fy(y), s, fontsize=T.s(role), **kw)

    def hline(self, x0, x1, y, color=C.rule_dark, lw=0.6):
        self.fig.add_artist(mpl.lines.Line2D([self.fx(x0), self.fx(x1)], [self.fy(y)] * 2,
                            color=color, lw=lw, solid_capstyle="butt"))

    def axes(self, x, y, w, h):
        """Axes placed by its top-left corner, in inches. Frameless by default."""
        ax = self.fig.add_axes([self.fx(x), self.fy(y + h), w / self.w, h / self.h])
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
        ax.patch.set_visible(False)
        return ax

    # editorial frame -----------------------------------------------------
    @staticmethod
    def _lines(s): return s.count("\n") + 1

    @classmethod
    def _head_h(cls, headline, deck):
        return (0.14 + cls._lines(headline) * T.s(T.headline) * 1.14 * PT
                + 0.15 + cls._lines(deck) * T.s(T.deck) * 1.42 * PT)

    @classmethod
    def _foot_h(cls, source):
        n = cls._lines(source) if source else 2
        return cls.GAP_FOOT + 0.10 + n * T.s(T.source) * 1.42 * PT

    @classmethod
    def height(cls, body_h, width, mode, headline="", deck="", source=""):
        w = WIDTH[width] if isinstance(width, str) else width
        T.base = base_size(w)
        m = cls.MARGIN[mode]
        if mode == "paper":
            return round(m + body_h + m, 3)
        return round(m + cls._head_h(headline, deck) + cls.GAP_BODY + body_h
                     + cls._foot_h(source) + m, 3)

    def header(self, headline, deck):
        if self.mode != "editorial":
            return self.m
        y = self.m
        self.fig.add_artist(mpl.lines.Line2D([self.fx(self.left), self.fx(self.left + 0.34)],
                            [self.fy(y)] * 2, color=C.ink, lw=3.0, solid_capstyle="butt"))
        y += 0.14
        self.text(self.left, y, headline, T.headline, ha="left", va="top",
                  fontweight=700, linespacing=1.12)
        y += self._lines(headline) * T.s(T.headline) * 1.14 * PT + 0.15
        self.text(self.left, y, deck, T.deck, ha="left", va="top",
                  color=C.ink_soft, linespacing=1.40)
        y += self._lines(deck) * T.s(T.deck) * 1.42 * PT
        return y + self.GAP_BODY

    def footer(self, source):
        if self.mode != "editorial":
            return
        self.body_bottom = self.h - self.m - self._foot_h(source)
        y = self.body_bottom + self.GAP_FOOT
        self.hline(self.left, self.right, y, color=C.rule, lw=0.6)
        self.text(self.left, y + 0.10, source, T.source, ha="left", va="top",
                  color=C.ink_faint, linespacing=1.40)

    # guards + output -----------------------------------------------------
    def _texts(self):
        return [t for t in self.fig.findobj(mpl.text.Text)
                if t.get_visible() and t.get_text().strip()]

    def check(self, allow_overlap=()):
        self.fig.canvas.draw()
        r = self.fig.canvas.get_renderer()
        texts = self._texts()
        _check_glyphs(texts)
        dpi = self.fig.dpi
        boxes = [(t, t.get_window_extent(r)) for t in texts]
        lo_x, hi_x = self.m * dpi - 0.5, (self.w - self.m) * dpi + 0.5
        lo_y, hi_y = self.m * dpi - 0.5, (self.h - self.m) * dpi + 0.5
        errs = []
        for t, b in boxes:
            if b.x0 < lo_x or b.x1 > hi_x or b.y0 < lo_y or b.y1 > hi_y:
                errs.append(f"  outside margin: {t.get_text()[:40]!r}")
        for (t1, b1), (t2, b2) in itertools.combinations(boxes, 2):
            pair = {t1.get_text(), t2.get_text()}
            if any(pair == set(a) for a in allow_overlap):
                continue
            if b1.overlaps(b2):
                errs.append(f"  overlap: {t1.get_text()[:30]!r} x {t2.get_text()[:30]!r}")
        if errs:
            raise RuntimeError("layout guard failed:\n" + "\n".join(errs))

    def save(self, stem, subdir, allow_overlap=()):
        self.check(allow_overlap)
        out = ROOT / "figures" / subdir
        out.mkdir(parents=True, exist_ok=True)
        paths = []
        for ext in ("pdf", "png"):
            p = out / f"{stem}.{ext}"
            self.fig.savefig(p, format=ext,
                             metadata={"CreationDate": None} if ext == "pdf" else None)
            paths.append(p)
        plt.close(self.fig)
        return paths


# ── glyph guard: a missing glyph fails the build, it never ships as a box ─
_CMAP = None
def _check_glyphs(texts):
    global _CMAP
    if _CMAP is None:
        _CMAP = set(FT2Font(str(_FONTS / "Inter-400.ttf")).get_charmap().keys())
    missing = {}
    for t in texts:
        for ch in t.get_text():
            if ch not in "\n\t" and ord(ch) not in _CMAP:
                missing.setdefault(ch, t.get_text()[:40])
    if missing:
        lines = [f"  U+{ord(c):04X} {c!r} in: {ctx!r}" for c, ctx in missing.items()]
        raise RuntimeError("glyphs missing from Inter — replace them:\n" + "\n".join(lines))
