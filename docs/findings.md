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
`VARNISH_SIZE=128m` (52% of the 245 MB working set). Corpus: 495 books,
16,954 chapters, 203,437-edge link graph, fixed seed. Cacheable endpoint
only. **Total arrival rate held constant at 260 req/s throughout.** Cold
cache before every measurement; 180 s warm-up discarded; 180 s measured.
70 measurements, randomised execution order (seed 42), 5 repetitions per
point and 10 at α ∈ {0.30, 0.35, 0.40}.

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

**Amplification.** This is the quantity that distinguishes the result
from prior work. Origin load is λ·(1 − h):

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
Claiming agreement with theory would require all four. Recorded as an
open direction, not a result.

**Caveat on C.** Capacity C = 74 req/s was measured under `THREADS=8`,
`VARNISH_SIZE=128m`, `DB_POOL_MAX=12`. Any quantitative use of C under a
different configuration requires re-measurement — including the mediator
experiment, which changes cache size.

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

**Direct measurement.** Per-class hit counters were recorded per run
(`ut_hit_zipf`, `ut_miss_zipf`, `ut_hit_traversal`,
`ut_miss_traversal`). Disaggregating the sweep:

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

- **High-locality degrades modestly**: 0.829 → 0.777 across the full
  range. Popular content is requested often enough to survive eviction
  pressure. The decline is monotonic over eleven consecutive points,
  which makes noise an unlikely explanation.
- **Low-locality *improves***: 0.296 → 0.401. As its share grows, the
  low-locality class accumulates cache residency and begins to benefit
  from its own long tail. This was not anticipated and runs against the
  intuition that a scanning workload can never benefit from caching.

**Decomposition at α = 0.50.** With both per-class ratios frozen at their
α → 0 values, the aggregate would be 0.5 × 0.829 + 0.5 × 0.296 = 0.563.
Observed: 0.589. The difference decomposes as:

| | change | contribution to h_total |
|---|---|---|
| high-locality | 0.829 → 0.777 | **−0.026** |
| low-locality | 0.296 → 0.401 | **+0.053** |
| net | | **+0.026** |

**The interaction is bidirectional and its net sign is positive.** The
low-locality class gains more than the high-locality class loses.

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
optimistic direction. This does not appear to be stated in the caching
literature.

**Caveat.** At α = 0.05 the low-locality hit ratio rests on 5% of a run's
requests; that point is the least reliable in the table. Per-point
confidence intervals have not been computed.

---

## F3. The transition is bimodal before it is broken

Dispersion across repetitions is not uniform:

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

**Operational implication.** The danger is not that the system becomes
slow. It stops being *predictable* before it becomes slow. An operator
watching medians — or p95 averaged over hours — sees nothing until the
collapse. The variance moves first.

Working name for this region: **the unstable band**. It is not the knee,
which is a threshold; it is the interval in which the outcome becomes a
coin flip.

**Consequence for the knee definition.** Because the outcome at α = 0.15
is probabilistic, a single threshold is not well defined. The
pre-registered criterion should be reported as two quantities:

    K50 = first α at which >=50% of runs exceed the threshold
    K90 = first α at which >=90% of runs exceed the threshold

with [K50, K90] reported as the unstable band. On these data K50 = 0.15
and K90 = 0.20, but with five repetitions those estimates are coarse.

**Caveat.** Five repetitions suffice to observe anomalous dispersion, not
to establish bimodality. Whether the distribution is genuinely bimodal or
merely heavy-tailed cannot be settled from these data. A dedicated
experiment is required: α from 0.12 to 0.18 in steps of 0.01, at least 20
repetitions, full latency distributions rather than summary percentiles.

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
knee unchanged. If confirmed, this separates two quantities:

- **where** the system breaks — set by cache behaviour and origin
  capacity;
- **how badly** it breaks — set by admission policy.

This is the empirical link between the measurement and the mitigation
argument: admission control does not prevent the transition, it bounds
the consequences. The arithmetic above is suggestive, not evidence.

---

## F5. Honeypot: identity and behaviour are independent

**Status: preliminary.** 82,618 requests over 4.5 days (2026-08-12 to
2026-08-16), roughly 24,000/day once the site was indexed. No
quantitative claim will be published on fewer than eight weeks. The
contrasts below are recorded because they are large, and because one of
them changes how the classification problem should be framed.

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
currently measuring automated web traffic, not agentic traffic. That
distinction must be maintained in anything published from it.

**The finding worth keeping: identity and behaviour are independent.**

