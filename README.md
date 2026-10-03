# Undertow

## Start here

Three ways in, depending on what you want.

1. **Understand the result** → read the paper ([`paper/`](paper/), LaTeX source) and look
   at its figures ([`figures/paper/`](figures/paper/), `FIG-01` first).
2. **Check a number** → [`docs/claims.md`](docs/claims.md) (the claim and its status) →
   [`docs/registry.csv`](docs/registry.csv) (the runs behind it) → the script in
   [`tools/`](tools/) → the file in [`data/derived/`](data/derived/)
   ([`data/derived/MANIFEST.csv`](data/derived/MANIFEST.csv) says which runs and which script made each file).
3. **Redo the experiment** → [`REPRODUCE.md`](REPRODUCE.md), which says what works at each of
   four levels and what does not.

## Why "Undertow"

An undertow is the current beneath the waves, often pulling in a different direction from
the surface. Traffic labels are the surface; the cost that reaches the origin is the undertow.

---

**Does a class of web traffic have a stable cost?** Undertow is an independent
measurement study of how automated and AI-agent traffic loads shared web infrastructure.
It asks a narrow question with a practical consequence: when a site, a CDN or an admission
policy assigns a cost to a *class* of traffic (human, crawler, agent) and decides on that
basis, is that cost a property of the class, or of the state the class meets?

On our testbed the answer is the second, for one class out of three.

**Paper:** *Same Label, Opposite Sign: State-Dependent Marginal Origin Cost in Shared Web
Caches*, Andrea Licitra (arXiv link to be added on posting). Source in [`paper/`](paper/).

> **Status, October 2026: experiments closed, evidence frozen, paper written, arXiv version
> in preparation. Nothing here is peer-reviewed yet.** Numbers in this README are the frozen ones
> in [`docs/claims.md`](docs/claims.md), the single source of truth. Retracted results are
> kept, not deleted: see [`docs/retractions.md`](docs/retractions.md).

---

## The finding in one figure

![Marginal origin cost of the agentic class at three reachable-set sizes](figures/paper/FIG-01_marginal-cost-vs-working-set.png)

*Figure 1 of the paper.* Holding the traffic class, the volumes, the cache and the corpus
fixed, and changing only the **reachable set** of the agentic class (the distinct chapters
its sessions can request), the origin cost of one additional agentic request goes from
**−0.035** (reachable set at 0.19× the cache capacity) to **+0.143** (0.58×) to **+0.421**
(1.90×) origin requests per request, with standard errors between 0.004 and 0.006. The
same label, "agentic", covers a class that relieves the origin at the margin and a class
that costs it 0.42 origin requests per request.

What this does **not** say: that agentic traffic reduces origin work (adding the class
costs +1.10 ± 0.08 origin req/s from 0 to 36 req/s at the narrowest scope), that agentic
traffic on the Web is benign, or that classification is useless. At the knee, blocking the
exhaustive class by identity sits on the sampled work/latency frontier; we did not test
policies without identity. The claim is narrower: **identity alone can be insufficient for
class-sensitive decisions**, because the marginal cost of a class depends on the state it
meets, here the width of its reachable set relative to the cache.

## Results at a glance

