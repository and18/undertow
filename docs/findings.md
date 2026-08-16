# Findings

Experimental results as they are obtained. Separate from `decisions.md`,
which records *why* things were done; this records *what was found*,
including predictions that failed.

Every result states the configuration it was obtained under. Absolute
numbers are properties of this testbed and are not claimed to transfer;
what is claimed to transfer is the mechanism and the relation.

---

## F1. The knee exists, and it is sharp

**Configuration.** Commit 6f2c2e7. 16-core host (WSL2, Ryzen AI 7 350),
CPU-pinned containers: k6 on 0–3, Varnish 4–7, app 8–9, PostgreSQL 10–11,
observability 14–15. `THREADS=8`, `BACKLOG=128`, `DB_POOL_MAX=12`,
`VARNISH_SIZE=128m` (71% of the 245 MB working set). Corpus: 495 books,
16,954 chapters, 203,437-edge link graph, fixed seed. Total arrival rate
held constant at 260 req/s throughout. Cacheable endpoint only.
Cold cache before every measurement; 180 s warm-up discarded; 180 s
measured. 70 measurements, randomised execution order (seed 42),
5 repetitions per point and 10 at α ∈ {0.30, 0.35, 0.40}.

**Result.**

| α | n | p99 median (ms) | p95 (ms) | hit ratio | pool occupancy | lost |
|---|---|---|---|---|---|---|
| 0.00 | 5 | 118.5 | 47.0 | 0.829 | 19% | 0.00% |
| 0.05 | 5 | 177.2 | 96.6 | 0.794 | 37% | 0.00% |
| 0.10 | 5 | 282.3 | 168.8 | 0.760 | 59% | 0.00% |
| **0.15** | 5 | **1476.1** | 1057.3 | 0.734 | 96% | 0.10% |
| 0.20 | 5 | 2951.3 | 2824.4 | 0.715 | 98% | 0.34% |
| 0.25 | 5 | 3058.9 | 2920.1 | 0.692 | 100% | 0.36% |
| 0.30 | 10 | 3052.4 | 2908.0 | 0.676 | 99% | 0.37% |
| 0.35 | 10 | 3051.8 | 2922.5 | 0.644 | 99% | 0.38% |
| 0.40 | 10 | 3039.6 | 2894.8 | 0.625 | 97% | 0.40% |
| 0.45 | 5 | 3023.4 | 2909.2 | 0.608 | 97% | 0.42% |
| 0.50 | 5 | 3043.8 | 2920.6 | 0.589 | 99% | 0.44% |

The pre-registered criterion (`p99 > 10 × p99(0)`, i.e. > 1185 ms) is
first met at **α = 0.15**. The transition from α = 0.10 to α = 0.15 is a
**5.2× increase in p99 for a five-percentage-point change in traffic
composition**, at constant total arrival rate.

**Why this is not simply "more load breaks things".** Total offered load
is identical at every point: 260 req/s. Only the *composition* changes.
The mechanism is that agentic requests miss the cache far more often, so
the load reaching the origin rises even though the load entering the
system does not.

**p95 tracks p99.** At α ≥ 0.20 the p95 is within 5% of the p99: past the
knee it is not a tail phenomenon, essentially every request is slow.

---

## F2. The prediction failed by a factor of 2.3 — and the reason is the
result

**Prediction.** From parameters measured in isolation
(h_H = 0.830, h_A = 0.493, C = 74 req/s), the mixture model

    λ_origin(α) = λ · [(1 − h_H) + α(h_H − h_A)]

predicted the knee at **α = 0.35**.

**Observed: α = 0.15.**

**Diagnosis.** The measured hit ratio falls faster than the linear
mixture predicts, and the gap widens with α:

| α | predicted hit | observed hit | deviation |
|---|---|---|---|
| 0.10 | 0.796 | 0.760 | −0.036 |
| 0.25 | 0.746 | 0.692 | −0.054 |
| 0.50 | 0.662 | 0.589 | −0.073 |

The cause is identifiable and specific:

> **A cache hit ratio measured in isolation is not the hit ratio that
> class achieves in a mixture.**

