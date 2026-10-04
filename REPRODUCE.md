# Reproducing Undertow

What a third party can reproduce from this repository, at four levels, from the cheapest
to the most expensive. Each level says what works, what it needs, and what it **cannot**
give you. Levels 1 and 2 run on a laptop in minutes. Level 3 is not available outside the
author's machines. Level 4 rebuilds the experiment, not the numbers.

| level | what you get | needs | available to a third party |
|---|---|---|---|
| 1 | every figure of the paper, from the published data | Python 3.12, three pinned packages | **yes**, verified byte-identical |
| 2 | the cache simulator and the post-hoc characteristic-time model | Python 3.12 (standard library only), a git clone | **yes**, except the phase 1 comparison and the object-size measurement |
| 3 | `data/derived/` from the raw runs and the honeypot logs | the lab server, VictoriaMetrics, the log snapshot | **no**: raw runs and logs are not published |
| 4 | a new campaign on your own hardware | 6 physical cores, Docker, k6, the corpus | **yes**, but absolute numbers do not transfer |

---

## Level 1: figures from published data

```bash
git clone https://github.com/and18/undertow.git && cd undertow
python3 -m venv .venv && .venv/bin/pip install -r analysis/requirements-figures.txt
make figures            # on Windows without make: python analysis/build_figures.py
```

The build deletes `figures/`, regenerates every figure from `data/derived/` alone (paper,
narrow and editorial widths, with captions and provenance), and runs a QA pass that refuses
missing glyphs, text outside the margins and overlapping labels. About 30 seconds. It writes
60 files: ten figures at three widths, PDF and PNG each. Only the paper width (20 PDF and PNG
files in `figures/paper/`) is versioned; `figures/narrow/` and `figures/editorial/` are
regenerated and ignored by git, like `figures/_qa/`.

**Verified on 3 October 2026** (Python 3.12.3, matplotlib 3.10.9, Linux): rebuilding from a
fresh clone gives PDF and PNG files byte-identical to the 20 committed ones, and `git status`
stays clean. PDFs are written without a creation date, so identical inputs give identical
bytes. A different matplotlib or FreeType version can change PNG pixels without changing the
content.

*Line endings, fixed on 3 October 2026.* Until then
`figures/paper/FIG-06_cpu-validation.provenance.txt` recorded the SHA-256 of
`data/derived/fig06_cpu_validation.csv` as it was on the author's disk, with CRLF line
endings, so a fresh clone wrote a different hash on that one line. `tools/cpu_validation.py`
now writes the CSV with `lineterminator="\n"`, and the provenance was regenerated from the
committed file (hash `2d5469895e0efedc`). The data values did not change: writing the committed
rows with the new setting reproduces the committed file byte for byte (6 rows), while the old
setting wrote CRLF on every row. The CSV itself was not regenerated from the lab, whose raw
runs are not reachable from here.

Every figure's provenance file lists the claims it supports (`docs/claims.md`), the data
files with their hashes, and the runs they came from (`docs/registry.csv`).

### Building the paper

`make paper` (or `cd paper && latexmk -pdf main.tex`) needs a LaTeX installation with
`latexmk` and the figures from `make figures`. It also needs `llncs.cls` and `splncs04.bst`
from Springer's LNCS class, which are **not included** in this repository: download them from
Springer and put them where LaTeX finds them (for instance in `paper/`).

## Level 2: simulator and post-hoc model

These scripts use only the Python standard library and read only files that are in the
repository.

```bash
python3 tools/che_posthoc.py           # characteristic-time model, claim B7 (post hoc)
python3 tools/sim/test_policies.py     # unit gate of the replacement policies
python3 tools/sim/fase2.py r0          # simulator phase 2 (pre-registered), step 1
python3 tools/sim/fase2.py calibra     # step 2
python3 tools/sim/fase2.py g0r         # step 3
python3 tools/sim/fase2.py lancio      # step 4, then the criteria
python3 tools/sim/fase2b.py            # phase 2b
python3 tools/sim/fase2scen.py         # phase 2, amendment 2 (TRAV_MODE=scen generator)
python3 tools/sim/esplora_artefatto.py # exploratory, labelled as such
```

- `tools/che_posthoc.py` was re-run on 2 October 2026 from a clean export: about 3 s, output
  identical to the committed `data/posthoc/che_posthoc.csv`. It uses no lab measurement as a
  parameter: object sizes come from `data/derived/chapter_sizes.csv`, the access
  distribution from `harness/load/workload.js`.
- `tools/che_posthoc.py` and `tools/sim/esplora_artefatto.py` compare their results with lab
  runs. The rows they need (run, repetition, configured α and β, `origin_rps`, hit ratio per
  class; miss = 1 − hit) are in `data/derived/lab_reference.csv`, extracted once from the
  `points.csv` of the author's local copies of the runs, without `env.txt`. `--from-backup`
  reads the same values from those copies (`~/undertow-backup`, not published) instead.
  Checked on 4 October 2026 from a fresh clone with a `HOME` that has no `~/undertow-backup`:
  both scripts run, `data/posthoc/che_posthoc.csv` is identical byte for byte, and the outputs
  of `tools/sim/esplora_artefatto.py` are identical apart from the commit hash on line 1.