AhrefsBot is the **only** operator on the site sending Web Bot Auth
signature headers — cryptographically identified under the emerging IETF
scheme — and it opens a fresh TCP connection for every single request,
exactly like Meta. GPTBot, which offers no cryptographic identity at all,
reuses connections 217 times on average.

**Verifiable identity says nothing about infrastructure cost.** A scheme
that authenticates crawlers does not, by itself, distinguish expensive
ones from cheap ones. A policy built on identity alone — admit the
signed, reject the unsigned — will admit expensive traffic and reject
cheap traffic. This is an argument for class-based resource budgeting
over identity-based admission, and it arrived from measurement rather
than from the design.

**A classification hierarchy follows.** Traffic is assigned to a tier by
the strongest available evidence:

1. cryptographically authenticated (Web Bot Auth signature verifies)
2. provider-attributed (source address in a published range, reverse DNS)
3. declared (user-agent string only — forgeable)
4. behavioural (no trusted identity; observed access pattern)
5. unknown

With one rule: **identity is never inferred from behaviour.** Behavioural
features construct workload classes; they do not assign operator
identity. On day one the highest-volume automated client presented as
Chrome 42 on Windows 7 — behaviour showed it was automated, but could not
show whose.

**Caveats.** 2026-08-12 and 2026-08-16 are partial days. Logs were
concatenated from rotated archives in an order that was not strictly
chronological, which does not affect aggregate counts but precludes
time-series analysis without re-sorting. The `browser-like` class
includes the author's own test traffic and the deployment health checks,
not yet excluded.

---

## Open questions

Ordered by how much they would change the work.

**Q1 — Is cache contention the mechanism, or a correlate?** The mediator
intervention answers this: size the cache above the working set, removing
eviction competition. Verified precondition: at 512 MB with 600 s
warm-up, h_H reaches 0.981, so origin load at α = 0 falls to ~5 req/s,
7% of capacity. If the mechanism is cache contention, the knee must
vanish at every α including 1.00. *The single most important outstanding
experiment.*

**Q2 — Does the knee position move with the cache/working-set ratio?** A
binary outcome (knee at 128m, absent at 512m) is weaker than a
quantitative one. If K = K(S/W) moves systematically, the relation is
quantitative and far harder to obtain by accident.

**Q3 — Which behavioural factor produces the effect?** Only locality is
varied so far. The other eight parameters — connection reuse, burstiness,
session state, think time, concurrency, client caching, header
completeness, diurnal modulation — require single-factor ablations.

**Q4 — Does the shape survive a different bottleneck?** Here the binding
resource is PostgreSQL CPU. Reducing DB cores, constraining the
connection pool below the thread pool, or introducing a downstream
service each move it. If the normalised curve keeps its shape,
generalisation is demonstrated; if not, the dependency has been found.

**Q5 — Is the knee invariant under normalisation?** Thread pools of 4, 8
and 12 with arrival rates scaled to hold λW/N constant should collapse
onto one curve.

**Q6 — Is the GIL contributing?** App CPU at the knee is ~31% against an
observed ceiling near 80%, which suggests not. Direct control:
`--workers 2 --threads 4` against `--workers 1 --threads 8` — same thread
count, double interpreter capacity.

**Q7 — Does the service-time distribution change near the knee?** Only
the mean is measured. If the coefficient of variation rises as saturation
approaches, the cost distribution is changing and not merely its mean —
which matters for any queueing treatment.

**Q8 — How does the unstable band behave under realistic dynamics?** All
measurements use stationary arrival rates. Real automated traffic is
bursty and lacks a diurnal cycle. A system whose *mean* utilisation sits
below the knee may still spend part of each day inside the unstable band.

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
  structural conclusion (per-class hit ratios are not invariant under
  composition) survives; the magnitude and mechanism do not.
- **2026-08-16.** The mediator dry run (45 s warm-up) produced identical
  hit ratios at 128 MB and 512 MB, which is impossible: it was measuring
  cache fill, not steady state. Dry-run parameters were changed. Dry-run
  numbers are a check of script logic and are never data.
- **2026-08-16.** An external review flagged a suspected column offset in
  the per-class extraction. It was not present: `sweep.sh` and
  `mediator.sh` use different CSV schemas (hit_h at column 14 and 12
  respectively), and the command in question ran against the sweep
  schema. The data confirm it independently — at α = 0 the low-locality
  hit ratio is exactly 0.000 and h_total equals h_high-locality, which is
  only possible if the columns are correct. Recorded because two CSV
  schemas in one project is a latent hazard.