When h_A was measured with 100% agentic traffic, agentic requests had the
entire cache to themselves and reached 0.493 through revisits. In a
mixture, they compete with human traffic, which occupies the cache with
popular content. The agentic class is evicted before it can benefit from
its own locality.

Recovering the effective in-mixture value from the observed slope near
α = 0 gives **h_A,eff ≈ 0.13**, not 0.493. Hence:

    r_eff = (1 − 0.13) / (1 − 0.829) = 5.1
    α* = (1/u₀ − 1) / (r_eff − 1) = (1/0.61 − 1) / 4.1 = 0.156

against an observed 0.15.

**The model's structure is correct; its parameterisation was not.** This
is a stronger outcome than a successful prediction would have been: a
prediction that failed, a cause that was identified, and a corrected
model that reproduces the observation.

**Methodological consequence, stated for others.** Any mixture model of
traffic classes parameterised with hit ratios measured per-class in
isolation will *overestimate* the tolerable fraction of the aggressive
class — here by 2.3×. Per-class hit ratios must be measured in the
mixture, or an interference term must be modelled explicitly. This does
not appear to be stated in the caching literature.

---

## F3. The transition is bimodal before it is broken

The dispersion across repetitions is not uniform:

| α | individual p99 values (ms) | spread |
|---|---|---|
| 0.00 | 112, 118, 118, 121, 123 | 1.10× |
| 0.10 | 255, 272, 282, 286, 288 | 1.13× |
| **0.15** | **486, 656, 1476, 1535, 1654** | **3.40×** |
| 0.20 | 2912, 2946, 2951, 2989, 3005 | 1.03× |

Below the knee the system is predictable. Above it, it is predictably
broken. **Exactly at the transition, identical configurations produce
outcomes differing by more than 3×.**

This is the signature of a system operating at the edge of a queueing
instability: whether the queue drains or grows depends on the realisation
of the arrival process, not only on its rate. Two of the five runs at
α = 0.15 stayed under the pre-registered threshold; three did not.

**Operational implication, and the most important practical finding so
far.** The danger is not that the system becomes slow. It is that it
stops being *predictable* before it becomes slow. An operator watching
medians — or even p95 averaged over hours — sees nothing until the
collapse. The variance moves first.

Working name for this region: **the unstable band**. It is not the knee,
which is a threshold; it is the interval in which the outcome becomes a
coin flip.

**Caveat.** Five repetitions is enough to observe the phenomenon, not to
characterise it. The band needs a dedicated experiment: fine α steps
(0.12–0.18 at 0.01), 20+ repetitions, and the full latency distribution
per run rather than summary percentiles. Whether the distribution is
genuinely bimodal or merely heavy-tailed cannot be settled from these
data.

---

## F4. The plateau is set by the socket backlog

For every α ≥ 0.20 the p99 settles at ~3000 ms and does not rise further,
despite origin load continuing to increase.

With `BACKLOG=128` and the origin saturated at ~74 req/s, the queue
drains in 128/74 ≈ 1.7 s; adding service time gives an upper bound
consistent with the observed plateau. **The ceiling on latency is not a
property of the collapse — it is a property of the admission queue.**

Requests are not lost in large numbers (0.4%): the system does not shed
load, it queues it. The backlog is what bounds how bad the queueing gets.

**Prediction to test.** Varying `BACKLOG` (64, 128, 256) should move the
plateau roughly proportionally while leaving the *position* of the knee
unchanged. If confirmed, this separates two distinct quantities:

- **where** the system breaks — set by cache behaviour and origin
  capacity;
- **how badly** it breaks — set by admission policy.

This is the empirical link between the measurement and the mitigation
argument: admission control does not prevent the transition, it bounds
its consequences. Untested as of this writing.

---

## F5. Honeypot: connection reuse differs by an order of magnitude
between operators

**Status: preliminary.** Four days of collection, 25,933 requests.
Reported here because the contrast is large and was not anticipated; not
yet suitable for quantitative claims.

Same site, same content, same hours:

| | Googlebot | Meta (`meta-externalagent/1.1`) |
|---|---|---|
| source addresses | 3 | ~30, single /24 |
| max requests per TCP connection | **339** | **1** |
| requests / distinct URLs | 1.09 | 1.00 |
| share of site traffic | ~25% | ~70% |

