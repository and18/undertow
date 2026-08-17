# Design decisions

A running log of design choices, why they were made, and what evidence
supports them. Written as decisions are taken, not reconstructed
afterwards — a rationale invented after seeing the results is not a
rationale.

Failures are recorded alongside choices. A log containing only correct
decisions is indistinguishable from one written after the fact.

---

## 1. Controlled experiment, not passive observation

**Decision.** The primary result comes from a controlled experiment in
which traffic *composition* is the independent variable. It does not come
from observing production logs.

**Why.** Passive observation of one site's access logs cannot separate
cause from circumstance: traffic mix, content, and load vary together and
none are under the observer's control. Many operators have published
their logs; the contribution of that genre to understanding *mechanism*
has been close to zero.

A controlled experiment answers a better question: holding everything
else fixed, what does changing the traffic mix do?

**Consequence.** The honeypot (`theslowshelf.org`) is not the experiment.
It calibrates the workload model — see §2.

---

## 2. The honeypot calibrates; it does not measure

**Decision.** `theslowshelf.org` serves public domain literature and
records request-level logs. Its output is a set of parameters, not a
result.

**Why.** The weakest point of any synthetic workload is the question
"how do you know your fake agent behaves like a real one?". Without an
answer the model rests on assumption, and every number derived from it
inherits that weakness.

With the honeypot, each parameter of the agentic profile can be labelled
`measured`, `literature` (cited), or `assumed` (stated). A reviewer can
see at a glance which is which.

**Instrumentation.** The nginx log format captures two fields absent from
standard formats:

- `$connection` and `$connection_requests` — TCP connection identifier
  and per-connection request counter. The only way to measure
  **connection reuse**. Not logging them would make the single most
  discriminating parameter unrecoverable.
- `$http_signature_agent`, `$http_signature_input` — Web Bot Auth headers
  (RFC 9421), to distinguish cryptographically authenticated agents from
  those merely asserting a forgeable user-agent string.

**No rate limiting on 80/443.** Deliberate, and disclosed on the site's
`/about` page. Rate limiting a crawler means measuring one's own
configuration rather than the crawler's behaviour. Brute-force protection
applies to SSH only.

### 2.1 Findings to date

**Four behaviourally distinct classes appeared within 24 hours**, before
any declared AI crawler:

1. Declared search crawlers — YandexBot first (via IndexNow), then
   Bingbot and Googlebot.
2. Infrastructure scanners — l9explore, zgrab, ModatScanner. Discovery
   appears to be via certificate transparency logs: they arrived before
   any search indexing.
3. Undeclared automation presenting as a browser. One client claiming
   Chrome 42 / Edge 12 (a 2015 user agent) accounted for 72% of traffic
   on day one.
4. Probes for `/v1/models`, `/mcp`, `/api/mcp`, `/sse` — the
   OpenAI-compatible API path and Model Context Protocol transports.
   **Automated traffic searching for exposed AI infrastructure.** This
   category appears in none of the published taxonomies and did not
   exist eighteen months ago.

The first declared AI agent (`Claude-User/1.0`, a retrieval fetcher
rather than a training crawler) appeared within 48 hours.

**Connection reuse: a natural experiment.** Same site, same content, same
hours, two operators with opposite connection behaviour:

| | Googlebot | Meta (`meta-externalagent/1.1`) |
|---|---|---|
| source addresses | 3 | ~30 (single /24) |
| max requests per connection | **339** | **1** |
| requests / distinct URLs | 1.09 | 1.00 |
| share of total traffic | 25% | **70%** |

Meta opens a fresh TCP connection for every request, spread across
roughly thirty addresses. Google reuses one connection for hundreds.
Both deduplicate near-perfectly (ratio ≈ 1.0); an earlier OVH-hosted
crawler with a forged user agent sat at 2.0 — it fetched every page twice.

This bears directly on the hypothesis: thirty addresses opening fresh
connections defeat edge affinity by construction, and per-request origin
cost is maximised. It is the mechanism under study, observed in the wild,
with numbers.

