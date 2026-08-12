# Undertow

Measuring where web infrastructure breaks when agentic traffic dominates.

> Status: **early / private.** Nothing here has been peer-reviewed or published.
> Numbers in this repository are provisional until the methodology section is
> complete and the null tests pass.

---

## The question

Bot traffic passed human traffic on the web for the first time in 2026.
Most of the public discussion has been about *volume* — how many requests,
how much bandwidth. That framing misses the more interesting failure.

Essentially every layer of web infrastructure was calibrated on human
behavioural assumptions: think time between requests, browser-side caching,
session persistence, diurnal cycles, geographic locality, connection reuse,
preferential access to popular content. Agentic clients violate all of them
simultaneously.

The hypothesis this project tests:

> The degradation is **non-linear**. A modest fraction of agentic traffic
> disproportionately degrades origin infrastructure, because cache pollution
> from long-tail access shifts load onto the origin, which then saturates
> bounded resources (thread pools, connection pools) that were sized against
> a human-derived load model.

Prior work (Zhang et al., SoCC 2025) measured the first link of that chain at
the CDN layer: 25% AI traffic nearly doubles cache miss ratio, 17.3% -> 32.2%.
Nobody has followed the chain down to the origin application server.

## What is being measured

The causal chain, link by link, with numbers on each:

```
agentic share ↑
  → cache hit ratio ↓
    → origin request rate ↑
      → thread / connection pool saturation
        → p99 latency ↑↑
          → timeouts
```

The output is a **knee curve**: the threshold at which the system moves from
degraded to collapsed, expressed in normalised terms (fraction of pool
capacity) rather than absolute request rates, so it generalises beyond the
specific hardware used.

## Why the framing matters

Every layer *below* the application solved traffic-class isolation decades
ago — DiffServ and weighted fair queueing in IP networks, T-CONT scheduling
in PON, network slicing in 5G SA, Resource Manager consumer groups in Oracle
DB, work managers in application servers. The web application layer never
did, because with only human clients it never needed to.

That is the argument this project is building toward: not "buy more servers",
but *admission control and per-class resource budgets for agentic traffic*.

## Method

Controlled experiment, not passive observation. Two traffic profiles (human
and agentic) are generated at a controlled ratio against an instrumented
stack; the ratio is swept and the response measured.

Non-negotiables:

- **Open-loop load generation.** Closed-loop generators stop issuing requests
  when the system stalls, under-sampling exactly the latency tail that
  matters (coordinated omission — Tene). k6 `constant-arrival-rate` only.
- **Full latency histograms.** Percentiles are computed in analysis from raw
  samples, never by the metrics store. Bucketed percentiles are not
  aggregatable across runs.
- **One independent variable per sweep.**
- **Null test before every campaign.** The load generator must sustain 10x the
  test rate against a trivial endpoint without saturating, proving it is not
  itself the bottleneck.
- **Provenance on every run.** Commit hash, full config, RNG seed, timestamps.

## Repository layout

```
honeypot/          Public measurement site (theslowshelf.org)
  content/         Static site generator, Project Gutenberg corpus
  nginx/           Server config, log format
  static/          robots.txt, about page
harness/           System under test + load generation  [not started]
analysis/          Parquet pipeline, figures             [not started]
paper/             Manuscript and artefact               [not started]
```

## Honeypot

A public site serving public domain literature, used to characterise the
behaviour of real crawlers at request granularity — depth, concurrency,
connection reuse, burstiness, return interval. These parameters calibrate the
synthetic agentic profile.

This matters methodologically: without it, the workload model rests on
assumption. With it, the model is calibrated against measured behaviour.

The site permits all AI crawlers explicitly in `robots.txt` — the inverse of
current practice, and deliberate. It discloses its purpose at `/about`.
Logs are retained in aggregate form only.

## Reproducibility

`site/` and `cache/` are generated, not versioned. Regenerate with:

```bash
python honeypot/content/generate.py --books 50
```

The RNG seed is fixed, so the internal link graph is deterministic.

Note: gutenberg.org blocks some residential ISP ranges. If downloads time
out, run from a datacenter host.

## References

- Zhang, Cai, Wildani, Klimovic. *Rethinking Web Cache Design for the AI Era.*
  SoCC 2025. doi:10.1145/3772052.3772255
- Liu et al. *Somesite I Used To Crawl.* IMC 2025. arXiv:2411.15091
- Tene. *How NOT to Measure Latency.*
- Wikimedia Foundation. *How crawlers impact the operations of the Wikimedia
  projects.* Diff, April 2025.

## Licence

Code: MIT. Data and figures: CC BY 4.0. Corpus: public domain
(Project Gutenberg).