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
missing glyphs, text outside the margins and overlapping labels. About 30 seconds.

**Verified on 2 October 2026** (Python 3.12.3, matplotlib 3.10.9, Linux): rebuilding from a
clean export of the repository gives PDF and PNG files byte-identical to the committed ones
(all 54: nine figures at three widths, PDF and PNG; the narrow width is regenerated but
not versioned). PDFs are
written without a creation date, so identical inputs give identical bytes. A different
matplotlib or FreeType version can change PNG pixels without changing the content.

One known difference: `figures/paper/FIG-06_cpu-validation.provenance.txt` records the
SHA-256 of `data/derived/fig06_cpu_validation.csv` as it was on the author's disk, with
CRLF line endings. Git stores and checks out the file with LF, so a fresh clone writes a
different hash on that one line. The data values are identical.

Every figure's provenance file lists the claims it supports (`docs/claims.md`), the data
files with their hashes, and the runs they came from (`docs/registry.csv`).

## Level 2: simulator and post-hoc model

These scripts use only the Python standard library and read only files that are in the
repository.

```bash
python3 tools/che_posthoc.py           # characteristic-time model, claim B7 (post hoc)
python3 tools/sim/test_policies.py     # unit gate of the replacement policies
python3 tools/sim/fase2.py             # simulator phase 2 (pre-registered)
python3 tools/sim/fase2b.py            # phase 2b
python3 tools/sim/fase2scen.py         # phase 2, amendment 2 (TRAV_MODE=scen generator)
python3 tools/sim/esplora_artefatto.py # exploratory, labelled as such
```

- `tools/che_posthoc.py` was re-run on 2 October 2026 from a clean export: about 3 s, output
  identical to the committed `data/posthoc/che_posthoc.csv`. It uses no lab measurement as a
  parameter: object sizes come from `data/derived/chapter_sizes.csv`, the access
  distribution from `harness/load/workload.js`.
- `tools/sim/test_policies.py` passes (under 1 s).
- The phase scripts (`fase2*.py`, `esplora_artefatto.py`) were not re-run for this document.
  They are seeded and write to `data/sim/`, so a re-run should reproduce the committed
  values. They must run inside a git clone: they record the commit in their output and
  refuse to run with uncommitted changes in `tools/sim/`.
- **Not reproducible outside the lab:** `tools/sim/fase1.py` compares the simulator with
  the lab's raw runs over `ssh lab`, and `tools/sim/object_sizes.py` measured
  `chapter_sizes.csv` on the lab. Their outputs (`data/sim/fase1/`,
  `data/derived/chapter_sizes.csv`) are committed and are the inputs of everything above.

Pre-registrations and their results are in `docs/PREREG-*.md` and `docs/RISULTATO-*.md`
(in Italian; the commit hashes they cite are the evidence of their timing).

## Level 3: `data/derived/` from raw data, *not available*

`make data` regenerates `data/derived/` from the raw runs. It only works on the author's
machines:

- `make data-lab` reads each run's `points.csv` and k6 summaries from the lab server over
  `ssh lab`, read only. The raw runs (`harness/results/`) are **not published**: every run
  directory contains `env.txt`, the full environment of the shell that launched it, which in
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
in `books.csv` into `cache/` in the format `generate.py` writes (`catalog.json` plus one
text file per book), then load it; a different corpus means nothing downstream is
comparable. Gutenberg rate-limits and blocks some residential ISP ranges.

Scripts from earlier phases of the project are kept in `harness/legacy/` for the record;
no run in the registry depends on them.

## The honeypot

`honeypot/` contains the site generator, the nginx configuration and the `robots.txt` of
the public measurement site. The paper's honeypot data cover the fixed window
[2026-08-12, 2026-09-22) UTC. The site is named in this repository, so traffic after the
repository was published is not comparable with that window. A new honeypot needs a new
domain, not this one.