**Consequence for the workload model.** The human/agent binary is wrong.
The synthetic agentic profile is calibrated on the *declared crawler*
class, because that class drives the hypothesised cache mechanism; the
others become a sensitivity analysis. User-agent alone cannot classify
traffic — on day one the highest-volume automated client presented as a
consumer browser. The most robust behavioural signal is 404s on unlinked
paths: a client requesting URLs that appear in no page and no sitemap is
guessing, not navigating, and no header can fake that away.

**Collection window.** Minimum one week before parameter extraction. Two
operators dominating the first days is not a representative sample.

---

## 3. Open-loop load generation, without exception

**Decision.** k6 with `constant-arrival-rate`. Never the default
executors.

**Why.** A closed-loop generator issues a request, waits for the
response, then issues the next. When the system stalls it therefore
*stops generating load* — precisely when real traffic would continue
arriving and queueing. Latency then looks best exactly when the system is
dying. This is coordinated omission (Tene).

`constant-arrival-rate` maintains arrival rate independently of
responses; when it cannot, it discards iterations and counts them in
`dropped_iterations`, making the failure visible rather than silently
optimistic.

**One rate per invocation.** With chained scenarios,
`dropped_iterations` is a global counter and cannot be attributed to the
step that caused it. Separate invocations also let queues drain between
steps.

---

## 4. Varnish as the cache tier

**Decision.** Varnish 7.5, deliberately minimal VCL.

**Why.** Zhang et al. (SoCC 2025) used Varnish. Using the same component
makes the first result a *replication* of theirs before it becomes an
extension — considerably more defensible than measuring something
adjacent with different tooling and claiming to have gone further.

**Minimal VCL, deliberately.** No cache-key normalisation, no grace, no
keep. Every heuristic is a variable requiring justification. Cache
behaviour must depend *only* on the `Cache-Control` headers the
application emits, so the cacheable/uncacheable distinction is a property
of the workload rather than of the configuration.

`grace = 0s` and `keep = 0s` specifically: stale-while-revalidate would
mask true misses, the quantity under measurement.

---

## 5. Cache size relative to working set — forced by a crash

**Decision.** `VARNISH_SIZE` is a fraction of corpus size: 32 MB against
a 245 MB working set (13%). Cache pressure is created by **enlarging the
corpus**, never by shrinking storage below Varnish's operational range.

**Why — the evidence.** The initial configuration did the opposite: a
50-book corpus (27 MB) with `VARNISH_SIZE=2m`. Under load, Varnish child
processes died repeatedly:

```
Error: Child (6757) not responding to CLI, killed it.
Error: Child (6757) died signal=6 (core dumped)
PANIC REENTRANCY
```

Diagnosis was initially confounded: `docker stats` showed Varnish pinned
at a constant 92% CPU regardless of load, resembling saturation. It was
not — Varnish had four cores, so its ceiling was 400%. **Flat consumption
independent of offered load is the signature of a crash-restart cycle**,
confirmed by `MAIN.uptime` (429 s) far below `MGT.uptime` (5219 s), and by
`SMA.s0.c_req = 0` — the storage allocator had never been asked for a
single object.

**Every measurement taken in that configuration was discarded.**

**Consequence.** Corpus enlarged tenfold (50 → 495 books, 16,954
chapters, 245 MB); cache set to a realistic fraction. This also addresses
an independent objection about corpus scale. After the change Varnish
scaled linearly and cleanly (11% → 20% → 37% → 77% → 154% CPU for
500 → 8000 req/s) with sub-millisecond p99 and zero failures.

---

## 6. Virtual users sized by Little's law

**Decision.** `preAllocatedVUs ≈ RATE × 0.05`, `maxVUs ≈ RATE × 0.2`.

**Why — the evidence.** Initial sizing was `RATE × 2`, chosen only to be
"generous". By Little's law, required concurrency is `λ × W`: at 1000
req/s with 1 ms responses that is one to two connections, not two
thousand. Allocating thousands creates concurrency the arrival rate does
not justify, and is the most likely trigger of the Varnish panic in §5.

