# Findings

Experimental results as they are obtained. Separate from `decisions.md`,
which records *why* things were done; this records *what was found*,
including predictions that failed and diagnoses that turned out wrong.

Every result states the configuration it was obtained under. Absolute
numbers are properties of this testbed and are not claimed to transfer.
What is claimed to transfer is the mechanism and the relation.

**Terminology.** The two synthetic workload classes are named by what
distinguishes them, not by what they are meant to represent:

- **high-locality** — Zipf(1) over a popularity ranking. Stands in for
  human browsing.
- **low-locality** — dispersed traversal of the object space. Stands in
  for crawler and agent access patterns.

α is the **low-locality fraction of traffic**. It is not yet the agentic
fraction: only one of the nine workload parameters is varied. Calling the
low-locality profile "agentic" at this stage would be circular — defining
the agent as the thing that defeats the cache, then demonstrating that it
defeats the cache. Mapping measured agent behaviour onto a calibrated
profile is Phase 4F and has not been done.

---

## F1. The knee exists, and it is sharp

**Configuration.** Commit 6f2c2e7. 16-core host (WSL2, Ryzen AI 7 350),
CPU-pinned: k6 on cores 0–3, Varnish 4–7, app 8–9, PostgreSQL 10–11,
observability 14–15. `THREADS=8`, `BACKLOG=128`, `DB_POOL_MAX=12`,
`VARNISH_SIZE=128m`. Corpus: 495 books, 16,954 chapters, 203,437-edge
link graph, fixed seed. Cacheable endpoint only. **Total arrival rate
held constant at 260 req/s throughout.** Cold cache before every
measurement; 180 s warm-up discarded; 180 s measured. 70 measurements,
randomised execution order (seed 42), 5 repetitions per point and 10 at
α ∈ {0.30, 0.35, 0.40}.

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
first met at **α = 0.15**: a **5.2× increase in p99 for a five-point
change in traffic composition**, at constant total arrival rate.

**This is not "more load breaks things".** Offered load is identical at
every point. Only composition changes.

**Amplification.** Origin load is λ·(1 − h):

    α = 0.00 → 260 × 0.171 = 44.5 req/s
    α = 0.15 → 260 × 0.266 = 69.2 req/s