| | result | status |
|---|---|---|
| A1 | the marginal cost of the agentic class changes sign with its reachable set: −0.035 → +0.143 → +0.421 | measured |
| A2 | raising the agentic share from 13% to 30% moves the agentic miss ratio 4.08×, the exhaustive and human ones 1.01× and 1.00× (narrowest scope) | measured |
| A7 | varying its *own* volume, the exhaustive class keeps a flat marginal cost of about 0.98 | measured (secondary series) |
| A9 | adding the agentic class costs: +1.10 ± 0.08 origin req/s from 0 to 36 req/s (narrowest scope) | measured |
| A3 | overlap between the agentic working set and the human popular head makes the agentic class look cheaper: +0.926 and +0.800 origin req/s when removed (t = 9.63, 10.14) | measured |
| A4 | at the knee, also blocking the agentic class costs 2,807 ± 185 served requests with no measurable latency benefit (Δp99 +0.03 ± 0.73 ms) | measured, with a stated limit on the frontier runs |
| A6 | blocking and deferring lie on a single convex work/latency frontier | measured, same limit |
| B5 | a wider agentic reachable set raises human p99 from 72.9 to 99.6 ms while the human miss ratio moves 1.07×: the cost arrives as origin load, not as lost cache hits | supported |
| C1 | origin requests are a validated proxy for backend CPU **on this testbed** (R² = 0.997) | measured |
| B3 | the characteristic-time approximation predicts the elasticity quantitatively | **rejected** by our own prior prediction |
| B7 | post hoc, the same approximation with the generator's access distribution reproduces the sign change of A1, and with periodic exhaustive traffic the values within 0.008 | interpretive (post hoc, not pre-registered) |

Every sentence of the paper maps to one row of [`docs/claims.md`](docs/claims.md), with its
status (measured, supported, interpretive, rejected, retracted) and what would falsify it.

## Two sources, two roles

| source | establishes | scale |
|---|---|---|
| **controlled testbed** | what each class costs, and on what that cost depends | one origin |
| **honeypot** (`theslowshelf.org`) | that the synthetic agent is realistic on the dimension that matters, and where it is not | one site |

The testbed is a CPU-pinned stack on a 6-core ARM server (Ampere Neoverse-N1):
k6 → Varnish (128 MB, 5,263 ± 8 objects measured at full cache) → gunicorn/Flask → PostgreSQL,
serving 495 public-domain books split into 16,954 chapters. Three traffic classes:
*human* (Zipf over the whole corpus), *exhaustive* (uniform traversal), *agentic* (sessions
of three contiguous chapters drawn from a configurable scope). Working sets of different
classes can be decorrelated (`AGENT_MUL`).

The honeypot is a public site of 18,720 pages of public-domain literature whose
`robots.txt` (`honeypot/static/robots.txt`) explicitly permits every AI crawler — the inverse of current practice, and
deliberate: a site that blocks crawlers cannot observe them. It logged 520,871 requests
in the fixed window [2026-08-12, 2026-09-22) UTC. Only aggregates are published.

**The paper's honeypot data cover only that window, [12 August, 22 September 2026) UTC.**
The domain is named in this repository, so traffic after the repository was published is
not comparable with it: anyone reading this can now find, and visit, the site.

## Method, non-negotiable

- **Open-loop load generation.** Closed-loop generators stop issuing requests when the
  system stalls, under-sampling exactly the latency tail that matters (coordinated
  omission). k6 `constant-arrival-rate` only, with the virtual-user pool sized for the
  saturated regime rather than the nominal one.
- **One manipulated variable at a time.** Either the total rate is held constant and the
  composition changes, or the other classes are held fixed in absolute terms and one class
  changes. Never both, so that a collapse cannot be explained by "more load".
- **Validity gate on every run.** A measurement with dropped iterations or an error rate
  above 1% is repeated, not averaged in. Its raw output is kept.
- **Intervention, not correlation.** Where one variable drives every link of a chain, all
  correlations along it approach unity by construction. Mechanism is established by
  manipulating the hypothesised mediator.
- **A prior prediction where a model makes one.** The prediction is written before the
  results it predicts are available and never edited afterwards; a failed prediction is
  published as failed. Ours has no independent timestamp, and we say so.
- **Nothing random unseeded.** A generator parameter drawn at random is an uncontrolled
  variable.
- **Provenance on every run.** Since 21 September 2026 every run writes its full
  configuration (`harness/results/<run>/env.txt`); every run, before and after, is classified in
  [`docs/registry.csv`](docs/registry.csv).

## Repository layout

One line per folder.

