"""
figure_style.py — the single visual identity for every Undertow figure.

No figure sets its own style. If a figure needs a colour, a size or a string
that is not here, it is added here.

TWO RENDER MODES, ONE SPECIFICATION
  paper      Venue-ready. No title inside the figure (the caption carries it),
             tight margins, exact column width. This is what goes in the PDF.
  editorial  For the thesis, website, slides and posts. Adds the grammar that
             makes editorial charts (FT, The Economist, Il Sole 24 Ore) work:
             a headline that STATES THE FINDING, a deck that gives the setup,
             and a source line. The data layer is identical in both modes.

  The headline of an editorial figure must be a claim marked MISURATO or
  SOSTENUTO in docs/claims.md. It may be shorter than the claim; it may never
  be stronger.

COLOUR
  Three traffic classes, validated with validate_palette.js across ALL pairs
  (not only adjacent ones): worst deutan Delta-E 9.2 (target 8), worst
  normal-vision Delta-E 24.0 (floor 15). One known warning: the agentic aqua
  is below 3:1 contrast on white, so the agentic class ALWAYS carries a direct
  label. That is the condition that makes the colour legitimate, not a style
  preference.

  Colour follows the entity, never its state or rank. Shared versus separated
  working sets are told apart by filled versus hollow markers, not by a fourth
  colour. Text never takes a series colour: values and labels stay in ink.

WIDTHS (inches, from the venue templates)
  acm-col   3.33   ACM sigconf single column (HotNets, IMC)   — the severe case
  lncs      4.80   Springer LNCS text width, 122 mm (PAM)     — default
  acm-full  7.00   ACM sigconf full width
  editorial 6.20   thesis, web, slides

FONT
  Inter (SIL Open Font License 1.1, see fonts/OFL.txt), bundled in the repo so
  that every machine renders identically. Embedded in PDFs as TrueType
  (fonttype 42): text stays text, selectable and searchable.
"""
from pathlib import Path
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# ── typography ────────────────────────────────────────────────────────────
_FONTS = HERE / "fonts"
for _f in sorted(_FONTS.glob("Inter-*.ttf")):
    font_manager.fontManager.addfont(str(_f))
FONT = "Inter" if list(_FONTS.glob("Inter-*.ttf")) else "DejaVu Sans"
if FONT != "Inter":
    import warnings
    warnings.warn("Inter not found in analysis/fonts — figures will not match the house style")

# ── colour tokens ─────────────────────────────────────────────────────────
class C:
    human      = "#2a78d6"   # blue    — human class
    exhaustive = "#eb6834"   # orange  — exhaustive class
    agentic    = "#1baf7a"   # aqua    — agentic class (direct label required)

    ink        = "#121212"   # primary text, values
    ink_soft   = "#55554f"   # axis labels, deck
    ink_faint  = "#8a8a83"   # annotations, source line
    rule       = "#dcdcd5"   # grid, leaders
    rule_dark  = "#5f5f59"   # semantic rules (zero line)
    wash       = "#f6f6f2"   # background regions, very sparingly
    surface    = "#ffffff"
    reference  = "#6f6f69"   # model curves, baselines — never a result

CLASS_COLOR = {"human": C.human, "exhaustive": C.exhaustive, "agentic": C.agentic}

WIDTH = {"acm-col": 3.33, "lncs": 4.80, "acm-full": 7.00, "editorial": 6.20}

# ── language ──────────────────────────────────────────────────────────────
LANG = "en"
_STR = {
    "en": {"source": "Source", "human": "human", "exhaustive": "exhaustive",
           "agentic": "agentic"},
    "it": {"source": "Fonte", "human": "umana", "exhaustive": "esaustiva",
           "agentic": "agentica"},
}
def t(key): return _STR[LANG].get(key, key)

MINUS = "−"
def num(x, dec=3, sign=False):
    """Number in the active language: true minus sign, decimal point or comma."""
    s = f"{abs(x):.{dec}f}"
    if LANG == "it":
        s = s.replace(".", ",")
    if x < 0:
        return MINUS + s
    return ("+" + s) if sign else s

