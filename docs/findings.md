# Findings

Results as obtained, including predictions that failed and diagnoses
later retracted. Separate from `decisions.md` (which records *why* things
were done) and from `contribution-boundary.md` (which records what is
ours to claim).

Three sources, three roles:

| source | what it establishes | scale |
|---|---|---|
| **Cloudflare Radar** | that the problem is real and mis-handled | global |
| **controlled testbed** | why it happens, causally | one origin |
| **honeypot** | that the behavioural classes are not invented | one site |

**Terminology.** In the testbed the two synthetic workload classes are
named by what distinguishes them, not by what they represent:
**high-locality** (Zipf(1) over popularity, standing in for human
browsing) and **low-locality** (uniform non-repeating traversal, standing
in for exhaustive crawling). α is the low-locality fraction. It is not
the agentic fraction: only one of nine workload parameters is varied.

---

# Part 1 — Global scale (Cloudflare Radar)

All figures from the Radar API, 28-day window ending 2026-08-22, unless
stated. Cloudflare's network covers roughly a fifth of the web; the
denominator for bot traffic figures is HTML requests, not all requests
and not bytes. Cloudflare has a commercial interest in bot management —
but these are its own measurements of its own network, published
openly, and the specific comparisons below are ones it has not itself
drawn.

## G1. The web refuses the wrong traffic

Response codes by crawl purpose:

| | **Training** | **Search** | **User Action** |
|---|---|---|---|
| | *nobody waiting* | | ***a person waiting*** |
| 200 OK | **63.7%** | 53.9% | **25.0%** |
| 403 Forbidden | 17.6% | 19.0% | **34.5%** |
| 404 Not Found | 5.5% | 10.3% | 18.6% |
| 429 Too Many Requests | 2.6% | 4.1% | 6.7% |
| **refused (403+404+429)** | **25.7%** | 33.4% | **59.8%** |

The class in which a human is waiting in real time is blocked at twice
the rate of the batch class and receives a valid response one time in
four. The batch class, where nobody is waiting and service could be
deferred at no cost to anyone, succeeds nearly two times in three.

**Why.** Blocking policy is organised around **identity** — is this an AI
bot? — not around cost or urgency. The agent acting for a person is
caught in the net built for the training crawler.

**Caveat, important.** A 403 may also express deliberate publisher
policy: paywalls, licensing disputes, a decision not to serve AI systems
at all. The data cannot separate intent from misclassification. What the
data do show is the *outcome*: whatever the reason, the traffic with a
human attached is the traffic most often refused.

## G2. Class composition is re-proportioning fast

Weekly series, 52 weeks, 2025-08-18 → 2026-08-17:

| class | Aug 2025 | Aug 2026 | change |
|---|---|---|---|
| **User Action** | 2.20% | **5.06%** | **+130%** |
| **Search** | 9.03% | **17.24%** | **+91%** |
| Training | 36.42% | 39.35% | +8% |
| Mixed Purpose | 51.68% | 36.67% | −29% |
| Undeclared | 0.67% | 1.69% | +153% |

The interactive classes are doubling annually while training is flat.
The mix is changing under everyone's feet, and the classes have different
resource footprints — which is the whole argument.

**Caveat.** The Mixed Purpose decline is partly reclassification, not
only a traffic shift: Cloudflare relabelled categories during this
window, and monthly views were rewritten while quarterly views were not.
Quarterly views should be preferred and the discontinuity stated. This
also means a historical series queried today is not the series one would
have obtained by querying day by day.

## G3. Nobody revalidates

304 Not Modified responses are **0.53%** of all AI bot requests. By
class: Training 0.52%, User Action 0.68%, Search does not register in the
top status codes at all.

Conditional requests (`If-None-Match`, `If-Modified-Since`) exist
precisely so a client can ask "has this changed?" and receive a few
hundred bytes of headers instead of the whole document. They are
essentially unused. Every crawler re-downloads unchanged content in full.

Read the Docs reported the same qualitatively in July 2024 — 73 TB of
HTML in a month from one crawler, with no ETag support. This is the
measurement.