```
paper/                       LaTeX source of the paper
analysis/                    figure design system, one script per figure, build and QA
figures/paper/               the paper's figures (4.80 in) with captions and provenance
data/derived/                one small CSV per figure, the only input of the figures; MANIFEST.csv
data/corpus/                 books.csv: the Gutenberg IDs of the 495 books (texts not included)
data/sim/  data/posthoc/     outputs of the cache simulator and of the post-hoc model
tools/                       raw runs and honeypot logs to data/derived/, analyses, replica launchers
tools/sim/                   the cache simulator (standard library only)
docs/                        claims, run registry, retractions, pre-registrations and their
                             results, verifications, design decisions, setup
                             (working documents are in Italian; the paper is in English)
docs/archive/                superseded narrative documents, kept for the record
harness/app/                 Flask application under test
harness/load/                k6 workload, the three-class runner treclassi.sh and its wrappers
harness/legacy/              runners from earlier phases; no registered run depends on them
harness/nginx/               per-class router (template)
harness/varnish/             cache tier: default.vcl is what docker-compose mounts;
                             default.vcl.tpl is the same file with host and port as variables,
                             the one cited by the simulator pre-registration and by tools/sim/cache.py
harness/observability/       VictoriaMetrics + Grafana (operations only, never in the paper)
harness/profiles/            testbed profiles (search terms)
harness/env.*  .env.example  per-host configuration and the credentials template
honeypot/                    static site generator, server configuration, robots.txt
Makefile                     make figures, make data (lab only), make paper
REPRODUCE.md                 what a third party can reproduce, level by level
```

**Which wrapper made which runs.** Every registered run (`tre-*` in
[`docs/registry.csv`](docs/registry.csv)) went through `harness/load/treclassi.sh`. The
registry names campaigns, not scripts, so the link below was reconstructed from the date, the
number of runs and the parameters (α, β, repetitions, λ) written in each script. *Exact* means
the count and the parameters agree run by run; *probable* means they agree but the registry
labels the campaign differently or does not record the variable that distinguishes the runs.
The lab's `harness/results/<run>/env.txt` files would settle the probable ones.

| script | what it launches | registry runs | match |
|---|---|---|---|
| `harness/load/costmap.sh` | six isolated-class runs (traversal @22 and @44, agent @5 and @22, zipf @44 and @88) | `tre-20260911-135930` … `-164534` ("isolata") | exact |
| | grid α 0.20–0.40 × β 0.05 and 0.20, λ 110 | `tre-20260911-171746` ("griglia alpha x beta") | exact |
| | the same series at α 0.25, β 0.02–0.30 with `OBJECT_TTL=60` | `tre-20260911-203812` ("sweep beta a cache piccola") | probable |
| `harness/load/verifiche.sh` | A: five `OBJECT_TTL` values at α 0.25, β 0.02 and 0.20 | `tre-20260910-212316` … `tre-20260911-013843` ("sweep capienza A–E") | probable |
| | B: β series 0.02–0.30 at constant λ 110 | `tre-20260911-024234` ("sweep beta a volume costante") | probable |
| | C: DB pool 4 and 12, λ 160, β 0.05 | `tre-20260911-055256` (invalid), `-072826` ("sweep alpha a carico alto") | probable |
| `harness/load/verifiche2.sh` | D: durations 620, 1860, 3720 s at β 0.02, plus the control at β 0.30 | `tre-20260914-065458`, `-072714`, `-084049`, `-105624` ("invarianza alla durata") | exact |
| | M: cache 64, 128, 256, 512 MB, α 0.00 and 0.30 at β 0.05 | `tre-20260914-121000` … `-152139` ("variante di capienza") | exact |
| `harness/load/marginale.sh` | shared-mapping marginal series, 0/6/12/24/36 agents | `tre-20260914-194419` … `-215321` | exact |
| `harness/load/marginale2.sh` | B: crawler series, four points, 3 repetitions | `tre-20260916-013722`, `-025527`, `-041332`, `-053137` ("serie crawler"; the registry itself says "blocco B di marginale2") | exact |
| | A: agent series, 0/12/24/36 agents, 5 repetitions | `tre-20260915-213648`, `-225700`, `tre-20260916-001711`, `-073843`, `-085853` ("serie marginale a 5 ripetizioni" and "ripetizione") | probable |
| `harness/load/policy.sh` | no policy, block B, block C, deferral with budget 4 and 6 | `tre-20260919-072040` … `-103501` ("frontiera") | exact |
| `harness/load/frontiera.sh` | deferral with budget 3, 2, 1 | `tre-20260920-061512`, `-070346`, `-075220` | exact |
| `harness/load/scopesweep.sh` | agentic scope 0.06 and 0.20, two operating points each | `tre-20260921-214946` … `tre-20260922-015010` ("SWEEP SCOPE") | exact |

