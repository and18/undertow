"""
build_figures.py — regenerate every Undertow figure from data/derived, from scratch.

    make figures            (or: python3 analysis/build_figures.py)

For each figure module and each target (paper 4.80 in, narrow 3.33 in, editorial
6.20 in) it renders PDF + PNG, then writes next to the canonical paper output:
    <STEM>.caption.txt      the caption, versioned with the figure
    <STEM>.caption.tex      the same caption, escaped for pdfLaTeX (\\input by paper/)
    <STEM>.provenance.txt   claims, data files with sha256, runs, toolchain
Then it runs the QA pass (figure_qa.py) and writes figures/_qa/.

figures/ is deleted first: nothing stale can survive a build. All text files are
written as UTF-8, so the build behaves the same on Linux, macOS and Windows.
A figure whose data file is missing is reported and makes the build exit non-zero;
all the others are still built.
"""
import hashlib
import importlib
import platform
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import matplotlib
import figure_style as S

FIGURES = [
    "fig_01_marginal_vs_workingset",
    "fig_02_class_asymmetry",
    "fig_03_frontier",
    "fig_04_overlap_confounder",
    "fig_05_accounting",
    "fig_06_cpu_validation",
    "fig_07_why_sign_flips",
    "fig_a1_human_externality",
    "fig_a2_model_reference",
    "fig_a3_honeypot_calibration",
]
OUT = S.ROOT / "figures"


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


_TEX = [("\\", r"\textbackslash{}"), ("%", r"\%"), ("&", r"\&"), ("_", r"\_"), ("#", r"\#"),
        ("\u2212", "$-$"), ("\u00b1", r"$\pm$"), ("\u00d7", r"$\times$"), ("\u00f7", r"$\div$"),
        ("\u03b1", r"$\alpha$"), ("\u03b2", r"$\beta$"), ("\u03bb", r"$\lambda$"), ("\u2192", r"$\rightarrow$"),
        ("\u2248", r"$\approx$"), ("\u2264", r"$\leq$"), ("\u00b2", r"$^{2}$"),
        ("\u00b7", r"$\cdot$"), ("\u2013", "--"), ("\u2014", "---"), ("\u2019", "'")]


def latex(s):
    """Caption text made safe for pdfLaTeX (no Unicode left, specials escaped)."""
    for a, b in _TEX:
        s = s.replace(a, b)
    bad = sorted({c for c in s if ord(c) > 127})
    if bad:
        raise ValueError(f"caption has characters with no LaTeX mapping: {bad}")
    return s


def write_sidecars(mod):
    d = OUT / "paper"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{mod.STEM}.caption.txt").write_text(mod.CAPTION.strip() + "\n", encoding="utf-8")
    (d / f"{mod.STEM}.caption.tex").write_text(latex(mod.CAPTION.strip()) + "\n", encoding="utf-8")
    lines = [f"figure     {mod.STEM}",
             f"claims     {mod.CLAIMS}",
             "data"]
    for name in mod.DATA:
        p = S.data_file(name)
        lines.append(f"           data/derived/{name}  sha256:{sha256(p)}")
    lines.append("runs")
    lines += [f"           {r}" for r in mod.RUNS]
    lines += [f"script     analysis/{mod.__name__}.py  sha256:{sha256(mod.__file__)}",
              f"style      analysis/figure_style.py  sha256:{sha256(S.__file__)}",
              f"targets    paper 4.80 in (canonical) · narrow 3.33 in · editorial 6.20 in",
              f"toolchain  python {platform.python_version()} · matplotlib "
              f"{matplotlib.__version__} · font {S.FONT}",
              "rebuild    make figures"]
    (d / f"{mod.STEM}.provenance.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    shutil.rmtree(OUT, ignore_errors=True)      # nothing stale survives, old targets included
    missing, built = [], []
    for name in FIGURES:
        mod = importlib.import_module(name)
        try:
            for v in S.VARIANTS:
                for p in mod.render(v):
                    built.append(p)
            write_sidecars(mod)
            print(f"ok       {mod.STEM}")
        except FileNotFoundError as e:
            missing.append((mod.STEM, str(e)))
            print(f"MISSING  {mod.STEM}: {e}")
            for v in S.VARIANTS:                  # never leave a partial set behind
                for ext in ("pdf", "png"):
                    (OUT / v / f"{mod.STEM}.{ext}").unlink(missing_ok=True)
    import figure_qa
    figure_qa.run(FIGURES)
    print(f"\n{len(built)} files written to figures/, QA in figures/_qa/")
    if missing:
        print("\nNOT BUILT (data missing):")
        for stem, err in missing:
            print(f"  {stem}: {err}")
        sys.exit(2)


if __name__ == "__main__":
    main()
