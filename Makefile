# On Windows without make, run: python analysis/build_figures.py
PY ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: figures clean-figures

# Rebuild every figure (paper 4.80 in, narrow 3.33 in, editorial 6.20 in),
# captions, provenance and the QA proofs, from data/derived only.
figures:
	$(PY) analysis/build_figures.py

clean-figures:
	rm -rf figures

.PHONY: paper
# Build the paper PDF (needs a LaTeX installation with latexmk). Run make figures first.
paper:
	cd paper && latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