The other registered groups were launched through `harness/load/treclassi.sh` directly: the "sweep TTL /
budget" runs of 13–14 September (R9, no wrapper kept), the separate-mapping runs of 21
September, and the replicas and reruns of 25–29 September, whose launchers are
`tools/replica-20260924.sh`, `tools/replica-own-20260928.sh` and
`tools/replica-own-scope-20260929.sh`. `harness/load/capacity.sh`, `harness/load/calibrate.sh`, `harness/load/null-test.sh` and
`harness/load/measure-model.sh` are validity and calibration steps, not registered runs.

Produced material that can be regenerated is not versioned: `cache/`, `site/`,
`harness/results/`, `harness/.env`, `figures/narrow/`, `figures/editorial/`, `figures/_qa/`.
Honeypot logs are never versioned.

## Rebuilding the figures

```bash
python3 -m venv .venv && .venv/bin/pip install -r analysis/requirements-figures.txt
make figures                          # on Windows without make: python analysis/build_figures.py
```

The virtual environment is needed on current Debian and Ubuntu, where `pip` refuses to install
into the system Python; `make` uses `.venv/bin/python` when it exists.

This deletes `figures/` and regenerates it from `data/derived/` only: every figure at three
widths (only the paper width is versioned), each with its caption (`*.caption.txt`) and provenance (`*.provenance.txt`: claims,
data hashes, source runs, toolchain). The build refuses to write a figure with a missing
glyph, text outside the margins or overlapping labels, and checks that every PDF is vector,
embeds only the bundled font and has the exact target width. Contact sheets, including
grayscale proofs, go to `figures/_qa/`. The font, Source Sans 3, is bundled in
`analysis/fonts/` so that every machine renders the same figures.

## Reproducing the experiments

[`REPRODUCE.md`](REPRODUCE.md) says what can be reproduced from this repository and what
cannot (the raw runs and the honeypot logs are not published).
[`docs/setup.md`](docs/setup.md) is the full procedure for the testbed. The short version:

```bash
git clone https://github.com/and18/undertow.git && cd undertow
# the corpus: the 495 books listed in data/corpus/books.csv, in ./cache/ (see REPRODUCE.md)
cd harness && cp env.arm6 .env                          # or env.x86-16
cat .env.example >> .env                                # then set the two passwords
docker compose up -d && docker compose --profile tools run --rm loader
bash load/null-test.sh        # is the generator the bottleneck?
bash load/calibrate.sh        # is the workload I/O-bound?
```

**Absolute numbers do not transfer between machines.** Capacity, hit ratios and the
composition at which the knee occurs are properties of the host; recalibrate before
comparing. Requires 6 physical cores, 16 GB RAM and 50 GB of disk; x86-64 and aarch64 both
work. Project Gutenberg rate-limits and blocks some ISP ranges: if you have access to an
existing host, copy `cache/` from it rather than downloading again.

## Evidence and honesty

- [`docs/claims.md`](docs/claims.md) — every claim, its status and its evidence.
- [`docs/registry.csv`](docs/registry.csv) — every run, with its configuration, its role
  (primary, secondary, validation, robustness, retracted, invalid) and the claim or figure
  it feeds.