## G4. The classes fetch different things

Content type by purpose:

| | Training | Search | User Action |
|---|---|---|---|
| HTML | 75.6% | 67.9% | **78.5%** |
| Plain text | 8.7% | 8.1% | **14.0%** |
| JavaScript | 1.7% | **12.5%** | 0.9% |
| Images | 6.0% | 7.2% | 1.9% |
| JSON | 4.3% | 2.4% | 2.6% |

Agents fetch text and almost nothing else — 92.5% HTML and plain text,
under 1% JavaScript, under 2% images. Search crawlers fetch JavaScript at
seven times the agentic rate, consistent with rendering. Training
crawlers take the most images.

These are different resource footprints, measured, before any testbed is
involved. It is direct support for treating the classes separately.

---

# Part 2 — Origin behaviour (controlled testbed)

Varnish → gunicorn/Flask (bounded thread pool) → PostgreSQL, CPU-pinned
containers, VictoriaMetrics at 1 s, k6 in strict open-loop mode
(`constant-arrival-rate`, avoiding coordinated omission). Corpus: 495
Project Gutenberg books, 16,954 chapters, measured cached-object
footprint **438 MB** (25.9 KB per object). Cold cache before every
measurement, warm-up discarded, randomised execution order.

## O1. Composition alone produces a regime transition

Latest campaign, 2026-08-19: `THREADS=8`, `VARNISH_SIZE=128m`,
**λ = 260 req/s held constant at every point**, 5–10 repetitions,
randomised order.

| α | p99 median (ms) | hit ratio | pool occupancy |
|---|---|---|---|
| 0.00 | 132 | 0.828 | 21% |
| 0.05 | 297 | 0.794 | 33% |
| 0.10 | 468 | 0.764 | 53% |
| 0.15 | 679 | 0.737 | 76% |
| **0.20** | **2681** | 0.712 | **93%** |
| 0.25 | 3263 | 0.692 | 96% |
| 0.30 | 3278 | 0.670 | 98% |
| 0.50 | 3234 | 0.578 | 99% |

Offered load is identical at every point. Only composition changes. This
is not "more load breaks things".

**Amplification.** Origin load is λ(1−h): 44.7 req/s at α=0, 68.4 at
α=0.15. **A 15-point change in composition produces a 53% increase in
origin load.** Capacity planning that treats automated traffic as
ordinary requests underestimates by this factor, and non-linearly near
saturation.

Pre-registered knee criterion (`p99 > 10 × p99(0)` = 1322 ms):
**K50 = 0.20, K90 = 0.30.**

## O2. The stability boundary is resource-based, not composition-based

**This is the most transferable result.**

Across four campaigns the knee always occurred at 90–97% thread pool
occupancy. The α at which that happened varied:

| campaign | knee at α | pool occupancy | origin capacity C |
|---|---|---|---|
| 2026-08-15 | 0.15 | 96% | 74 req/s |
| 2026-08-16 (mediator, 128m) | 0.30 | 97% | ~80 |
| 2026-08-18 | never reached | max 75% | 86 |
| 2026-08-19 | 0.20 | 93% | ~88 |

The 2026-08-18 campaign is the informative one: a repeat of the first,
with **identical hit ratios** (0.708 vs 0.715 at α=0.20, reproducible to
1%) and p99 nine times lower. Nothing about the cache had changed. The
database had warmed — PostgreSQL's working set had migrated fully into
`shared_buffers` (blks_hit 99.96%) — and origin capacity had risen from
74 to 86 req/s, so ρ = λW/N fell from 0.98 to 0.75 and the system never
approached the boundary.

**There is no universal "AI percentage limit". There is a
resource-utilisation boundary.** An operator cannot use someone else's α;
they can watch their own ρ, which is a number already in their
monitoring.

*How this was found:* by accident, from a campaign that produced no
result. It is recorded as a discovery rather than discarded as a failed
run, and it is the reason the project's central question changed from
"what is the threshold" to "what does each class cost".

## O3. Cache contention is the causal mediator

Correlation along the chain identifies nothing: α drives every link by
construction. This is an intervention on the hypothesised mediator.

