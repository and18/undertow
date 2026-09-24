# On Windows without make, run: python analysis/build_figures.py
PY ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

.PHONY: figures clean-figures

# Rebuild every figure (paper 4.80 in, narrow 3.33 in, editorial 6.20 in),
# captions, provenance and the QA proofs, from data/derived only.
figures:
	$(PY) analysis/build_figures.py

clean-figures:
	rm -rf figures

# Regenerate data/derived from the runs on the lab (read only: ssh lab cat), see
# data/derived/MANIFEST.csv. data-vm also needs the VictoriaMetrics tunnel on
# localhost:8428 (usage in tools/cache_capacity.py); fig01 and figA read
# cache_capacity.csv, so data-vm runs first. figA3_honeypot.csv is not regenerated:
# the honeypot scripts cannot restrict the log period to the frozen one.
.PHONY: data data-vm data-lab
data: data-vm data-lab

data-vm:
	@curl -sf -o /dev/null http://localhost:8428/health || \
		{ echo "VictoriaMetrics non raggiungibile su localhost:8428: apri il tunnel (tools/cache_capacity.py)"; exit 1; }
	$(PY) tools/cache_capacity.py
	$(PY) tools/cpu_validation.py

data-lab:
	$(PY) tools/fig01_data.py
	$(PY) tools/class_miss_by_scope.py
	$(PY) tools/fig02b_data.py
	$(PY) tools/fig03_data.py
	$(PY) tools/fig04_data.py
	$(PY) tools/fig05_data.py
	$(PY) tools/figA_data.py

.PHONY: paper
# Build the paper PDF (needs a LaTeX installation with latexmk). Run make figures first.
paper:
	cd paper && latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