# ── size system: one base, derived everywhere ─────────────────────────────
def _base(width_in):
    # 7.4 pt at the severe 3.33" column, gently larger when there is room.
    return 7.4 * max(1.0, min(1.16, (width_in / 3.33) ** 0.22))

class T:
    """Type scale, in multiples of the base size. Set by figure()."""
    base = 7.4
    @classmethod
    def s(cls, k): return cls.base * k
    headline, deck, label, tick, value, value_sub, note, source = (
        1.62, 1.06, 1.00, 0.92, 1.04, 0.82, 0.90, 0.80)

def _rc(width_in):
    b = _base(width_in); T.base = b
    return {
        "font.family": FONT, "font.size": b,
        "axes.labelsize": b * T.label, "xtick.labelsize": b * T.tick,
        "ytick.labelsize": b * T.tick, "legend.fontsize": b * T.tick,

        "figure.facecolor": C.surface, "axes.facecolor": C.surface,
        "savefig.facecolor": C.surface,

        "axes.edgecolor": C.ink_soft, "axes.linewidth": 0.7,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.labelcolor": C.ink_soft, "axes.labelpad": 5,

        "xtick.color": C.ink_soft, "ytick.color": C.ink_soft,
        "xtick.direction": "out", "ytick.direction": "out",
        "xtick.major.size": 3.0, "ytick.major.size": 0.0,
        "xtick.minor.size": 1.8, "xtick.major.width": 0.7,
        "xtick.major.pad": 4, "ytick.major.pad": 5,

        "axes.grid": True, "axes.grid.axis": "y",
        "grid.color": C.rule, "grid.linewidth": 0.6,
        "axes.axisbelow": True,

        "lines.linewidth": 1.6, "lines.solid_capstyle": "round",
        "legend.frameon": False,

        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
        "figure.dpi": 110, "savefig.dpi": 400,
        "savefig.bbox": "tight", "savefig.pad_inches": 0.03,
    }

def figure(width="lncs", ratio=0.62, mode="paper", **kw):
    """Open a figure at the requested column width with the house style."""
    w = WIDTH[width] if isinstance(width, str) else width
    mpl.rcParams.update(_rc(w))
    fig, ax = plt.subplots(figsize=(w, w * ratio), **kw)
    fig._undertow = {"mode": mode, "width": w}
    return fig, ax

def spine_offset(ax, pts=4):
    """Detach the remaining spines from the data: removes the default look."""
    ax.spines["left"].set_visible(False)            # y spine off: gridlines carry y
    ax.spines["bottom"].set_position(("outward", pts))

def value_label(ax, x, y, main, sub=None, where="above", gap=7):
    """
    A value in ink, with an optional quieter second line (e.g. "± 0.005").
      where="above"  both lines stacked above the point, value on top
      where="right"  both lines to the right of the point, value on top
      where="below"  both lines below the point, value on top
    """
    ms, ss = T.s(T.value), T.s(T.value_sub)
    kw_main = dict(textcoords="offset points", fontsize=ms, color=C.ink,
                   fontweight=600, zorder=10)
    kw_sub  = dict(textcoords="offset points", fontsize=ss, color=C.ink_faint,
                   zorder=10)
    if where == "above":
        if sub:
            ax.annotate(sub,  (x, y), xytext=(0, gap), ha="center", va="bottom", **kw_sub)
            ax.annotate(main, (x, y), xytext=(0, gap + ss * 1.25), ha="center",
                        va="bottom", **kw_main)
        else:
            ax.annotate(main, (x, y), xytext=(0, gap), ha="center", va="bottom", **kw_main)
    elif where == "below":
        ax.annotate(main, (x, y), xytext=(0, -gap), ha="center", va="top", **kw_main)
        if sub:
            ax.annotate(sub, (x, y), xytext=(0, -gap - ms * 1.25), ha="center",
                        va="top", **kw_sub)
    elif where == "below-right":          # for a point on a rising line
        ax.annotate(main, (x, y), xytext=(gap, -gap * 0.35), ha="left", va="top", **kw_main)
        if sub:
            ax.annotate(sub, (x, y), xytext=(gap, -gap * 0.35 - ms * 1.25), ha="left",
                        va="top", **kw_sub)
    elif where == "right":
        if sub:
            ax.annotate(main, (x, y), xytext=(gap + 2, ms * 0.50), ha="left",
                        va="center", **kw_main)
            ax.annotate(sub,  (x, y), xytext=(gap + 2, -ss * 0.80), ha="left",
                        va="center", **kw_sub)
        else:
            ax.annotate(main, (x, y), xytext=(gap + 2, 0), ha="left", va="center", **kw_main)
    else:
        raise ValueError(where)