Cache capacity varied at fixed λ = 260, 2026-08-16:

| cache | knee | p99 at α=0.50 |
|---|---|---|
| 128 MB | α = 0.30 | 3096 ms |
| 256 MB | α = 1.00 | 252 ms |
| 512 MB | **absent** | **1 ms** |

**At α = 0.50, changing only the cache size takes p99 from 3096 ms to
1 ms** — a factor of roughly 3000, with identical traffic, application
and database.

At 512 MB the low-locality workload reaches hit = 1.000 against Zipf's
0.980: the cost inverts. This is textbook scan-versus-LRU behaviour —
above the object set every object is resident after the first pass, while
Zipf retains an inexhaustible tail — and is stated to illustrate the
mechanism, **not as a finding**. Its consequence, however, is the
argument: *the cost of the low-locality workload is not a property of the
workload; it emerges from its interaction with bounded cache capacity.*

**Caveat.** Three repetitions per point: sufficient for qualitative
discrimination, not for estimating the shape of K(cache size). Cache
sizes are stated as configured capacity; whether 512 MB exceeds the true
footprint (438 MB measured) is close enough to be uncertain.

## O4. Per-class hit ratios are not invariant under composition

Measured directly per class (2026-08-19, 128 MB):

| α | high-locality | low-locality | total |
|---|---|---|---|
| 0.00 | 0.828 | — | 0.828 |
| 0.05 | 0.819 | 0.330 | 0.794 |
| 0.15 | 0.806 | 0.345 | 0.737 |
| 0.30 | 0.789 | 0.392 | 0.670 |
| 0.50 | 0.764 | 0.392 | 0.578 |

Two effects in opposite directions: high-locality degrades modestly
(0.828 → 0.764, monotonic over nine points), low-locality **improves**
(0.330 → 0.392).

**The mechanism, and it matters for Part 3.** The low-locality class
samples uniformly, so it does not care *which* objects are resident — only
how many. Its hit ratio is therefore approximately cache/footprint,
regardless of who put those objects there. **It free-rides on the cache
the human traffic filled.**

**Consequence for modelling.** A mixture model parameterised with
per-class hit ratios measured *in isolation* misestimates the tolerable
aggressive-class fraction by **2.3×, in the optimistic direction**. The
prediction from isolated parameters was a knee at α = 0.35; observed
0.15.

**Outstanding check.** This may exist in the CPU shared-cache contention
literature (Intel CAT/RDT, Bubble-Up, Quasar) under different
terminology. Search before claiming novelty.

## O5. For uniform access, hit ratio is cache over footprint

Predicted from first principles: a client sampling uniformly hits a
cached object with probability equal to the resident fraction of the
corpus. 128 MB / 438 MB = **0.29**. Measured at low α: **0.33**.

Within 13%, with no free parameters. Used as **validation of the
testbed**, not as a discovery — it is elementary probability.

Its architectural consequence is not elementary: for this class there is
no locality to exploit, so **no eviction policy can do better than
chance**. Caching stops being a question of *what to keep* and becomes
one of *who gets to keep*.

## O6. The transition is bimodal before it breaks

Individual repetitions, 2026-08-19:

| α | individual p99 (ms) | over threshold |
|---|---|---|
| 0.15 | 654, 658, 679, 848, 906 | 0/5 |
| **0.20** | **645, 1301, 2681, 2787, 2991** | **3/5** |
| 0.25 | 1007, 3156, 3263, 3288, 3303 | 4/5 |
| 0.30 | all above 3000 | 10/10 |

At α = 0.20 the same configuration produces 645 ms or 2991 ms. Below the
band the system is predictable, above it predictably broken; in between
the outcome is a coin flip.

The p99/p95 ratio collapses from 2.9 at α=0.10 to 1.1 at α=0.20: before
the transition it is a tail phenomenon, after it every request is slow.
The convergence of the two percentiles *is* the transition.

**Operational implication.** The system stops being *predictable* before
it becomes slow. An operator watching medians sees nothing until the
collapse. The variance moves first.