**Principle: a load generator parameter not derived from the intended
workload is itself an uncontrolled variable.**

---

## 7. Bounded thread pool as the resource under study

**Decision.** gunicorn, one process, `gthread` worker class, `THREADS`
threads, `BACKLOG` socket queue depth.

**Why.** The constrained resource is a bounded thread pool with a request
queue in front — structurally the same mechanism as a WebLogic Work
Manager or an Oracle Resource Manager consumer group. Both are
environment variables, so pool size is a sweep parameter rather than a
rebuild.

**What this is not.** It is not WebLogic. Python's GIL means the pool
behaves differently under CPU-bound load. The supportable claim is that
the *shape* of the saturation curve, expressed in normalised terms,
transfers — not that absolute numbers do.

---

## 8. The workload must be I/O-bound — discovered by measurement

**Decision.** Sweeps run against endpoints that block on the database.
`/health` is for the null test only and must never carry a measurement
sweep.

**Why — the evidence.** The null test against `/health`:

| rate (req/s) | app CPU | p99 |
|---|---|---|
| 100 | 9% | 2.6 ms |
| 400 | 31% | 1.8 ms |
| 800 | 59% | 13.3 ms |
| 1000 | 79% | 6205 ms |
| 4000 | 74% | — |

The app saturates at ~80% CPU and rises no further despite two allocated
cores. That is one core: the GIL. And at 400 req/s with 1.8 ms latency,
Little's law gives 0.7 threads occupied out of 16 — the pool never fills.
A sweep on this endpoint would measure CPython's limits, not thread pool
saturation, and the central thesis would be untestable.

**A thread is occupied while it is *blocked*, not while it computes.**
The real endpoints block on PostgreSQL; threads accumulate while CPU
stays low, which is how a production Work Manager exhausts.

**Incidental.** The 800 → 1000 req/s transition produced p99 from 13.3 ms
to 6205 ms: a 470× degradation for 25% more load. That is the GIL knee,
not the project's result, but it demonstrates the apparatus resolves
non-linear collapse sharply.

---

## 9. Endpoint cost calibration

**Decision.** Per-request cost is a controlled constant of the
experiment, measured cold and documented.

**Search (uncacheable).** Full-text search cost depends on how many
chapters contain the term: 83 ms for "whale", 1330 ms for "night" — a
factor of 16. Freely chosen terms would make per-request cost an
**uncontrolled variable**, and if the human and agentic profiles sampled
terms differently, traffic composition and query cost would be
confounded.

The variance is intrinsic to full-text ranking (`ts_rank` must be
computed over every match) and cannot be removed by rewriting the query.
It is controlled by selecting terms in a measured band:
`tools/pick_terms.py` measures ~170 candidates and selects 40 within a
target range. Result: **103–198 ms, max/min ratio 1.93×**, written to
`harness/profiles/search-terms.txt` and versioned.

One genuine query bug was found along the way: `ts_headline` was computed
over all matching rows *before* `ORDER BY … LIMIT`. Moving it to an outer
query over the 25 winners cut worst-case cost roughly threefold.

**Chapter (cacheable).** A single primary-key lookup cost ~1.5 ms. At
that cost, Little's law puts pool saturation beyond 2,600 req/s at the
origin — a rate the GIL does not permit reaching. **The experiment could
not have produced its own phenomenon.**

The endpoint was made to do what a real CMS page does: content, book
metadata, table of contents, and excerpt generation for related chapters
(`LINKS_PER_CHAPTER` raised 4 → 12). Cost is now **25.8 ms** (range
17.0–39.6, n = 25, cold cache). This is not inflated work — a cacheable
page is expensive to generate, which is why it is cached.

**Why pushing work into PostgreSQL is the correct lever.** Work inside
Postgres blocks the Python thread *without* consuming the GIL: the thread
waits on a socket — occupied but idle. Both realistic and exactly the
mechanism required.

**Measure cold.** Cache-warm measurement returns Varnish's latency, not
the application's. This error was made once: a chapter appeared to cost
1 ms and to have 4 related items after the corpus had been reloaded with
12 — the response was a cache hit predating the reload.