Meta opens a fresh TCP connection for every request. Google reuses one
for hundreds. Both deduplicate near-perfectly; a third crawler, hosted at
OVH and presenting a 2015-era Chrome 42 user agent, fetched every page
twice (ratio 2.0) and accounted for 72% of traffic on day one.

**Relevance to the experiment.** Connection reuse is one of the nine
workload parameters, and this is the first of them measured rather than
assumed. The testbed currently runs without TLS, which makes new
connections far cheaper than in reality — so the cost attributed to
Meta's behaviour here would be *understated*. Quantifying it requires a
TLS sub-experiment.

**Also observed.** Probes for `/v1/models`, `/mcp`, `/api/mcp`, `/sse` —
automated traffic searching for exposed AI infrastructure on a site that
hosts none. This category is already documented by others (SANS ISC
diary 33150; Knostic's survey of 1,862 exposed MCP servers, July 2025) and
is reported here as independent confirmation, not as a new finding.

`Claude-User/1.0` — a retrieval fetcher rather than a training crawler —
appeared within 48 hours, with 3 requests.

**Collection continues.** No quantitative claim will be published on
fewer than eight weeks of data. Comparable studies run longer: Kim et al.
(IMC 2025) collected for 40 days across 36 sites; Fastly's Q2 2025 report
spans roughly three months.

---

## Open questions

Ordered by how much they would change the work.

**Q1 — Is cache pollution the mechanism, or a correlate?** The mediator
intervention answers this: size the cache at or above the working set,
removing eviction competition. If the mechanism is cache pollution, the
knee must vanish even at α = 1. If it does not, the causal claim fails
and the mechanism is elsewhere. *This is the single most important
outstanding experiment.*

**Q2 — Which behavioural factor produces r?** The agentic profile changes
locality, connection reuse, session state and arrival burstiness
simultaneously. Single-factor ablations are required before any claim
about *why* agentic traffic is expensive.

**Q3 — Does the shape survive a different bottleneck?** Here the binding
resource is PostgreSQL CPU. Reducing DB cores, constraining the
connection pool below the thread pool, or introducing a downstream
service would each move the bottleneck. If the normalised curve keeps its
shape, generalisation is demonstrated; if not, the dependency has been
found — also a result.

**Q4 — Is the knee invariant under normalisation?** Thread pool sizes
4, 8, 12 with arrival rates scaled to hold λW/N constant should collapse
onto one curve. Absolute numbers do not transfer; this would show the
relation does.

**Q5 — Is the GIL contributing?** App CPU at the knee is ~31%, against an
observed GIL ceiling near 80%, which suggests not. The direct control is
`--workers 2 --threads 4` against `--workers 1 --threads 8`: same thread
count, double interpreter capacity. If the knee does not move, the GIL is
excluded.

**Q6 — How does the unstable band behave under realistic dynamics?** All
measurements use stationary arrival rates. Real agentic traffic is
bursty and lacks a diurnal cycle. A system whose *mean* utilisation sits
below the knee may still spend part of each day inside the unstable band.

---

## Corrections and retractions

Kept as a running list. Nothing here is deleted.

- **2026-08-12.** All measurements taken with `VARNISH_SIZE=2m` discarded:
  Varnish was in a crash-restart cycle (`signal=6`, `PANIC REENTRANCY`),
  misdiagnosed initially as CPU saturation because consumption was flat
  at 92% regardless of load. See `decisions.md` §5.
- **2026-08-14.** Hit-ratio measurements taken without a discarded warm-up
  phase are invalid: they include compulsory misses from cache filling
  and are indistinguishable from a capacity limit. Affected the first
  cache-size sweep, which appeared to plateau at h = 0.815 for all cache
  sizes ≥ 192 MB. See `decisions.md` §9.
- **2026-08-15.** The predicted knee of α = 0.35 published in
  `decisions.md` §15 is superseded. It was derived from h_A measured in
  isolation; the in-mixture value is roughly a quarter of it. The
  pre-registration itself stands — the prediction was recorded before the
  data and is retained as made.