**Caveat.** Five to ten repetitions establish anomalous dispersion, not
bimodality. A dedicated experiment is required: α from 0.18 to 0.24 in
steps of 0.01, ≥20 repetitions, full latency distributions.

## O7. The plateau is set by the socket backlog (hypothesis, untested)

p99 settles at ~3000 ms for every α above the knee. With `BACKLOG=128`
and the origin saturated near 88 req/s, the queue drains in ~1.5 s; with
service time this is consistent with the plateau. Requests are queued,
not shed (loss stays under 0.4%).

If varying `BACKLOG` moves the plateau while leaving the knee position
unchanged, this separates **where** the system breaks (cache behaviour
and origin capacity) from **how badly** (admission policy). Arithmetic,
not evidence.

## O8. The boundary survives a change of architecture

**The invariance test.** O2 established that the knee occurs at a
resource-utilisation boundary rather than at a fixed traffic composition,
but all four campaigns supporting it ran on one machine. If the boundary
were an artefact of that hardware — its cache hierarchy, its SMT, its
scheduler — the claim would not transfer.

The harness was rebuilt on a different architecture and the campaign
repeated.

**Configuration.** Oracle Cloud VM.Standard.A1.Flex, 6 Ampere
Neoverse-N1 cores, no SMT (1 thread per core), 24 GB, Ubuntu 24.04
aarch64. CPU-pinned: k6 core 0, Varnish 1, app 2, PostgreSQL 3–5,
observability shares core 0. `THREADS=8`, `BACKLOG=128`,
`VARNISH_SIZE=128m` — identical to the x86 host. Corpus identical: 495
books, 16,954 chapters, 203,437-edge link graph, same seed.

Parameters measured on this machine: h_H = 0.791, **h_A = 0.000**,
C ≈ 85–100 req/s. λ held constant at 220 req/s. 65 measurements,
randomised order, 5 repetitions per point and 10 at α ∈ {0.30, 0.35,
0.40}.

**Result.**

| α | p99 median (ms) | p95 (ms) | hit ratio | pool occupancy |
|---|---|---|---|---|
| 0.00 | 82.9 | 46.9 | 0.827 | 21% |
| 0.05 | 105.9 | 57.4 | 0.791 | 25% |
| 0.10 | 141.9 | 80.3 | 0.753 | 40% |
| 0.15 | 184.6 | 115.1 | 0.713 | 53% |
| 0.20 | 407.1 | 232.4 | 0.673 | 72% |
| **0.25** | **1970.8** | 1390.4 | 0.636 | **89%** |
| 0.30 | 2547.1 | 2430.8 | 0.601 | 95% |
| 0.35 | 2606.6 | 2483.9 | 0.565 | 97% |
| 0.40 | 2635.4 | 2510.9 | 0.528 | 97% |
| 0.50 | 2626.4 | 2527.5 | 0.452 | 97% |

Pre-registered criterion (p99 > 10 × 82.9 = 829 ms): **knee at
α = 0.25, pool occupancy 89%**.

**The invariance, across five campaigns:**

| host | date | knee at α | pool occupancy |
|---|---|---|---|
| Ryzen AI 7 350, WSL2, 16 threads | 2026-08-15 | 0.15 | 96% |
| same | 2026-08-16 | 0.30 | 97% |
| same | 2026-08-18 | not reached | max 75% |
| same | 2026-08-19 | 0.20 | 93% |
| **Ampere Neoverse-N1, 6 cores** | **2026-08-27** | **0.25** | **89%** |

**The composition at which the knee occurs varies from 0.15 to 0.30
across architectures, CPU generations, core counts, SMT presence and
database warmth. The pool occupancy at which it occurs stays between 89%
and 97%.**

The 2026-08-18 campaign remains the control: it never exceeded 75%
occupancy and never produced a knee at any α.

**What this licenses, and what it does not.** It licenses reporting the
boundary in normalised terms — an operator watching their own pool
occupancy has a transferable quantity, whereas someone else's α is
useless to them. It does not license claiming a universal constant: two
architectures are two points, the pool size was 8 in every campaign, and
the bottleneck was PostgreSQL CPU throughout. Q4 (varying pool size and
bottleneck type) remains open.