---

## 10. Calibration result: the pool is an admission valve, not the bottleneck

**Measurement** (commit 2fc4c1f, 16-core host, `THREADS=16`, 60 s per
step, cold cache at start):

Search endpoint, uncacheable:

| rate | pool used | app CPU | db CPU | p99 |
|---|---|---|---|---|
| 50 | 31% | 5.9% | 91% | 143 ms |
| 100 | 84% | 5.8% | 190% | 1362 ms |
| 200 | 100% | 6.4% | 194% | 6303 ms |

Chapter endpoint, cacheable:

| rate | pool used | app CPU | p99 |
|---|---|---|---|
| 400 | 52% | 61% | 205 ms |
| 800 | 98% | 42% | 2402 ms |

**The I/O-bound precondition is satisfied**: pool occupancy goes 31% →
100% while application CPU stays near 6%. Threads are blocked on
PostgreSQL, not computing.

**But the causal chain is not what the design assumed.** Database CPU
saturates at ~195% of its two allocated cores. The chain is:

> database saturates → threads stay blocked → pool fills → queue grows →
> p99 explodes

The thread pool is not the *cause* of collapse. It is the **valve that
determines how much work may accumulate upstream of a saturated
resource** — which is precisely admission control, the mechanism at the
centre of the traffic-class isolation thesis.

That this emerged from measurement rather than from the design makes it
considerably stronger. It also reframes the contribution: the work is not
about thread pools, it is about **what happens at an origin whose slowest
tier saturates, and what the queue in front of it does**.

**Derived operating points.** Chapter endpoint: origin saturates near
620 req/s, so a total rate of **800 req/s** places the knee inside the
composition sweep (a human profile at 90% hit ratio sends 80 req/s to
origin; an agentic profile at 20% sends 640). Search endpoint: operating
range **100–150 req/s**.

---

## 11. Open issues to resolve before the sweeps

Identified by reviewing the calibration data. None invalidates the
apparatus; all must be fixed in the workload design.

**No repetitions.** Every point is a single measurement. Confidence
intervals require ≥5 repetitions per point.

**`DB_POOL_MAX` equals `THREADS`.** Both are 16, so every thread can hold
a connection and the DB pool never blocks — the two cannot be
distinguished. They must be decoupled to attribute saturation correctly.

**Chapter endpoint approaches the GIL.** App CPU reaches 61% at 400 req/s.
The chapter knee may be partly an interpreter artefact. It must be shown
to vanish under normalisation across pool sizes.

**Cache state carries across steps.** Varnish is flushed only at the start
of a calibration run. Every sweep step must begin from a cold cache, or
eviction history from the previous step contaminates the next.

**Uniform random sampling confounds hit ratio with test duration.** At
800 req/s for 60 s, 48,000 requests over 16,954 chapters means each page
is requested ~3 times; at 50 req/s almost all requests are unique.
Observed hit ratio rose 21% → 76% purely from this arithmetic. In the
real design, hit ratio must follow from the *access model* — Zipf over
popularity for the human profile, graph traversal for the agentic one —
never from sample size.

**Resource allocation is arbitrary.** Varnish 4 cores, app 2, db 2 was
chosen by hand. It must either be justified or swept.

---

## 12. Metrics must not traverse the resource under study

**Decision.** Application metrics are served by
`prometheus_client.start_http_server` on a dedicated port and thread, not
by a Flask route.

**Why.** A `/metrics` route served by Flask occupies a pool thread. When
the pool saturates — the exact moment of interest — scraping queues or
times out, and instrumentation goes dark precisely when needed.

**Principle: instrumentation must not contend for the resource it is
instrumenting.**

**Scrape interval 1 s.** Unusually high, but the collapse is a transient;
at 15 s it would appear as a single point, and its dynamics are the object
of study. PostgreSQL system views are expensive, so that job scrapes at
5 s — the lower resolution there is deliberate.

