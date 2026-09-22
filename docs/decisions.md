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

The denominator of 245 MB is the corpus text in PostgreSQL. The effective
footprint of objects in the cache, measured later, is 438 MB -- see §18.
Fractions cited here must be reread with that denominator.

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

## 20. A load generator parameter drawn at random is an uncontrolled variable

**Decision.** Every source of randomness in the workload generator is
derived from the experiment seed. Nothing calls `Math.random()` for a
quantity that affects what is measured.

**Why — the evidence.** On 2026-08-19 a random per-run offset was added
to the traversal profile, to stop warm-up and measurement traversing the
same sequence. The intent was right. The implementation made the result
a lottery: because the index permutation is bijective modulo the corpus
size, only `offset mod 16954` mattered, and its value determined how much
of the measurement window overlapped the portion of corpus the warm-up
had just loaded.

Three consecutive repetitions on identical configuration, identical rate,
**exactly 7201 completed requests each**, zero dropped, system far below
saturation, produced h_A = **0.051, 0.287, 0.362**.

With the offset derived from the seed, the same three repetitions return
**0.667, 0.667, 0.667**.

**The general principle, now stated twice in this log.** §6 recorded that
a load generator parameter not derived from the intended workload is
itself an uncontrolled variable — there, virtual user counts. This is the
same error in a different place. Randomness that is not seeded is not
randomness in an experiment; it is an unmeasured input.

**Consequence.** All h_A measurements before 2026-08-26 are retracted.
See `findings.md`.

---

## 21. Configuration is per host, and every host is recalibrated

**Decision.** `harness/.env` is a local copy and is not versioned. The
repository holds `harness/env.<host-class>` — currently `env.x86-16` and
`env.arm6` — and each machine copies its own into place.

**Why.** §14 argued that sweep parameters must be versioned or no run is
reproducible, and versioned `.env` directly. That was right for one
machine and wrong for two: a single file cannot describe both a 16-thread
x86 host and a 6-core ARM host, and versioning it means each machine
overwrites the other's configuration at every pull.

**Recalibration is not optional.** Moving the harness to a new machine
invalidates every derived quantity. The order is fixed:

1. `null-test.sh` — is the generator the bottleneck on this hardware?
2. `calibrate.sh` — is the workload I/O-bound, and does the database
   scale with load rather than sitting flat at one saturated core?
3. `measure-model.sh` — h_H, h_A and C **on this machine**.

Only then may a sweep run. On the ARM host this took four attempts: the
first three CPU allocations each produced a component saturated at
exactly one core — Varnish at 100% across a sixteen-fold range of offered
load, then PostgreSQL at 100% across a sixteen-fold range. A component
whose consumption does not respond to load is not saturated by the
workload; it is confined by its allocation, and everything measured
behind it is measuring that confinement.

---

## 22. Database state must be controlled, not assumed

**Decision.** Origin capacity C is measured at the start of every
campaign, never carried over. `blks_hit` and `blks_read` are recorded
with each run.

**Why — the evidence.** Between 2026-08-15 and 2026-08-19 origin capacity
on the x86 host drifted from 74 to 92 req/s as PostgreSQL's working set
migrated into `shared_buffers` (blks_hit reaching 99.96%). A repeat of an
earlier campaign produced **no knee at all**, with hit ratios identical
to 1% — the cache was behaving the same, the database had become 24%
faster, and ρ had fallen from 0.98 to 0.75.

That campaign was initially read as a failed run. It is the origin of
§23.

---

## 23. The central question changed, and why

**From:** *at what fraction of automated traffic does an origin
collapse?*

**To:** *what does each traffic class cost, and what resource budget does
it deserve?*

**Three reasons, in order of weight.**

The threshold is not transferable. Across five campaigns the knee
occurred at α between 0.15 and 0.30 while pool occupancy at the knee
stayed between 89% and 97%. An operator cannot use someone else's α; they
can watch their own utilisation.