**A secondary observation: the transition is sharper on the noisier
machine.** Dispersion across repetitions at α = 0.30 was 4% here (ten
runs between 2495 and 2597 ms) against more than 300% on the x86 host at
its transition point. Without SMT, without competing processes and
without a virtualisation layer, the ARM host behaves far more
deterministically. The unstable band of O6 is therefore not a property of
the phenomenon alone but of the platform's own variability — which
weakens the "bimodal" reading and strengthens the operational one: the
variance that matters is the variance a real deployment actually has.

**The curve is also better resolved here.** Five points below the knee
and five above, with a graded rise (185 → 407 → 1971 ms) rather than the
single jump observed on x86 (468 → 2681 ms). Hit ratio falls almost
perfectly linearly, −0.075 per 0.10 of α, consistent with h_A = 0.

**h_A = 0.000, and why it is the correct value.** On this machine the
low-locality class achieves no cache hits at all. The mechanism is
textbook: a sequential scan over an object set larger than the cache
causes LRU to evict precisely the object that will be needed next. It
also matches the honeypot, where GPTBot, AhrefsBot and Amazonbot all show
requests-per-URL of exactly 1.00 and a Gini coefficient of 0.00. The
values of 0.30–0.52 measured earlier on x86 were an artefact — see the
retraction of 2026-08-26.

Amplification is therefore r = (1 − 0) / (1 − 0.791) = **4.8**: at equal
request counts, exhaustive traffic imposes nearly five times the origin
load of human traffic.

---

# Part 3 — Operator behaviour (honeypot)

`theslowshelf.org`, 18,720 pages of public domain literature, robots.txt
explicitly permitting all AI crawlers. 153,680 requests, 2026-08-12 to
2026-08-19, roughly 20,000/day once indexed. Author's own browsing and
deployment health checks excluded.

**One site, one week.** These are case-study observations. Where they are
corroborated by Radar at global scale, that is stated.

| operator | requests | req/conn | req/URL | coverage | Gini | signs |
|---|---|---|---|---|---|---|
| Meta | 25,730 | **1.0** | 1.49 | 92% | 0.19 | no |
| GPTBot | 19,228 | **686.7** | 1.00 | 103% | **0.00** | no |
| AhrefsBot | 19,175 | **1.0** | 1.00 | 102% | **0.00** | **yes** |
| SemrushBot | 16,185 | 1.0 | 1.01 | 86% | 0.01 | no |
| Amazonbot | 10,218 | 1.0 | 1.00 | 55% | **0.00** | no |
| Googlebot | 3,972 | 2.8 | 1.22 | **17%** | **0.18** | no |
| browser-like | 36,300 | 7.5 | **2.58** | 75% | 0.29 | — |

## H1. Verifiable identity does not predict cost

**AhrefsBot is the only operator on the site sending Web Bot Auth
signature headers** — cryptographically identified under the emerging
IETF scheme that the industry is adopting to decide who to admit — and it
opens exactly one TCP connection per request. GPTBot, which offers no
cryptographic identity at all, reuses connections 687 times.

A policy that admits the signed and rejects the unsigned admits the
expensive and rejects the cheap.

This is one counterexample, from one site, with one signing operator. A
counterexample is sufficient to refute "identity predicts cost"; it is
not sufficient to characterise the relationship.

## H2. Connection reuse varies by three orders of magnitude

686.7 requests per connection for GPTBot; exactly 1.0 for Meta,
AhrefsBot, SemrushBot and Amazonbot. Meta runs HTTP/2 across 331
addresses and opens a fresh connection for every request, which defeats
the only reason HTTP/2 exists.

Not found in any prior measurement — search covered IMC/PAM papers and
the Cloudflare, Fastly, Akamai, Vercel and Bunny engineering blogs, which
report requests per minute and per IP but not per connection.

**Caveat.** nginx `$connection` is a per-worker serial; the key used is
(ip, connection), so distinct connections are underestimated and
requests-per-connection overestimated. The error direction is known: 1.0
is a floor that no collision can produce spuriously.