**Percentiles are never computed by the metrics system.** Fixed histogram
buckets give approximate and, more importantly, **non-aggregatable**
percentiles: the p99 of five runs is not the average of their p99s.
Latency percentiles are computed in analysis from raw k6 samples.

---

## 13. Known limitations

Stated here rather than discovered by a reviewer.

**Constant total rate.** The sweep varies composition at fixed total
arrival rate. If volume rose with agentic share, a knee would demonstrate
only that more load saturates a system — a result from 1961.

**Ablation is required.** The agentic profile changes four things at
once: no client cache, deep traversal, no session, bursty arrivals. If
the system collapses, the mechanism is unidentified. Single-factor runs
must isolate each.

**The GIL.** Python's thread pool is not a JVM thread pool. Absolute
numbers do not transfer. Mitigation: normalised reporting, invariance
verified across ≥3 pool sizes, and a fitted queueing model — the model
parameters generalise where the measurements do not.

**Database saturation is CPU-bound here.** `ts_rank` and `ts_headline`
are compute-heavy. Many production databases saturate on I/O instead. The
queueing behaviour upstream is the same; the resource is not.

**Corpus scale.** 16,954 objects against a production site's millions.
Cache dynamics at that scale are not self-evidently identical. Mitigated
by expressing cache size as a ratio to working set; the limitation stands.

**No TLS, single host.** Deliberate, to reduce variance. Both make
opening a connection much cheaper than reality, so the penalty attributed
to agentic connection behaviour is **underestimated**. Conservative, but
it must be stated — particularly given the Meta observation in §2.1,
where every request opens a fresh connection.

**Single hardware platform.** Development on WSL2, final campaign on a
dedicated-CPU OCI instance. No measurement intended for publication is
taken on WSL2.

---

## 14. Reproducibility

**Sweep parameters are versioned.** `harness/.env` is explicitly *not*
gitignored despite convention: it holds pool sizes, CPU allocation and
cache size. Without it in version control no run is reproducible. It
contains no secrets.

**Raw results are not versioned.** `harness/results/` is gitignored. The
repository holds what is needed to *reproduce*, not what was *produced*.
Reports worth keeping are promoted to `docs/runs/` by hand.

**Every run records provenance.** Commit hash, full configuration, RNG
seed, timestamp, core count. The corpus link graph uses a fixed seed, so
the same corpus produces the same graph on any machine.

**Configuration lives in the repository, never on the host.** An early
`server_tokens` directive created directly on the honeypot VM caused an
nginx conflict and, more importantly, meant the running configuration
diverged from the versioned one. Any such divergence makes the data
collected under it unreproducible.

**Source files are bind-mounted during development.** Three separate
debugging sessions were lost to containers running stale code after
`docker compose build` failed to rebuild a dependent service. Mounting
`app.py` and `load_corpus.py` removes the ambiguity. Mounts are removed
before the final campaign so the image is self-contained.

---

## 15. Knee definition — pre-registered

Fixed before the sweep, deliberately: a threshold chosen after seeing the
data is chosen, however unconsciously, to make the result work.

    K = inf{ alpha : p99(alpha) > 10 * p99(alpha=0) }

Relative rather than absolute, so it transfers to systems with different
baseline latency. Ten-fold degradation is far outside normal operating
variance (measured run-to-run spread at alpha=0 is under 20%) and well
below the collapse observed in calibration (27x).

Secondary criteria, reported alongside: request completion ratio below
99%, and pool occupancy above 90%.

If the three criteria disagree, all three are reported and the
disagreement discussed. None is selected after the fact.

Operating point derived from measurement (commit 18db2f2, cache 128m):
h_H = 0.830, h_A = 0.493, C = 74 req/s, r = 2.98, lambda_total = 260 req/s.
Predicted knee at alpha = 0.35, with u_0 = 0.60.

---

## 16. Knee reported as a band, not a point (amends §15)