def note(ax, x, y, text, **kw):
    kw.setdefault("ha", "left"); kw.setdefault("va", "center")
    kw.setdefault("color", C.ink_faint)
    return ax.annotate(text, (x, y), fontsize=T.s(T.note), **kw)

# ── editorial frame ───────────────────────────────────────────────────────
def editorial_frame(fig, ax, headline, deck, source):
    """Headline + deck above, source below, all aligned to ONE left margin."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    bb = ax.get_tightbbox(r).transformed(fig.transFigure.inverted())
    left = bb.x0
    top  = ax.get_position().y1
    H = fig.get_figheight() * 72.0                    # figure height in points
    gap = lambda pts: pts / H
    # accent rule, headline, deck — stacked upward from the axes top
    y_deck = max(top, bb.y1) + gap(T.s(T.tick) * 1.2)
    y_head = y_deck + gap(T.s(T.deck) * 1.40 * (deck.count("\n") + 1) + T.s(T.headline) * 0.35)
    fig.text(left, y_deck, deck, ha="left", va="bottom", fontsize=T.s(T.deck),
             color=C.ink_soft, linespacing=1.35)
    fig.text(left, y_head, headline, ha="left", va="bottom",
             fontsize=T.s(T.headline), color=C.ink, fontweight=700, linespacing=1.15)
    y_bar = y_head + gap(T.s(T.headline) * 1.18 * (headline.count("\n") + 1) + 5)
    fig.add_artist(mpl.lines.Line2D([left, left + 0.055], [y_bar, y_bar],
                   transform=fig.transFigure, color=C.ink, lw=2.4,
                   solid_capstyle="butt"))
    # source line under everything
    y_src = bb.y0 - gap(T.s(T.source) * 1.9)
    src = fig.text(left, y_src, source, ha="left", va="top", fontsize=T.s(T.source),
                   color=C.ink_faint, linespacing=1.35)
    # Width guard: editorial text must never be wider than the chart it frames,
    # otherwise bbox="tight" silently widens the figure and shrinks the plot.
    fig.canvas.draw()
    right = ax.get_tightbbox(r).transformed(fig.transFigure.inverted()).x1
    for t_ in fig.texts:
        x1 = t_.get_window_extent(r).transformed(fig.transFigure.inverted()).x1
        if x1 > right + 1e-3:
            raise RuntimeError(f"editorial text wider than the chart — add a line break: "
                               f"{t_.get_text()[:50]!r}")


# ── glyph guard: a missing glyph fails the build, it never ships as a box ─
from matplotlib.ft2font import FT2Font as _FT2Font
_CMAP = None
def _check_glyphs(fig):
    global _CMAP
    if FONT != "Inter":
        return
    if _CMAP is None:
        _CMAP = set(_FT2Font(str(_FONTS / "Inter-400.ttf")).get_charmap().keys())
    missing = {}
    for txt in fig.findobj(mpl.text.Text):
        for ch in txt.get_text():
            if ch in "\n\t" or ch == "$":
                continue
            if ord(ch) not in _CMAP:
                missing.setdefault(ch, txt.get_text()[:40])
    if missing:
        lines = [f"  U+{ord(c):04X} {c!r} in: {ctx!r}" for c, ctx in missing.items()]
        raise RuntimeError("glyphs missing from Inter — replace them:\n" + "\n".join(lines))

def save(fig, stem, subdir):
    out = ROOT / "figures" / subdir
    out.mkdir(parents=True, exist_ok=True)
    _check_glyphs(fig)
    paths = []
    for ext in ("pdf", "png"):
        p = out / f"{stem}.{ext}"
        fig.savefig(p, format=ext, metadata={"CreationDate": None} if ext == "pdf" else None)
        paths.append(p)
    plt.close(fig)
    return paths