- [`docs/retractions.md`](docs/retractions.md) — seven corrections. Six are
  interpretations we had adopted internally and later withdrew, with what falsified each
  one: for those, the measurements never changed, the readings did. The seventh (R7) is a
  design defect in the load generator's exhaustive traversal that moved some measured
  values; it was found by the cache simulator, verified on the lab with a pre-registered
  rerun, and the claims it affected were updated in `docs/claims.md`. All seven were
  found by us before publication.
- [`docs/PREREGISTRAZIONE-scopesweep.md`](docs/PREREGISTRAZIONE-scopesweep.md) — the
  prior prediction for the working-set sweep, written before the first results at scopes
  0.06 and 0.20 were available and not independently timestamped. The text is unmodified;
  a dated note on top records the timing. It failed its quantitative criterion, and the
  paper reports that.

## Limitations

One testbed, one corpus, one cache technology, one synthetic generator. The synthetic agent
matches the agents seen on the honeypot on working-set width within one cache
characteristic time, but not on contiguity: with the same metric on both sides (consecutive
request pairs within one session reading adjacent chapters; a session is a TCP connection
on the honeypot and a k6 virtual user in the generator), 4.25% observed against 66.9% in
the generator. One
honeypot, 31 agent-class clients and one period do not characterise agentic traffic on the
Web. The CPU proxy is validated on this testbed only.

## Data policy

- Honeypot logs contain IP addresses and are **never** published or committed. Scripts
  hash client identifiers; only aggregate statistics leave the server.
- Book texts are not redistributed. The corpus is described by public-domain identifiers
  and schema only.

## References

- Fagin. *Asymptotic miss ratios over independent references.* JCSS 14(2), 1977.
- Che, Tung, Wang. *Hierarchical web caching systems.* IEEE JSAC 20(7), 2002.
- Fricker, Robert, Roberts. *A versatile and accurate approximation for LRU cache
  performance.* ITC 24, 2012. arXiv:1202.3974
- Zhang, Cai, Wildani, Klimovic. *Rethinking Web Cache Design for the AI Era.* SoCC 2025.
  doi:10.1145/3772052.3772255
- Hua, Xiao. *Semantics Delivery Network: Rethinking Web Retrieval Infrastructure for LLM
  Agents.* HotNets 2026. arXiv:2609.22486
- Qureshi, Patt. *Utility-Based Cache Partitioning.* MICRO 2006.
- Cidon et al. *Cliffhanger: Scaling Performance Cliffs in Web Memory Caches.* NSDI 2016.
- Pu et al. *FairRide: Near-Optimal, Fair Cache Sharing.* NSDI 2016.
- Megiddo, Modha. *ARC.* FAST 2003. Jiang, Zhang. *LIRS.* SIGMETRICS 2002.
  Johnson, Shasha. *2Q.* VLDB 1994.
- Liu et al. *Somesite I Used To Crawl.* IMC 2025. arXiv:2411.15091
- Cloudflare. *Why we're rethinking cache for the AI era.* Blog, 2 April 2026.
- Cloudflare. *Your site, your rules: new AI traffic options for all customers.* Blog,
  1 July 2026.
- IETF. `draft-ietf-webbotauth-httpsig-protocol-00` (1 September 2026);
  `draft-ietf-aipref-vocab-08`, `draft-ietf-aipref-attach-05`.
- Tene. *How NOT to Measure Latency.*

## Licence

Code under the MIT licence ([`LICENSE`](LICENSE)). Data and figures (`data/`, `figures/`)
under CC BY 4.0 ([`LICENSE-data`](LICENSE-data)). Corpus public domain (Project Gutenberg),
not redistributed. Bundled font Source Sans 3 under the SIL Open Font License 1.1.

## Citation

See [`CITATION.cff`](CITATION.cff); GitHub shows it as "Cite this repository".

## Author

Andrea Licitra — independent research project.