The second half of the chain is not a discovery. Saturation producing
non-linear latency growth is Pollaczek–Khinchine. Measuring it carefully
is worth doing; presenting it as a finding is not.

The question nobody is answering is the next one. Cloudflare shipped
Search/Agent/Training classification in July 2026 and answers *what kind
of traffic is this*. Zhang et al. (SoCC 2025) propose better eviction and
answer *what should the cache keep*. Neither answers *how should capacity
be divided between the classes you choose to serve* — and Radar's own
data show the current answer is wrong: the class with a human waiting in
real time receives a 403 in 34.5% of cases and a valid response in 25%,
while the batch class succeeds 64% of the time.

**What this preserves.** Everything measured. The mediator intervention
(§5, findings F/O3) demonstrates the mechanism the argument assumes; the
resource boundary becomes the condition under which a budget must be
set; the honeypot supplies the parameters. The apparatus did not change.
The question it answers did.

---

## 24. Retraction is part of the method, not a failure of it

Four claims have been withdrawn: a scan-versus-LRU inversion described as
counterintuitive when it is textbook; a working-set figure that was the
corpus size in PostgreSQL rather than the cached-object footprint; an
inferred hit ratio contradicted by direct measurement; and every h_A
value taken before the offset was made deterministic.

Each is recorded in `findings.md` with the evidence that overturned it.
None is deleted.

The reason is not modesty. A log containing only correct decisions is
indistinguishable from one written after the results were known, and a
reviewer who suspects that has no way to check. A log that records what
was believed, when, and what overturned it can be audited.

The practical rule that follows: **the moment a result is exciting is the
moment the novelty check is least likely to happen.** Both the
scan-inversion claim and the working-set error were made within minutes
of a good measurement. `contribution-boundary.md` exists for this.

---

## 25. A script that rewrites shared configuration must not carry
contradicting defaults

`budget.sh` writes BUDGET_LOW and BUDGET_WAIT into `.env` before each
measurement, so the application picks them up on restart. Its own default
for BUDGET_WAIT was 0.5s, contradicting the value in `env.*` and silently
overriding a fix made three days earlier in `app.py`.

Two campaigns ran with the wrong value before anyone noticed, on two
architectures, both showing the same signature: monotonic degradation as
the budget tightened, which is what a blocking acquire produces when the
waiting thread is itself a worker.

The fix is one line. The lesson is that configuration written by a script
is configuration, and must be reviewed as such — a default buried in a
runner silently defeated a correction made in the code it runs.

---

## 26. VU sizing according to Little's law applies only under saturation

**Decision.** `preAllocatedVUs = RATE × 2`, `maxVUs = RATE × 20`, capped
at 20,000. The virtual-user pool must be sized for the worst regime the
experiment intends to traverse, not the nominal regime.

**Why -- the evidence.** §6 fixed `maxVUs = RATE × 0.2` with a correct
argument: by Little's law, at 1 ms response time and 1000 req/s one or
two connections are needed, not two thousand. At the knee mean latency
exceeds two seconds and required concurrency is λ·W: with `maxVUs = 2λ`,
the pool is exhausted exactly at W = 2 s, after which k6 no longer
measures the system.

On 30 August, nine of twenty-five runs produced p99 values of 4377,
4380, 4386, 4293, 4341, 4347, 4354, 4439 and 4443 ms. All nine had
exactly `vus = 440` (the cap), 6,120–7,002 dropped iterations and 18%
failed requests. The near-constant value was a generator constant, not a
system property.

**Principle.** §6 says a generator parameter not derived from the load is
uncontrolled. §20 says unseeded randomness is an unmeasured input. Here:
**a parameter derived from the nominal regime is uncontrolled in the
saturated regime**, which is the only regime the experiment is meant to
observe.

**Operational consequence.** The validity gate in §27 repeats a run with
dropped iterations and retains its raw output as `invalid-*.json`. With
`GATE=0`, errors are recorded and not discarded, because beyond
saturation the errors **are** the signal.

---

## 27. A check that does not check is worse than no check