## H3. Selective versus exhaustive crawling

Googlebot covers 17% of the site with Gini 0.18 — some pages matter more.
GPTBot, AhrefsBot and Amazonbot cover the whole site with **Gini 0.00**:
perfectly uniform, every page exactly once, no page more important than
any other.

The difference is economic before it is technical. Search crawling is
constrained by expected value per page — indexing costs, and the return
is a click. Training crawling has no such constraint: every page is worth
the same as training data, so take everything, once.

Gini is the discriminant, and it is computable from any access log.

**Caveat.** Googlebot's low coverage may reflect crawl budget on a
one-week-old domain with no backlinks rather than policy. Continued
collection distinguishes the two: if Google is still at 20% after two
months while GPTBot has completed three full passes, it is policy.

## H4. Zero revalidation

**One 304 response in 153,680 requests.** Corroborates G3 at site level:
what Radar measures at 0.53% globally is effectively zero here.

## H5. Agentic traffic is concentrated, not rare

Genuinely agentic traffic — retrieval fetchers acting for a user in real
time — amounted to **34 requests out of 153,680**, or 0.11% of the AI
traffic on the site. Globally, User Action is **5.06%** of AI crawling: a
factor of roughly 40.

**Agentic traffic goes where people ask questions** — Wikipedia, GitHub,
news, documentation. A small new site will never see it in useful
quantity, however long it runs.

**Consequence for the method.** Volume and trend for the agentic class
come from Radar. Behaviour, if needed for a workload profile, must be
generated deliberately by querying commercial assistants against the
site. Waiting is not a strategy.

## H6. Scanning for AI infrastructure

Probes for `/v1/models`, `/mcp`, `/api/mcp`, `/sse` — automated traffic
searching for exposed AI infrastructure on a site that hosts none.
Already documented by SANS ISC (diary 33150) and Knostic (July 2025);
recorded as independent confirmation, not as a finding.

---

# Open questions

**Q1 — The scan-resistance trade-off. Sign unknown.** *Highest priority.*

Scan-resistant eviction protects the human working set. But O4 shows the
scan class free-rides on the shared cache: sampling uniformly, it hits
whatever is resident. Partitioning removes that free ride and sends all
of it to the origin.

Computed on measured data at α = 0.15, moving from shared LRU to full
reservation for the human class:

    human gain     221 req/s × 0.022  =   +4.9 req/s saved
    scan loss       39 req/s × 0.345  =  −13.5 req/s added
    net                                   +8.6 req/s

Origin load 68.4 → 77.0. With C ≈ 88, utilisation moves 0.78 → 0.88:
**from safe to the edge of the knee.**

But substituting the harmonic model for h_high instead of the measured
value reverses the sign. The model error exceeds the effect. **The sign
cannot be predicted; it must be measured.** Three outcomes, all
publishable: the paradox exists (Zhang's proposal creates an origin
problem); it does not (partitioning improves both); or there is an
interior optimum (a Pareto frontier and a quantified policy choice).

**Q2 — Optimal reserve fraction.** If a trade-off exists, locate the
reserve share minimising total origin load, which will differ from the
one minimising human latency.

**Q3 — Origin-side per-class admission control.** Cache partitioning is
insufficient: the exhaustive stream reaches the origin regardless. Give
each class a bounded thread and connection budget. The prediction is
asymmetric — the interactive class recovers while the batch class barely
notices, because it was never thread-limited but limited by the
contention it created. If it holds, the conflict is apparent and nobody
needs blocking. This is the answer to G1.

**Q4 — Generality.** Does the shape survive different pool sizes and a
different bottleneck (DB CPU vs connection pool vs downstream service)?
Normalised curves should collapse onto one.

**Q5 — Is O4 already published under other terminology?** The CPU
shared-cache contention literature. Check before claiming.

**Q6 — Characterise the unstable band.** α 0.18–0.24 at 0.01, ≥20
repetitions, full distributions.

**Q7 — Does the service-time distribution change near the knee?** Only
the mean is measured. A rising coefficient of variation would matter for
any queueing treatment.

