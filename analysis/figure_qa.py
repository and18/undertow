"""
figure_qa.py — the visual QA pass, run by build_figures.py after every build.

Checks (a failure stops the build):
  vector    every PDF contains no raster image;
  fonts     every PDF embeds its fonts as TrueType, and only the house font;
  size      every PDF page is exactly the target width;
Proofs written to figures/_qa/ for looking at, not for the paper:
  contact_<target>.png            all figures of one target at 150 px per inch,
                                  i.e. close to printed size on a normal screen
  contact_<target>_grayscale.png  the same in grayscale (print / CVD proof)
  report.txt                      what was checked, per file
(The glyph, margin and text-overlap guards run earlier, inside Canvas.save.)
"""
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import figure_style as S

QA = S.ROOT / "figures" / "_qa"
PPI = 150


def _pdf_checks(p, width_in):
    raw = p.read_bytes()
    errs = []
    if re.search(rb"/Subtype\s*/Image", raw):
        errs.append("contains a raster image")
    fonts = set(re.findall(rb"/BaseFont\s*/([A-Za-z0-9+\-_]+)", raw))
    if not re.search(rb"/FontFile2", raw):
        errs.append("fonts not embedded as TrueType")
    foreign = [f.decode() for f in fonts if b"SourceSans3" not in f]
    if foreign:
        errs.append(f"non-house fonts: {foreign}")
    m = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)\s*\]", raw)
    w = float(m.group(1)) / 72 if m else 0
    if abs(w - width_in) > 0.01:
        errs.append(f"page width {w:.3f} in, expected {width_in}")
    h = float(m.group(2)) / 72 if m else 0
    return errs, sorted(f.decode().split("+")[-1] for f in fonts), w, h


def _sheet(pngs, out, gray=False):
    font = ImageFont.truetype(str(S.FONT_DIR / "SourceSans3-Semibold.ttf"), 22)
    ims = []
    for p in pngs:
        im = Image.open(p).convert("L" if gray else "RGB")
        scale = PPI / 400
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        ims.append((p.stem, im))
    cols = 3 if ims and ims[0][1].width < 600 else 2
    cw = max(i.width for _, i in ims) + 60
    rows = [ims[i:i + cols] for i in range(0, len(ims), cols)]
    heights = [max(i.height for _, i in r) + 70 for r in rows]
    sheet = Image.new("L" if gray else "RGB", (cols * cw + 40, sum(heights) + 40), "white")
    d = ImageDraw.Draw(sheet)
    y = 20
    for r, h in zip(rows, heights):
        for k, (name, im) in enumerate(r):
            x = 20 + k * cw
            d.text((x, y), name, fill="black", font=font)
            sheet.paste(im, (x, y + 38))
            d.rectangle([x - 1, y + 37, x + im.width, y + 38 + im.height], outline="#dddddd")
        y += h
    sheet.save(out)


def run(figures):
    QA.mkdir(parents=True, exist_ok=True)
    report, failures = [], []
    for v, (width, _) in S.VARIANTS.items():
        d = S.ROOT / "figures" / v
        pdfs = sorted(d.glob("*.pdf")) if d.exists() else []
        for p in pdfs:
            errs, fonts, w, h = _pdf_checks(p, width)
            status = "FAIL " + "; ".join(errs) if errs else "ok"
            report.append(f"{v:9s} {p.stem:40s} {w:.2f} x {h:.2f} in  fonts: "
                          f"{', '.join(fonts)}  {status}")
            if errs:
                failures.append(f"{v}/{p.name}: {'; '.join(errs)}")
        pngs = sorted(d.glob("*.png")) if d.exists() else []
        if pngs:
            _sheet(pngs, QA / f"contact_{v}.png")
            _sheet(pngs, QA / f"contact_{v}_grayscale.png", gray=True)
    (QA / "report.txt").write_text(
        "Undertow figure QA\n"
        "checks: vector (no raster), TrueType-embedded house font only, exact page width;\n"
        "glyph / margin / text-overlap guards ran at render time.\n\n"
        + "\n".join(report) + "\n", encoding="utf-8")
    if failures:
        raise SystemExit("QA failed:\n  " + "\n  ".join(failures))