**Decision.** `nginx/router.conf` becomes `router.conf.tpl`, and
`split.sh` resolves the low-locality backend per configuration:
`varnish-h` for the shared reference and `varnish-l` for partitioned
runs. The resolved `router.active.conf` is not versioned. Each block
checks with `varnishstat` that allocated space matches the expected value
and prints it.

**Why -- the evidence.** The router always routed by user agent, without
a switch. With `r=shared`, the script changed only the sizes of the two
instances, so both classes still went to separate caches. The shared
reference never existed; campaign `split-20260830-123521` compared two
partitions.

The symptom was visible and read backwards: `hit_high` was 0.8272 across
five configurations, identical to the fourth decimal place and to α=0.
An invariant variable must first be shown to have varied in the mechanism,
not merely in its parameters.

**Corollary.** Every campaign includes the reference twice, at the start
and end. If the blocks differ, the campaign is invalid. On 30–31 August
the blocks produced 59.85 and 59.61 req/s, a 0.39% difference.

---

## 28. La durata della misura non si sceglie: si deriva dalla copertura del corpus
 
**Decisione.** `MEASURE` è fissato in modo che la classe a bassa località
attraversi **tutto** il corpus almeno una volta:
 
    MEASURE ≥ N_oggetti / (λ · α)
 
Sul banco attuale, con 16 954 capitoli, λ=110 e α=0,25, sono 617 s;
il protocollo usa **620 s**, con `WARMUP=300`. Nessuna misura di hit
ratio per classe è valida con una durata inferiore.
 
**Perché — l'evidenza.** Il 6 settembre `hit_bassa` variava da 0,285 a
0,172 al variare del solo warm-up, con configurazione altrimenti
identica e ripetizioni interne concordi allo 0,5%. Un parametro che non
dovrebbe entrare nel risultato lo spostava del 50%.
 
Due cause sovrapposte, entrambe di campionamento.
 
La prima: warm-up e misura sono **due invocazioni k6 separate**, quindi
`exec.scenario.iterationInTest` ripartiva da zero e la misura
ripercorreva la stessa sequenza appena percorsa. Ogni richiesta della
classe esaustiva era una seconda visita a un oggetto inserito
esattamente `WARMUP` secondi prima: `hit_bassa` misurava la **curva di
sopravvivenza della cache**, non il passaggio gratuito. Firma: 0,163 con
warm-up 180 s e 0,089 con 300 s a 128 MB, con il salto a 0,572 su 256 MB
proprio dove il tempo di residenza attraversa la durata del warm-up.
Corretto con `TRAV_SKIP`, che fa riprendere la traversata da dove il
warm-up l'ha lasciata.
 
La seconda, rimasta dopo la prima correzione: con `MEASURE=180` la
classe esaustiva emetteva 4 950 richieste su 16 954 oggetti, cioè
**campionava il 29% del corpus**. E il corpus è a coda pesante — mediana
9,5 KB, media 15,0 KB, deviazione standard 32,4 KB, massimo 1,9 MB, con
la deviazione doppia della media. Finestre diverse contengono oggetti di
stazza diversa ed esercitano pressioni diverse sulla cache. Un'escursione
del ±25% fra campioni al 29% non è un bug: è errore di campionamento con
un campione troppo piccolo.
 
Coprendo tutto il corpus l'escursione è scesa da 1,50× a 1,17×.
 
**Perché era invisibile.** L'ordine di traversata è deterministico dal
seed — correzione di §20, giusta e necessaria. Ma un bias deterministico
resta un bias: renderlo riproducibile l'ha reso invisibile. Tre
ripetizioni davano 0,161 / 0,163 / 0,162 e sembravano una misura solida.
**La riproducibilità non è accuratezza.**
 