At the transition the outcome is probabilistic: at α = 0.15 three of five
runs exceeded the pre-registered threshold and two did not. A single α is
therefore not well defined. The criterion is reported as K50 and K90 —
first α at which 50% and 90% of runs exceed the threshold — with the
interval between them as the unstable band. The original single-threshold
pre-registration stands as made; this refines the reporting, not the
criterion.

---

## 17. Identity is never inferred from behaviour

Traffic is assigned to a tier by the strongest available evidence:
cryptographic (Web Bot Auth), provider-attributed (published IP range,
reverse DNS), declared (user-agent), behavioural, unknown. Behavioural
features construct workload classes; they never assign operator identity.

Forced by measurement: AhrefsBot is the only signed operator on the
honeypot and opens one connection per request, while GPTBot is unsigned
and reuses connections 217 times. Identity and cost are independent.

---

## 18. Cache size is stated as a ratio, and the denominator must be named

"Cache larger than the working set" is meaningless without specifying
which working set. The 245 MB figure used throughout is the corpus text
size in PostgreSQL; what Varnish stores is gzipped JSON responses, whose
aggregate footprint has not been measured directly. 256 MB exceeds the
nominal figure and still exhibits contention; 512 MB does not.

Every statement about cache sizing must name its denominator, and the
effective footprint must be measured rather than derived.

---

## 19. Correlations along a driven chain identify nothing

Where a single independent variable drives every link of a causal chain,
every correlation along that chain approaches unity by construction.
Reporting them as evidence of mechanism would be circular.

Mechanism is established only by intervening on the hypothesised mediator
and observing whether the effect disappears. This is the design of F6 and
should be the design of any subsequent mechanistic claim in this project.

---

## Changelog

- **2026-08-11** — Project scoped. Honeypot domain registered.
- **2026-08-12** — Honeypot live, 2,237 pages, submitted to Google/Bing
  and IndexNow. First traffic within hours; four classes of automated
  client observed. Harness stack built.
- **2026-08-12 evening** — Varnish panic under 2 MB cache. All
  measurements discarded. Corpus enlarged 10×, cache resized to 13% of
  working set, VUs resized per Little's law.
- **2026-08-13 00:23 CEST** — Honeypot regenerated at 18,720 pages.
  **Discontinuity: analysis of honeypot logs must treat this timestamp as
  a change point.**
- **2026-08-13** — Null test passes. Generator ceiling 4000 req/s
  (cached), 800 req/s (application). GIL identified as the binding
  constraint on `/health`; I/O-bound workload established as a
  precondition.
- **2026-08-14** — Endpoint costs calibrated: chapter 25.8 ms, search
  161.7 ms (40 terms, 1.93× spread). I/O-bound precondition satisfied on
  both endpoints. **Database identified as the downstream bottleneck and
  the thread pool as the admission valve** — a reframing of the
  contribution. Phase 2 (harness) closed.
- **2026-08-14** — Honeypot: Googlebot vs Meta connection-reuse contrast
  recorded (339 vs 1 requests per connection). Probes for MCP transports
  observed. Collection continues; parameter extraction after ≥1 week.
- **2026-08-15/16** — First composition sweep, 70 measurements. Knee at
  α = 0.15, sharp (5.2× p99 for a 5-point change at constant total rate).
  Prediction of α = 0.35 failed by 2.3×; cause identified as isolated
  vs in-mixture hit ratio measurement. Model structure validated after
  reparameterisation. Variance explosion at the transition observed
  (3.4× spread across repetitions at α = 0.15, against 1.1× elsewhere).
  See docs/findings.md.
- **2026-08-16** — Mediator intervention (45 measurements, 3 cache sizes,
  α to 1.00). Knee at α=0.30 with 128 MB, α=1.00 with 256 MB, absent with
  512 MB. At α=0.50, cache size alone moves p99 from 3096 ms to 1 ms.
  Cost inverts at large cache: low-locality reaches hit=1.000 against
  Zipf's 0.980. Offered and served origin load agree to 4–7% below
  saturation and diverge above it, with served pinned at 74–76 req/s,
  consistent with the independently measured capacity. Cache contention
  strongly supported as the causal mediator. See docs/findings.md §F6.