A **15-point change in composition produces a 55% increase in origin
load** — an amplification of roughly 3.7×. Capacity planning that treats
automated traffic as ordinary requests ("agents are 20% of requests, so
add 20% capacity") underestimates the requirement by this factor, and
underestimates it non-linearly near saturation.

**p95 tracks p99.** At α ≥ 0.20 the two are within 5%: past the knee this
is not a tail phenomenon, essentially every request is slow.

**On queueing theory.** At α = 0.15 the origin operates at
ρ = 69.2/74 ≈ 0.94 against the separately measured capacity, and the knee
falls just below saturation. This is *consistent with* the rapid growth
of queueing delay as utilisation approaches capacity. It is not a
validated fit: no queueing model has been specified, no service-time
distribution measured, no theoretical curve compared against data.
Recorded as an open direction, not a result.

---

## F2. Per-class hit ratios are not invariant under composition

**The prediction failed.** From parameters measured in isolation
(h_H = 0.830, h_A = 0.493, C = 74 req/s), the mixture model

    λ_origin(α) = λ · [(1 − h_H) + α(h_H − h_A)]

predicted the knee at **α = 0.35**. Observed: **α = 0.15**. A factor
of 2.3.

**First diagnosis, since retracted.** The gap was initially attributed to
an in-mixture hit ratio for the low-locality class of ≈ 0.13, *inferred*
from the slope of the aggregate curve. Direct measurement shows this was
wrong. It is recorded because the inference appeared in an earlier
revision of this document, and because it illustrates why inference from
an aggregate must not substitute for the disaggregated measurement when
the latter is available — and it was, in the same CSV.

**Direct measurement.**

| α | h high-locality | h low-locality | h total |
|---|---|---|---|
| 0.00 | 0.829 | — | 0.829 |
| 0.05 | 0.821 | 0.296 | 0.794 |
| 0.10 | 0.812 | 0.294 | 0.760 |
| 0.15 | 0.806 | 0.325 | 0.734 |
| 0.20 | 0.803 | 0.362 | 0.715 |
| 0.25 | 0.801 | 0.366 | 0.692 |
| 0.30 | 0.796 | 0.399 | 0.676 |
| 0.35 | 0.789 | 0.374 | 0.644 |
| 0.40 | 0.785 | 0.386 | 0.625 |
| 0.45 | 0.781 | 0.397 | 0.608 |
| 0.50 | 0.777 | 0.401 | 0.589 |

Two effects, in opposite directions:

- **High-locality degrades modestly**: 0.829 → 0.777. Popular content is
  requested often enough to survive eviction pressure. The decline is
  monotonic over eleven consecutive points, which makes noise an unlikely
  explanation.
- **Low-locality *improves***: 0.296 → 0.401. As its share grows, the
  low-locality class accumulates cache residency and begins to benefit
  from its own long tail. Not anticipated, and against the intuition that
  a scanning workload can never benefit from caching.

**Decomposition at α = 0.50.** With both per-class ratios frozen at their
α → 0 values, the aggregate would be 0.5 × 0.829 + 0.5 × 0.296 = 0.563.
Observed: 0.589.

| | change | contribution to h_total |
|---|---|---|
| high-locality | 0.829 → 0.777 | **−0.026** |
| low-locality | 0.296 → 0.401 | **+0.053** |
| net | | **+0.026** |

**The interaction is bidirectional and its net sign is positive.**

**What this means for the model.** The failure was not interference
degrading the high-locality class — that effect exists but is small. The
failure was that **h_A measured in isolation (0.493) is not h_A in a
mixture (0.30–0.40), and is not constant either**: it depends on α. The
model must become

    λ_origin(α, S) = λ · [(1−α)(1 − h_H(α,S)) + α(1 − h_A(α,S))]

where S is the cache/working-set ratio. Per-class hit ratios are
functions of composition, not parameters.

**Stated for others.** Any mixture model of traffic classes parameterised
with per-class hit ratios measured in isolation will misestimate the
tolerable fraction of the aggressive class — here by 2.3×, in the
optimistic direction.

**Caveat.** At α = 0.05 the low-locality hit ratio rests on 5% of a run's
requests; that point is the least reliable. Per-point confidence
intervals have not been computed.

---

## F3. The transition is bimodal before it is broken

| α | individual p99 values (ms) | spread |
|---|---|---|
| 0.00 | 112, 118, 118, 121, 123 | 1.10× |
| 0.10 | 255, 272, 282, 286, 288 | 1.13× |
| **0.15** | **486, 656, 1476, 1535, 1654** | **3.40×** |
| 0.20 | 2912, 2946, 2951, 2989, 3005 | 1.03× |

Below the knee the system is predictable. Above it, predictably broken.
**At the transition, identical configurations produce outcomes differing
by more than 3×.** Two of five runs at α = 0.15 stayed under the
pre-registered threshold; three did not.

**Independent replication.** The mediator campaign (F6), a separate
experiment run a day later with three repetitions, gave a median p99 of
944 ms at 128 MB / α = 0.15 — *below* the 10× threshold, where F1 gave
1476 ms, *above* it. Same configuration, opposite verdicts. This is not a
contradiction between the experiments: it is the unstable band,
reproduced independently.

**Operational implication.** The danger is not that the system becomes
slow. It stops being *predictable* before it becomes slow. An operator
watching medians — or p95 averaged over hours — sees nothing until the
collapse. The variance moves first.

Working name for this region: **the unstable band**.

**Consequence for the knee definition.** Because the outcome is
probabilistic, a single threshold is not well defined. The criterion is
reported as two quantities:

    K50 = first α at which >=50% of runs exceed the threshold
    K90 = first α at which >=90% of runs exceed the threshold

with [K50, K90] as the unstable band. On the F1 data K50 = 0.15 and
K90 = 0.20; with five repetitions those estimates are coarse, and the
three repetitions of F6 are not sufficient to refine them.

**Caveat.** Five repetitions suffice to observe anomalous dispersion, not
to establish bimodality. Whether the distribution is genuinely bimodal or
merely heavy-tailed cannot be settled from these data. A dedicated
experiment is required: α from 0.12 to 0.18 in steps of 0.01, at least 20
repetitions, full latency distributions.

---

## F4. The plateau is set by the socket backlog (hypothesis)

For every α ≥ 0.20 the p99 settles at ~3000 ms and rises no further,
despite origin load continuing to increase.

With `BACKLOG=128` and the origin saturated near 74 req/s, the queue
drains in 128/74 ≈ 1.7 s; with service time added this is consistent with
the observed plateau. Requests are not shed in large numbers (0.4%): the
system queues rather than rejects.

**Prediction, untested.** Varying `BACKLOG` (64, 128, 256) should move
the plateau roughly proportionally while leaving the *position* of the
knee unchanged. If confirmed, this separates **where** the system breaks
(cache behaviour and origin capacity) from **how badly** it breaks
(admission policy). The arithmetic above is suggestive, not evidence.

---

## F5. Honeypot: identity and behaviour are independent

**Status: preliminary.** 82,618 requests over 4.5 days (2026-08-12 to
2026-08-16), roughly 24,000/day once indexed. No quantitative claim will
be published on fewer than eight weeks.

| class | requests | req/connection | req/unique URL | 404s |
|---|---|---|---|---|
| declared AI | 19,313 | **217.0** | 1.00 | 36 |
| browser-like | 35,125 | 9.5 | **2.50** | 628 |
| Meta | 18,225 | **1.0** | 1.11 | 0 |
| Google | 3,845 | 3.0 | 1.20 | 9 |
| Ahrefs | 2,814 | **1.0** | 1.00 | 0 |
| other | 3,204 | 1.4 | 2.12 | 652 |

**Critical qualification: the "declared AI" class is 99.5% one
operator.**

    GPTBot/1.4        19,220
    OAI-SearchBot         44
    ChatGPT-User          13
    PerplexityBot         10
    ClaudeBot              7
    CCBot                  7
    Claude-User            3
    Amazonbot              1

So "declared AI crawlers are well behaved" means "GPTBot is well
behaved" — n = 1 operator, and a *training* crawler rather than an agent.

**Genuinely agentic traffic — retrieval fetchers acting for a user in
real time — amounts to 16 requests out of 82,618.** The honeypot is
currently measuring automated web traffic, not agentic traffic.

**The finding worth keeping: identity and behaviour are independent.**

AhrefsBot is the **only** operator on the site sending Web Bot Auth
signature headers — cryptographically identified under the emerging IETF
scheme — and it opens a fresh TCP connection for every single request,
exactly like Meta. GPTBot, which offers no cryptographic identity at all,
reuses connections 217 times on average.

**Verifiable identity says nothing about infrastructure cost.** A policy
built on identity alone — admit the signed, reject the unsigned — will
admit expensive traffic and reject cheap traffic. This is an argument for
class-based resource budgeting over identity-based admission, and it
arrived from measurement rather than from the design.

**Classification hierarchy.** Traffic is assigned to a tier by the
strongest available evidence:

1. cryptographically authenticated (Web Bot Auth signature verifies)
2. provider-attributed (source address in a published range, reverse DNS)
3. declared (user-agent string only — forgeable)
4. behavioural (no trusted identity; observed access pattern)
5. unknown

With one rule: **identity is never inferred from behaviour.**

**Caveats.** 2026-08-12 and 2026-08-16 are partial days. Logs were
concatenated from rotated archives in a non-chronological order, which
does not affect aggregate counts but precludes time-series analysis
without re-sorting. The `browser-like` class includes the author's own
test traffic and the deployment health checks, not yet excluded.

---

## F6. Removing cache-capacity pressure removes the transition

**This is the central result.** The preceding findings establish a
phenomenon and a correlated chain. Because α drives every link of that
chain by construction, correlations along it identify nothing. F6
intervenes on the hypothesised mediator directly.

**Question.** Does eliminating contention for cache space eliminate the
low-locality-induced origin saturation?

**Configuration.** Commit 34027a7. Same host and pinning as F1.
`THREADS=8`, `BACKLOG=128`, `DB_POOL_MAX=12`, λ = 260 req/s throughout.
Cache size varied across three values; α across five; 3 repetitions;
45 measurements. Cold cache before every point; **600 s warm-up
discarded** (the validated minimum — see corrections), 180 s measured.
α and repetition randomised within each cache size; cache size not
randomised, since changing it requires restarting Varnish.

**Result.**

| cache | α | p99 median (ms) | hit | origin offered | origin served |
|---|---|---|---|---|---|
| **128 MB** | 0.00 | 121.8 | 0.827 | 44.9 | 47.6 |
| | 0.15 | 944.1 | 0.732 | 69.6 | 74.0 |
| | 0.30 | **2982.0** | 0.671 | 85.5 | 75.5 |
| | 0.50 | 3095.8 | 0.594 | 105.5 | 74.7 |
| | 1.00 | 3027.1 | 0.470 | 137.7 | 75.6 |
| **256 MB** | 0.00 | 30.5 | 0.931 | 18.0 | 19.2 |
| | 0.15 | 62.7 | 0.868 | 34.3 | 35.9 |
| | 0.30 | 99.6 | 0.823 | 46.0 | 48.0 |
| | 0.50 | 252.3 | 0.763 | 61.6 | 64.8 |
| | 1.00 | **689.2** | 0.730 | 70.1 | 73.0 |
| **512 MB** | 0.00 | 23.0 | 0.980 | 5.1 | 6.1 |
| | 0.15 | 20.0 | 0.989 | 3.0 | 3.7 |
| | 0.30 | 1.0 | 0.995 | 1.4 | 2.0 |
| | 0.50 | 1.0 | 0.997 | 0.8 | 1.3 |
| | 1.00 | 1.0 | 1.000 | 0.0 | 0.2 |

Applying the pre-registered criterion (`p99 > 10 × p99(α=0)`) within each
cache size:

| cache | threshold | knee |
|---|---|---|
| 128 MB | 1218 ms | **α = 0.30** |
| 256 MB | 305 ms | **α = 1.00** |
| 512 MB | 230 ms | **not observed through α = 1.00** |

**Increasing cache capacity systematically shifts the transition toward
higher low-locality fractions and eventually eliminates it within the
tested range.** With three cache sizes and a discrete threshold, this
establishes the direction of the shift, not the functional form of
K(S/W).

**The single most striking comparison.** At α = 0.50, with identical
total load, identical application, identical database, and identical
workload, changing only the cache size takes the p99 from **3096 ms to
1 ms** — a factor of roughly 3000.

**The cost inverts at large cache.** At 512 MB the low-locality workload
is not more expensive than the high-locality one — it is *less*:

    α = 0.00 → hit = 0.980, p99 = 23 ms
    α = 1.00 → hit = 1.000, p99 =  1 ms

Traversal covers the object space systematically, so after warm-up every
object is resident and every request is a hit. Zipf retains an
inexhaustible tail and keeps touching new objects. **The cost of the
low-locality workload is not a property of the workload. It emerges from
its interaction with bounded cache capacity.**

**Offered versus served origin load.** The two columns above are distinct
quantities: *offered* is λ(1−h), what the cache passes through; *served*
is the application's own request counter divided by elapsed time.

Below saturation they agree to within 4–7%, which closes the cache →
origin link quantitatively rather than by assumption.

At 128 MB with α ≥ 0.30 they diverge, and the divergence grows (−12%,
−29%, −45%) while the served rate pins at **74–76 req/s**. That value is
consistent with the origin capacity C = 74 req/s measured three days
earlier by an independent method. The gap between offered and served is
work accumulating in the queue — which is precisely what produces the
plateau of F4.

**Interpretation.** This is strong evidence that cache contention
mediates the observed transition. It is an intervention that removes the
phenomenon in this system; it does not establish that no other mechanism
could produce a similar transition in a different deployment, and the
ablations of Q3 remain necessary to identify which behavioural property
of the low-locality profile drives the effect.

**Nominal working set is not effective cache capacity.** 256 MB is 104%
of the 245 MB nominal working set, yet at α = 1.00 the hit ratio is only
0.730 and a transition is still observed. Only 512 MB removes it. The
245 MB figure is the corpus text size in the database, not the footprint
of the gzipped JSON responses that Varnish actually stores, and the
effective footprint has not been measured directly. Any statement of the
form "cache sized above the working set" must specify which working set.
This is recorded as an open measurement, not resolved.

**Caveats.**
- Three repetitions per point: sufficient for a qualitative
  discrimination, not for estimating K50/K90 or the shape of K(S/W).
- The application request counter used for *served* load includes the
  Docker health check (one request per 5 s, i.e. 0.2 req/s). At saturated
  rates this is 0.27% of the total and does not affect any conclusion; at
  512 MB, where rates fall below 1 req/s, it accounts for essentially all
  of the apparent positive discrepancy. Subsequent runs restrict the
  query to `endpoint="chapter"`.
- One cache implementation, one origin workload, one host.

---

## Open questions

Ordered by how much they would change the work.

**Q1 — Is cache contention the mechanism? — ANSWERED (F6).** Strongly
supported by intervention. Remaining refinement: measure the effective
cache footprint directly, and add cache sizes between 256 and 512 MB to
constrain the shape of K(S/W).

**Q2 — Which behavioural factor produces the effect?** Only locality is
varied so far. The other eight parameters — connection reuse, burstiness,
session state, think time, concurrency, client caching, header
completeness, diurnal modulation — require single-factor ablations. Until
these are done, "low-locality" cannot become "agentic".

**Q3 — Does the shape survive a different bottleneck?** Here the binding
resource is PostgreSQL CPU. Reducing DB cores, constraining the
connection pool below the thread pool, or introducing a downstream
service each move it. If the normalised curve keeps its shape,
generalisation is demonstrated; if not, the dependency has been found.

**Q4 — Is the knee invariant under normalisation?** Thread pools of 4, 8
and 12 with arrival rates scaled to hold λW/N constant should collapse
onto one curve.

**Q5 — Is the GIL contributing?** App CPU at the knee is ~31% against an
observed ceiling near 80%, which suggests not. Direct control:
`--workers 2 --threads 4` against `--workers 1 --threads 8`.

**Q6 — Does the service-time distribution change near the knee?** Only
the mean is measured. If the coefficient of variation rises as saturation
approaches, the cost distribution is changing and not merely its mean.

**Q7 — Characterise the unstable band.** α from 0.12 to 0.18 at 0.01,
≥20 repetitions, full latency distributions. Needed to establish whether
the distribution is bimodal and to estimate K50/K90 properly.

**Q8 — Does admission control bound severity without moving the knee?**
The `BACKLOG` sweep of F4, and then per-class resource budgeting: the
mitigation argument requires demonstrating that giving the low-locality
class its own thread and connection quota preserves service for the rest.

**Q9 — How does the unstable band behave under realistic dynamics?** All
measurements use stationary arrival rates. Real automated traffic is
bursty and lacks a diurnal cycle. A system whose *mean* utilisation sits
below the knee may still spend part of each day inside the band.

---

## Corrections and retractions

A running list. Nothing is deleted.

- **2026-08-12.** All measurements at `VARNISH_SIZE=2m` discarded:
  Varnish was in a crash-restart cycle (`signal=6`, `PANIC REENTRANCY`),
  initially misdiagnosed as CPU saturation because consumption was flat
  at 92% regardless of load. See `decisions.md` §5.
- **2026-08-14.** Hit-ratio measurements without a discarded warm-up are
  invalid: they include compulsory misses from cache filling and are
  indistinguishable from a capacity limit. Affected the first cache-size
  sweep, which appeared to plateau at h = 0.815 for all sizes >= 192 MB.
- **2026-08-15.** The pre-registered prediction of a knee at α = 0.35 is
  superseded by observation at α = 0.15. The pre-registration itself
  stands and is retained as made.
- **2026-08-16.** The diagnosis in the first revision of F2 — that the
  in-mixture low-locality hit ratio was ≈ 0.13, inferred from the
  aggregate slope — is **retracted**. Direct per-class measurement gives
  0.30–0.40 and shows the effect runs opposite to the one inferred. The
  structural conclusion survives; the magnitude and mechanism do not.
- **2026-08-16.** The mediator dry run (120 s warm-up) produced nearly
  identical hit ratios at 128 MB and 512 MB, which is impossible: it was
  measuring cache fill, not steady state. Dry-run numbers are a check of
  script logic and are never data.
- **2026-08-16.** An external review flagged a suspected column offset in
  the per-class extraction. It was not present: `sweep.sh` and
  `mediator.sh` use different CSV schemas (hit_h at column 14 and 12
  respectively), and the command ran against the sweep schema. The data
  confirm it independently — at α = 0 the low-locality hit ratio is
  exactly 0.000 and h_total equals h_high-locality, which is only
  possible if the columns are correct. Recorded because two CSV schemas
  in one project is a latent hazard; `mediator.sh` now validates its
  header and exits rather than migrating silently.
- **2026-08-16.** The origin request counter used in F6 includes the
  Docker health check. Quantified at 0.2 req/s: negligible under load,
  dominant in the 512 MB rows where rates fall below 1 req/s. No
  conclusion changes; the query is restricted to `endpoint="chapter"`
  from the next run onward.
- **2026-08-16.** The "working set = 245 MB" figure used throughout is
  the corpus text size in PostgreSQL, not the footprint of cached
  responses. It should not be used to claim a cache is "larger than the
  working set" — 256 MB exceeds it nominally and still exhibits
  contention. The effective footprint requires direct measurement.