**Una diagnosi intermedia, sbagliata e registrata.** Il 7 settembre è
stato ipotizzato che la causa fosse la correlazione fra l'ordine di
traversata e il rango di popolarità, dato che le due classi usavano la
stessa permutazione moltiplicativa. L'ipotesi tornava con i numeri. È
stata falsificata cambiando il moltiplicatore della classe esaustiva
(`permuteTrav`): l'effetto è rimasto identico. La modifica è stata
mantenuta perché la correlazione era comunque un difetto di disegno, ma
non era la causa.
 
**Il principio generale, ora enunciato quattro volte in questo log.**
§6: un parametro del generatore non derivato dal carico è una variabile
incontrollata. §20: la casualità non seminata è un input non misurato.
§26: un parametro derivato dal regime nominale è incontrollato nel
regime saturo. Qui: **una durata di misura scelta a mano è una
dimensione di campionamento non dichiarata.**
 
**Residuo dichiarato.** Anche a copertura piena `hit_bassa` dipende
ancora dal warm-up per ±8% (0,204 / 0,198 / 0,174 a 120 / 300 / 600 s),
in modo monotono e con ripetizioni interne allo 0,5%. È probabilmente
una proprietà reale del sistema — la cache ha memoria dello stato
precedente — non un artefatto. Il protocollo fissa il warm-up a 300 s e
il residuo è dichiarato come limite. **Il criterio per fermarsi non è
che il rumore sia zero: è che sia più piccolo dell'effetto da misurare.**
Gli effetti in gioco vanno da −3,8% a +321%.
 
---
 
## 29. Il protocollo di misura è fisso e ogni campagna lo dichiara
 
**Decisione.** Da 2026-09-07, ogni misura sul banco usa: `WARMUP=300`,
`MEASURE=620`, cancello di validità per run, riferimento condiviso
ripetuto a inizio e fine campagna, verifica con `varnishstat` che lo
spazio allocato coincida con quello atteso, e ogni parametro scritto nel
CSV insieme al risultato.
 
**Perché.** Cinque campagne sono state buttate per parametri non
dichiarati o non verificati: dimensione della cache non applicata,
riferimento inesistente, tetto dei virtual user, offset casuale, durata
di misura arbitraria. Il costo cumulativo è dell'ordine di quaranta ore
di macchina e otto giorni di calendario.
 
**Il cancello, e quando va spento.** Un run con iterazioni scartate o
tasso di errore sopra l'1% viene **ripetuto**, non mediato, e il suo
output grezzo conservato come `invalid-*.json`. Ma con `GATE=0` gli
errori vengono registrati invece che scartati: oltre la saturazione gli
errori **sono** il segnale, e il cancello butterebbe proprio i punti che
dimostrano il collasso. La scelta va dichiarata per campagna.
 
**Il controllo di deriva.** Il riferimento compare due volte, all'inizio
e alla fine. Se i due blocchi non coincidono entro il 4%, la campagna è
invalida e lo si sa **prima** di interpretarla. Sulle campagne del 7-8
settembre lo scarto osservato è stato sotto l'1%.
 
**Regola generale che ne discende.** Prima di interpretare
un'invarianza, dimostrare che la variabile indipendente è stata
effettivamente variata. Una grandezza che non si muove di una cifra su
cinque configurazioni non è quasi mai un fenomeno fisico: è una
variabile che non è stata variata. Vedi §27.

---

## 30. La capienza della cache si misura, non si deriva (chiude §18)

**Decisione.** La capienza della cache e' letta da `varnish_main_n_object`
con la cache piena, e riportata in **oggetti**, non in byte di corpus.

**Perche' — l'evidenza.** §18 chiedeva che l'impronta effettiva fosse
misurata invece che derivata, e la richiesta e' rimasta aperta per tre
settimane. Nel frattempo e' stata derivata comunque, e sbagliata: dividendo
128 MB per 192,4 KB si ottengono 681 oggetti, e su quel numero era stata
costruita un'intera spiegazione meccanicistica.

I 192,4 KB venivano da `classcost.py` e sono i **byte di lavoro a
PostgreSQL per richiesta** — corpo del capitolo, righe di indice, byte dei
capitoli correlati. Non sono la dimensione dell'oggetto HTTP che Varnish
memorizza. Due grandezze diverse, confuse da una divisione.

