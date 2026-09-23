"""
build_figures.py — regenerate every Undertow figure from data/derived, from scratch.

    make figures            (or: python3 analysis/build_figures.py)

For each figure module and each target (paper 4.80 in, narrow 3.33 in, editorial
6.20 in) it renders PDF + PNG, then writes next to the canonical paper output:
    <STEM>.caption.txt      the caption, versioned with the figure
    <STEM>.provenance.txt   claims, data files with sha256, runs, toolchain
Then it runs the QA pass (figure_qa.py) and writes figures/_qa/.

Output directories are deleted first: nothing stale can survive a build.
A figure whose data file is missing is reported and makes the build exit non-zero;
all the others are still built.
"""
import hashlib
import importlib
import platform
import shutil
import subprocess
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
    "fig_a1_human_externality",
    "fig_a2_model_reference",
    "fig_a3_honeypot_calibration",
]
OUT = S.ROOT / "figures"


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def git_rev():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=S.ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "not a git checkout"


def write_sidecars(mod):
    d = OUT / "paper"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{mod.STEM}.caption.txt").write_text(mod.CAPTION.strip() + "\n")
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
              f"commit     {git_rev()}",
              "rebuild    make figures"]
    (d / f"{mod.STEM}.provenance.txt").write_text("\n".join(lines) + "\n")


def main():
    for sub in list(S.VARIANTS) + ["_qa"]:
        shutil.rmtree(OUT / sub, ignore_errors=True)
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