**Q8 — Behaviour under realistic dynamics.** All measurements use
stationary arrival rates. Real automated traffic is bursty and lacks a
diurnal cycle; a system whose mean utilisation sits below the knee may
spend part of each day inside the band.

---

# Corrections and retractions

Nothing is deleted.

- **2026-08-12.** All measurements at `VARNISH_SIZE=2m` discarded:
  Varnish was in a crash-restart cycle (`signal=6`, `PANIC REENTRANCY`),
  initially misdiagnosed as CPU saturation because consumption was flat
  at 92% regardless of load.
- **2026-08-14.** Hit-ratio measurements without a discarded warm-up are
  invalid: they include compulsory misses from cache filling and are
  indistinguishable from a capacity limit.
- **2026-08-15.** The pre-registered prediction of a knee at α = 0.35 is
  superseded by observation at 0.15. The pre-registration stands as made;
  the cause is O4.
- **2026-08-16.** The inferred in-mixture low-locality hit ratio of ≈0.13
  is **retracted**. Direct per-class measurement gives 0.33–0.39, and the
  effect runs opposite to the inference.
- **2026-08-16.** "The α=1 inversion at large cache is counterintuitive
  and unreported" — **withdrawn**. Textbook scan-versus-LRU behaviour.
- **2026-08-16.** "Cache larger than the working set" — the 245 MB figure
  was corpus text in PostgreSQL, not cached-object footprint, measured
  later at 438 MB. Cache sizes are now stated as configured capacity.
- **2026-08-18.** The campaign that produced no knee was initially read
  as a failure. It is O2, and it changed the project's central question.
- **2026-08-19.** The correction preventing the low-locality profile from
  revisiting produced **no measurable change** in hit ratios (0.764 vs
  0.760 at α=0.10). The prediction that it would raise the cost by 60%
  was wrong: within the measurement window the previous profile already
  revisited rarely. The correction is retained as a guarantee rather than
  an accident, but the diagnosis behind it was mistaken.
- **2026-08-21.** "The web cannot distinguish human from agent traffic" —
  **withdrawn**. Cloudflare shipped exactly that capability in July 2026.
  The defensible claim is that knowing the class is not enough without
  knowing its cost.
- **2026-08-21.** The central question changed from "at what fraction
  does the origin collapse" to "what does each class cost, and what
  budget does it deserve". The first is machine-dependent (O2) and its
  second half is queueing theory from 1961. Prior results are retained;
  their role changed.
- **2026-08-26.** All measurements of the low-locality class hit ratio
  h_A taken before this date are **retracted**. The traversal profile
  used a random per-run offset into the corpus permutation, introduced on
  2026-08-19 to prevent warm-up and measurement traversing the same
  sequence. Because the permutation is bijective modulo the corpus size,
  only `offset mod 16954` mattered, and its value determined how much the
  measurement window overlapped the portion of the corpus the warm-up had
  just loaded. The overlap — and therefore h_A — was a lottery.

  Demonstrated on the ARM host: three consecutive repetitions, identical
  configuration, identical rate, **exactly 7201 completed requests each**,
  zero dropped, system far below saturation. Measured h_A: **0.051,
  0.287, 0.362**.

  This explains the incoherent values recorded earlier: 0.493 on
  2026-08-13, 0.330–0.392 across the sweeps of 15–19 August, 0.002 and
  0.378 in two runs thirty minutes apart on 2026-08-26. None of them were
  measuring a property of the workload.

  Fixed by deriving the offset deterministically from the experiment
  seed. Verification: three repetitions now return **0.667, 0.667,
  0.667** — identical to three decimal places.

  The value that stands is **h_A = 0.000**, measured under a warm-up
  long enough to exceed cache capacity, which is the steady-state regime
  and the one matching real crawler behaviour on the honeypot.

  Consequences: r rises from 2.6 to **4.8**; the amplification claim in
  O1 was conservative by roughly a factor of two; F2's per-class
  decomposition must be re-measured before it can be claimed, since it
  rests on h_A values now known to be unreliable.