Misura diretta, 22 settembre 2026, cache satura (134 196 368 byte occupati,
21 360 liberi):

| grandezza | valore |
|---|---|
| oggetti in cache | **5 274** |
| oggetto medio | **24,8 KB** |
| frazione del corpus residente | **31,1%** di 16 954 |

La stima era sbagliata di **7,75 volte**, e con essa il rapporto fra
l'insieme di lavoro agentico e la capienza: 0,19× invece di 1,49×.

**Principio, ora enunciato cinque volte in questo log.** §6: un parametro
del generatore non derivato dal carico e' incontrollato. §20: la casualita'
non seminata e' un input non misurato. §26: un parametro derivato dal
regime nominale e' incontrollato nel regime saturo. §28: una durata scelta
a mano e' una dimensione di campionamento non dichiarata. Qui: **un numero
derivato per divisione e' un'assunzione travestita da misura, finche' non
si verifica cosa misura il divisore.**

---

## 31. Ogni parametro del generatore deve raggiungere il generatore

**Decisione.** `treclassi.sh` inoltra a k6 tutti i parametri della classe
agentica — `AGENT_MUL`, `AGENT_SCOPE`, `AGENT_SESSION`, `AGENT_SKEW` —
con i default letti da `workload.js`. Ogni directory di run scrive
`env.txt` con l'ambiente completo e l'hash del commit. Trenta secondi dopo
ogni lancio si verifica che la variabile manipolata compaia in `env.txt`.

**Perche' — l'evidenza.** L'invocazione di k6 inoltrava solo `MODEL`,
`ALPHA`, `BETA`, `RATE`, `DURATION`, `TARGET`, `TRAV_SKIP` e `OUTFILE`.
Qualunque altra variabile impostata dal driver restava fuori dal container.
La campagna di separazione working-set del 20 settembre e' girata con
`AGENT_MUL` al default, cioe' con la stessa permutazione della classe
umana, **rieseguendo per quattro ore la configurazione del 14 settembre**.

Il no-op e' rimasto invisibile ventiquattro ore perche' le directory di run
non registravano la propria configurazione. Conseguenza collaterale: per
tutti i run precedenti al 21 settembre la configurazione **non e'
recuperabile**, e per lo sweep di capienza del 10-11 settembre la dimensione
nominale della cache e' definitivamente persa. Quei punti restano
ordinabili solo per hit ratio umano osservato, ed e' il motivo per cui la
figura corrispondente resta in appendice.

**Corollario di §27** — un controllo che non controlla e' peggio di nessun
controllo: **un parametro che non viene registrato non e' stato
controllato, anche quando lo si e' impostato.**

---

## 32. La domanda centrale si e' stretta ancora (amend §23)

**Da:** *cosa costa ciascuna classe di traffico, e quale budget di risorse
merita?*

**A:** *il costo per richiesta di una classe e' abbastanza stabile, al
variare della composizione e dello stato condiviso, da poter essere
trattato come una proprieta' della classe?*

**Perche'.** La domanda di §23 presupponeva che «il costo di una classe»
fosse una grandezza. Lo sweep di `AGENT_SCOPE` mostra che non lo e': a
parita' di classe, volumi, cache e corpus, cambiando solo l'ampiezza
dell'insieme di lavoro, il costo marginale agentico passa da
−0,0477 ± 0,0054 a +0,4383 ± 0,0055 richieste all'origine per
richiesta. La domanda precedente chiedeva quale valore assegnare a una
variabile che cambia segno.

**Cosa conserva.** Tutto il misurato. La frontiera lavoro/latenza resta la
conseguenza decisionale; il costo marginale resta la grandezza; il
confronto fra classi resta il risultato. Cambia che non cerchiamo piu' *il*
costo di una classe, ma le condizioni sotto cui un costo fisso e' adeguato.