- `tools/sim/test_policies.py` passes (under 1 s).
- The phase scripts (`tools/sim/fase2.py`, `tools/sim/fase2b.py`, `tools/sim/fase2scen.py`,
  `tools/sim/esplora_artefatto.py`) are seeded and write to `data/sim/`. `tools/sim/fase2.py` needs its four steps in the order shown above:
  each starts only if the previous one wrote a PASSA outcome, and without a step it exits with
  an error. Re-run on 3 October 2026 from a fresh clone, every step passes and every value is
  identical to the committed one; times: `tools/sim/fase2b.py` 5 s, `tools/sim/esplora_artefatto.py` 16 s,
  `tools/sim/fase2scen.py` about 1 minute, `tools/sim/fase2.py` 3 + 3 + 0 + 58 s.
- **They rewrite one line of the committed CSVs.** Each output starts with
  `# commit <hash>; ...`, the commit of the clone it ran in. After a re-run, `git status` shows
  13 modified files in `data/sim/` whose only change is that hash. Discard them with
  `git checkout -- data/sim`. The scripts must run inside a git clone and refuse to run with
  uncommitted changes in `tools/sim/`.
- **Not reproducible outside the lab:** `tools/sim/fase1.py` compares the simulator with
  the lab's raw runs over `ssh lab`, and `tools/sim/object_sizes.py` measured
  `data/derived/chapter_sizes.csv` on the lab. Their outputs (`data/sim/fase1/`,
  `data/derived/chapter_sizes.csv`) are committed and are the inputs of everything above.

Pre-registrations and their results are in `docs/PREREG-*.md` and `docs/RISULTATO-*.md`
(in Italian; the commit hashes they cite are the evidence of their timing).

## Level 3: `data/derived/` from raw data, *not available*

`make data` regenerates `data/derived/` from the raw runs. It only works on the author's
machines:

- `make data-lab` reads each run's `harness/results/<run>/points.csv` and k6 summaries from the lab server over
  `ssh lab`, read only. The raw runs (`harness/results/`) are **not published**: every run
  directory contains `env.txt` (`harness/results/<run>/env.txt`), the full environment of the shell that launched it, which in
  an SSH session includes the address the operator connected from.
- `make data-vm` reads CPU and cache-occupancy series from VictoriaMetrics on the lab,
  through an SSH tunnel.
- `make data-honeypot` reads the honeypot log snapshot. The logs contain client IP
  addresses and are **never published**. Only the aggregates leave the server; the
  snapshot is identified by the SHA-256 of each file in
  `data/derived/honeypot_snapshot.sha256`.

What a third party *can* check without the raw data:

- which runs feed which file: `data/derived/MANIFEST.csv`;
- the role and configuration of every run, including invalid and superseded ones:
  `docs/registry.csv`;
- the scripts that turn raw runs into `data/derived/` (`tools/*_data.py`,
  `tools/class_miss_by_scope.py`, `tools/cache_capacity.py`, `tools/cpu_validation.py`,
  `tools/honeypot_aggregate.py`): their logic is public even where their input is not.

## Level 4: a new campaign on your own hardware

The harness is complete: Flask application, Varnish, nginx router, PostgreSQL, k6
generator, observability. [`docs/setup.md`](docs/setup.md) is the full procedure,
including CPU pinning and the validation steps that decide whether a measurement is valid.

```bash
cd harness
cp env.arm6 .env                 # or env.x86-16: CPU pinning for your host
cat .env.example >> .env         # then set POSTGRES_PASSWORD and GRAFANA_ADMIN_PASSWORD
docker compose up -d
docker compose --profile tools run --rm loader     # needs the corpus in ../cache/
bash load/null-test.sh           # is the generator the bottleneck?
bash load/calibrate.sh           # is the workload I/O-bound?
bash load/treclassi.sh           # the three-class runner behind every run in the registry
```

Image versions are pinned in `harness/docker-compose.yml` (k6 0.52.0, Varnish 7.5,
PostgreSQL 16, nginx 1.27). Requires at least 6 physical cores, 16 GB RAM, 50 GB disk;
x86-64 and aarch64 both work.

**What will differ, by design.** Capacity, hit ratios and the composition at which the
knee occurs are properties of the host. The paper claims the *sign change* and the
dependence on the reachable set relative to cache capacity, not the absolute values;
recalibrate (setup.md, "Deriving the operating point") before comparing.

**The corpus is the hard part.** The experiment used 495 Project Gutenberg books
(16,954 chapters, 203,437 links once loaded). Book texts are not redistributed:
`data/corpus/books.csv` lists the Gutenberg IDs and the chapter count of each book, and
`data/derived/chapter_sizes.csv` the size of every chapter page, so you can verify that
your corpus is the same one. There is currently **no script that downloads a given list
of IDs**: `honeypot/content/generate.py` downloads the *currently most popular* books from
Gutendex, which will not be the same set today. To rebuild the exact corpus, fetch the IDs
in `data/corpus/books.csv` into `cache/` in the format `honeypot/content/generate.py` writes (`catalog.json` plus one
text file per book), then load it; a different corpus means nothing downstream is
comparable. Gutenberg rate-limits and blocks some residential ISP ranges.

Scripts from earlier phases of the project are kept in `harness/legacy/` for the record;
no run in the registry depends on them.

## The honeypot

`honeypot/` contains the site generator, the nginx configuration and the `robots.txt` (`honeypot/static/robots.txt`) of
the public measurement site. The paper's honeypot data cover the fixed window
[2026-08-12, 2026-09-22) UTC. The site is named in this repository, so traffic after the
repository was published is not comparable with that window. A new honeypot needs a new
domain, not this one.