**Cosa NON rivendichiamo, e va scritto qui perche' e' la tentazione
principale.** Il modello che spiega il fenomeno — l'approssimazione a
tempo caratteristico — non e' nostro: Fagin 1977 per l'origine, Che et al.
2002 per la riscoperta e il nome, Fricker, Robert e Roberts 2012 per la
formalizzazione. Si adatta a tre dei nostri quattro punti con zero
parametri liberi, ed e' esattamente questo a renderlo credibile. Il
contributo non e' il modello: e' quale classe stia in quale regime, la
quantificazione della sovrapposizione come bias di misura, e il criterio
che ne discende.

---

## 33. Il conteggio delle ritrattazioni (amend §24)

§24 ne registrava quattro. Sono **dieci**. Le sei nuove, tutte fra il 19 e
il 22 settembre 2026, sono in `docs/retractions.md` con la storia completa:
il rinvio che dominerebbe il blocco; il traffico agentico che ridurrebbe il
lavoro all'origine; la separazione working-set che avrebbe falsificato la
critica; il confine di residenza a 681 oggetti; la dominanza di Pareto di B
su C; la previsione quantitativa del tempo caratteristico.

**Tutte e sei erano interpretazioni, nessuna era una misura.** Nessun dato
misurato e' mai stato smentito in questo progetto: sono cadute le
spiegazioni appoggiate sopra i dati. E tutte e sei sono state trovate prima
della pubblicazione, da controlli decisi da noi.

Tre delle sei hanno la stessa origine, ed e' la regola che §24 non aveva
ancora: **non ragionare sull'esito di un controllo prima di averlo
eseguito.** §24 dice che il momento in cui un risultato e' entusiasmante e'
quello in cui il controllo di novita' e' meno probabile. Questo e' il suo
gemello: il momento in cui un meccanismo e' elegante e' quello in cui la
verifica del meccanismo e' meno probabile.

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
- **2026-08-26** — Harness ported to Ampere ARM (6 Neoverse-N1 cores).
  Four CPU allocations required before one produced gradual saturation
  rather than a single confined core. Random per-run offset in the
  traversal profile identified as a lottery over cache overlap; all
  prior h_A measurements retracted.
- **2026-08-27** — Composition sweep on ARM: knee at α = 0.25, pool
  occupancy 89%. Across five campaigns on two architectures α varies
  0.15–0.30 while occupancy at the knee stays 89–97%. Invariance test
  passed.

- **2026-09-19/20** — Campagna di politiche al ginocchio, otto punti.
  Blocco e rinvio giacciono su un'unica curva convessa a pendenza monotona:
  la tesi che il rinvio domini il blocco e' ritirata. CPU PostgreSQL lineare
  in origin_rps, R² = 0,998.
- **2026-09-20** — Campagna di separazione working-set: **no-op**.
  `AGENT_MUL` non inoltrato a k6. Quattro ore perse, difetto invisibile
  perche' i run non registravano la configurazione. Vedi §31.
- **2026-09-21** — Capienza della cache misurata: 5 274 oggetti, oggetto
  medio 24,8 KB. La stima precedente era sbagliata di 7,75×. Vedi §30.
  Separazione working-set eseguita davvero: la sovrapposizione fra insiemi
  di lavoro vale 0,061 di hit ratio agentico e 0,71 req/s all'origine.
- **2026-09-21/22** — Sweep di `AGENT_SCOPE` a 0,02 / 0,06 / 0,20. Il costo
  marginale agentico passa da −0,048 a +0,438 richieste all'origine per
  richiesta. Previsione pre-registrata sul tempo caratteristico: fallita
  sul criterio quantitativo, confermata su direzione e ordinamento.
  Fase sperimentale chiusa.
- **2026-09-22** — Congelamento dell'evidenza: 72 run classificati in
  `docs/registry.csv`, sei ritrattazioni in `docs/retractions.md`,
  mappa dei claim in `docs/claims.md`. Letteratura verificata su fonti
  primarie. Vedi §32 e §33.
