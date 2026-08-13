# Design decisions

A running log of design choices, why they were made, and what evidence
supports them. Written as decisions are taken, not reconstructed
afterwards — the distinction matters, because a rationale invented after
seeing the results is not a rationale.

Each entry states the decision, the reasoning, and where applicable the
measurement that forced it.

---

## 1. Controlled experiment, not passive observation

**Decision.** The primary result comes from a controlled experiment in
which traffic composition is the independent variable. It does not come
from observing production logs.

**Why.** Passive observation of one site's access logs cannot separate
cause from circumstance: traffic mix, content, and load all vary together
and none of them are under the observer's control. Dozens of operators
have published their logs; the aggregate contribution of that genre to
understanding *mechanism* has been close to zero.

A controlled experiment answers a different and better question: holding
everything else fixed, what does changing the traffic mix do?

**Consequence.** The honeypot (`theslowshelf.org`) is not the experiment.
It exists solely to calibrate the workload model — see §2.

---

## 2. The honeypot calibrates; it does not measure

**Decision.** `theslowshelf.org` serves public domain literature and
records request-level logs. Its output is a set of parameters, not a
result.

**Why.** The weakest point of any synthetic workload is the question
"how do you know your fake agent behaves like a real one?". Without an
answer, the workload model rests on assumption and every number derived
from it inherits that weakness.

With the honeypot, each parameter of the agentic profile can be labelled
`measured` (from real crawler traffic), `literature` (from published
work, cited), or `assumed` (with the assumption stated). A reviewer can
see at a glance which is which.

**Instrumentation choice.** The nginx log format captures two fields
absent from standard formats:

- `$connection` and `$connection_requests` — the TCP connection
  identifier and per-connection request counter. These are the only way
  to measure **connection reuse**, one of the structural differences
  between human and agentic clients. Not logging them would make the
  most interesting parameter unrecoverable.
- `$http_signature_agent`, `$http_signature_input` — Web Bot Auth
  headers (RFC 9421), to distinguish cryptographically authenticated
  agents from those merely asserting a forgeable user-agent string.

**No rate limiting on 80/443.** Deliberate, and stated on the site's
`/about` page. Rate limiting a crawler means measuring one's own
configuration rather than the crawler's behaviour. Brute-force
protection applies to SSH only.

**Early finding (2026-08-12).** Within 24 hours the log contained at
least four behaviourally distinct classes of automated client:

1. Declared search crawlers (YandexBot first, via IndexNow; then Bingbot,
   Googlebot).
2. Infrastructure scanners (l9explore, zgrab, ModatScanner). Discovery
   appears to be via certificate transparency logs — they arrived before
   any search indexing.
3. Undeclared automation presenting as a browser. The single
   highest-volume client claimed Chrome 42 / Edge 12 (a 2015 user agent)
   and accounted for 72% of all traffic.
4. Probes for `/v1/models` — the OpenAI-compatible API path. Automated
   traffic *searching for exposed AI infrastructure*, a category none of
   the usual taxonomies accounts for.

The first genuine AI agent (`Claude-User/1.0`) appeared within 48 hours.

**Consequence for the workload model.** The human/agent binary is wrong.
The synthetic agentic profile is calibrated on the *declared crawler*
class, because that is the class whose access pattern drives the
hypothesised cache mechanism. The others are reported as a sensitivity
analysis. User-agent alone cannot classify traffic; the most robust
behavioural signal observed so far is 404s on unlinked paths — a client
requesting URLs that appear in no page and no sitemap is guessing, not
navigating, and no header can fake that away.

---

## 3. Open-loop load generation, without exception

**Decision.** k6 with the `constant-arrival-rate` executor. Never the
default executors.

**Why.** A closed-loop generator issues a request, waits for the
response, then issues the next. When the system under test stalls, the
generator therefore *stops generating load* — exactly at the moment when
real-world traffic would continue to arrive and queue. The result is
latency figures that look best precisely when the system is dying.
This is coordinated omission (Tene).

`constant-arrival-rate` maintains the arrival rate independently of
responses. When it cannot keep up it discards iterations and counts them
in `dropped_iterations`, which makes the failure visible rather than
silently optimistic.

**Consequence.** `dropped_iterations > 0` invalidates that data point.
It is a necessary condition — see §9 for why it is not sufficient.

---

## 4. Varnish as the cache tier

**Decision.** Varnish 7.5, with a deliberately minimal VCL.

**Why.** Zhang et al. (SoCC 2025) used Varnish. Using the same component
makes the first result a *replication* of theirs before it becomes an
extension — considerably more defensible than measuring something
adjacent with different tooling and claiming to have gone further.

**Minimal VCL, deliberately.** No cache-key normalisation, no grace, no
keep. Every heuristic added to the VCL is a variable that would need
justifying in the methodology. Cache behaviour must depend *only* on the
`Cache-Control` headers the application emits, so that the
cacheable/uncacheable distinction is a property of the workload rather
than of the configuration.

`grace = 0s` and `keep = 0s` specifically: stale-while-revalidate would
mask true misses, which are the quantity under measurement.

---

## 5. Cache size is expressed relative to working set — forced by a crash

**Decision.** `VARNISH_SIZE` is chosen as a fraction of the corpus size,
currently 32 MB against a 245 MB working set (13%). Competition for
cache space is created by **enlarging the corpus**, never by shrinking
storage below Varnish's operational range.

**Why — the evidence.** The initial configuration took the opposite
approach: a 50-book corpus (27 MB) with `VARNISH_SIZE=2m`, chosen to
force eviction pressure. Under load, Varnish child processes died
repeatedly:

```
Error: Child (6757) not responding to CLI, killed it.
Error: Child (6757) died signal=6 (core dumped)
Error: Child (6757) Panic at: Wed, 12 Aug 2026 21:39:58 GMT
PANIC REENTRANCY
```

Diagnosis was initially confounded: `docker stats` showed Varnish pinned
at a constant 92% CPU regardless of load, which resembles saturation.
It was not — Varnish had four cores available, so its ceiling was 400%.
A flat consumption independent of offered load is the signature of a
crash-restart cycle, confirmed by `MAIN.uptime` (429s) being far below
`MGT.uptime` (5219s), and by `SMA.s0.c_req = 0` — the storage allocator
had never been asked for a single object.

**Everything measured in that configuration was discarded.**

**Consequence.** The corpus was enlarged tenfold (50 → 495 books,
16,954 chapters, 245 MB) and cache size set to a realistic fraction.
This also addresses an independent reviewer objection about corpus scale:
1,981 objects is not a plausible stand-in for a real site's URL space.
It remains small relative to production, and that limitation is stated
in §11.

After the change, Varnish scaled linearly and cleanly across the sweep
(11% → 20% → 37% → 77% → 154% CPU for 500 → 8000 req/s), with sub-
millisecond p99 and zero failures.

---

## 6. Virtual users are sized by Little's law

**Decision.** `preAllocatedVUs ≈ RATE × 0.05`, `maxVUs ≈ RATE × 0.2`.

**Why — the evidence.** The initial sizing was `RATE × 2`, chosen only
to be "generous". By Little's law the concurrency a workload actually
requires is `λ × W`: at 1000 req/s with 1 ms responses, that is one to
two connections, not two thousand. Allocating thousands of VUs creates
concurrency that the arrival rate does not justify, and is the most
likely trigger of the Varnish panic described in §5.

The general principle: **a load generator parameter that is not derived
from the intended workload is itself an uncontrolled variable.**

---

## 7. Bounded thread pool as the resource under study

**Decision.** gunicorn, one process, `gthread` worker class, `THREADS`
threads, `BACKLOG` socket queue depth.

**Why.** Configured this way, the constrained resource is a bounded
thread pool with a request queue in front of it — structurally the same
mechanism as a WebLogic Work Manager, an Oracle Database Resource
Manager consumer group, or any other admission-controlled worker pool.
`THREADS` and `BACKLOG` are environment variables, so pool size is a
sweep parameter rather than a rebuild.

**What this is not.** It is not WebLogic. Python's GIL means the pool
behaves differently from a JVM thread pool under CPU-bound load. The
claim the project can support is that the *shape* of the saturation
curve, expressed in normalised terms, transfers — not that absolute
numbers do. See §8 and §11.

---

## 8. The workload must be I/O-bound — a constraint discovered by measurement

**Decision.** Sweeps must run against endpoints that block on the
database. The `/health` endpoint is for the null test only and must
never be used for a measurement sweep.

**Why — the evidence.** The null test against `/health` produced:

| rate (req/s) | app CPU | p99 |
|---|---|---|
| 100 | 9% | 2.6 ms |
| 200 | 21% | 2.3 ms |
| 400 | 31% | 1.8 ms |
| 800 | 59% | 13.3 ms |
| 1000 | 79% | 6205 ms |
| 2000 | 76% | — |
| 4000 | 74% | — |

Two things follow.

**First, the app saturates at ~80% CPU and goes no higher** despite
having two cores allocated. That is a single core: the GIL. `/health`
does no I/O, so it is pure Python overhead — CPU-bound.

**Second, and decisively for the design**: at 400 req/s with 1.8 ms
latency, Little's law gives 0.7 threads occupied out of 16. The pool
never fills. A sweep built on this endpoint would measure the limits of
the CPython interpreter, not thread pool saturation, and the central
thesis would not be testable at all.

A thread is occupied while it is **blocked**, not while it is computing.
The real endpoints — chapter retrieval, full-text search — block waiting
on PostgreSQL. There, threads accumulate while CPU stays low, which is
precisely the mechanism by which a production Work Manager exhausts.

**Consequence.** Before each sweep configuration, verify that
`ut_requests_inflight` is high while application CPU is low. If the
workload turns out CPU-bound, query cost must be increased until it is
not. This is a precondition, not an assumption.

**Incidental observation.** The transition from 800 to 1000 req/s
produced a p99 increase from 13.3 ms to 6205 ms — a 470× degradation
for a 25% load increase. This is the GIL knee, not the thread pool knee,
and is not the project's result. It does demonstrate that the apparatus
resolves non-linear collapse sharply when it occurs.

---

## 9. Null test criteria

**Decision.** A rate qualifies as clean only if all three hold:
`dropped_iterations == 0`, `http_req_failed < 0.1%`, and `p99 < 200 ms`.

**Why — the evidence.** An early run reported this line as passing:

```
rate=1000  dropped=0  p99=17697ms  fail=2.9%
```

Zero dropped iterations, so the generator kept up — but a 17-second p99
on a cached object with 3% failures describes a system already broken.
`dropped_iterations == 0` is necessary and not sufficient; it says the
generator was healthy, not that the target was.

**Operating rates derived (commit ee38d40, 16-core host).** Generator
ceiling 4000 req/s on cached content; application ceiling 800 req/s on
`/health`. Sweeps run at **400 req/s**. That margin is what licenses the
claim that the generator never influenced the measurement.

**One rate per invocation.** With chained scenarios,
`dropped_iterations` is a global counter and cannot be attributed to the
step that caused it. Separate invocations also let queues drain fully
between steps.

---

## 10. Metrics must not traverse the resource under study

**Decision.** Application metrics are served by
`prometheus_client.start_http_server` on a dedicated port and thread, not
by a Flask route.

**Why.** A `/metrics` route served by Flask occupies a thread from the
pool. When the pool saturates — the exact moment of interest — metrics
scraping queues or times out, and instrumentation goes dark precisely
when it is needed.

The general principle: **instrumentation must not contend for the
resource it is instrumenting.**

**Related.** Scrape interval is 1 s. Unusually high for a metrics system,
but the collapse is a transient; at 15 s it would appear as a single
point, and its dynamics are the object of study. PostgreSQL system views
are expensive to query, so that job scrapes at 5 s — the lower
resolution there is deliberate, to avoid perturbing the target.

**Percentiles are never computed by the metrics system.** Both
Prometheus-compatible stores and InfluxDB use fixed histogram buckets;
the resulting percentiles are approximate and, more importantly, **not
aggregatable** — the p99 of five runs cannot be obtained by averaging
their p99s. Latency percentiles are computed in analysis from raw k6
samples.

---

## 11. Known limitations

Stated here rather than discovered by a reviewer.

**Constant total rate.** The sweep varies traffic *composition* at fixed
total arrival rate. If total volume rose with agentic share, finding a
knee would demonstrate only that more load saturates a system — a result
from 1961. The claim being tested is that composition alone, at constant
volume, degrades the system.

**Ablation is required.** The agentic profile changes four things at
once: no client cache, deep traversal, no session, bursty arrivals. If
the system collapses, the mechanism is unidentified. Single-factor runs
must isolate each. Without them, "which mechanism?" has no answer.

**The GIL.** Python's thread pool is not a JVM thread pool. Absolute
numbers do not transfer to WebLogic. Mitigation: express results in
normalised terms (fraction of pool occupied, arrival rate over service
capacity), verify invariance across at least three pool sizes, and fit a
queueing model — it is the model parameters that generalise, not the
measurements.

**Corpus scale.** 16,954 objects against a production site's millions.
Cache dynamics at that scale are not self-evidently the same. Mitigated
by expressing cache size as a ratio to working set; the limitation
stands.

**No TLS, single host.** Deliberate, to reduce variance. Both make
opening a new connection much cheaper than in reality, which means the
penalty attributed to agentic connection behaviour is **underestimated**.
Conservative, but it must be stated.

**Single hardware platform.** Development on WSL2, final campaign on a
dedicated-CPU OCI instance. WSL2 introduces filesystem and scheduling
behaviour that is not representative; no measurement intended for
publication is taken there.

---

## 12. Reproducibility

**Everything is versioned, including sweep parameters.** `harness/.env`
is explicitly *not* gitignored despite the usual convention, because it
contains the experiment's configuration — pool sizes, CPU allocation,
cache size. Without it in version control, no run is reproducible. It
contains no secrets.

**Raw results are not versioned.** `harness/results/` is gitignored.
The repository holds what is needed to *reproduce*, not what was
*produced*. Reports worth keeping are promoted to `docs/runs/` by hand.

**Every run records provenance.** Commit hash, full configuration, RNG
seed, timestamp, core count. The corpus link graph uses a fixed seed, so
the same corpus produces the same graph on any machine.

**Configuration lives in the repository, never on the host.** An early
`server_tokens` directive created directly on the honeypot VM caused an
nginx conflict and, more importantly, meant the running configuration
diverged from the versioned one. Any such divergence makes the data
collected under it unreproducible.

---

## Changelog

- **2026-08-11** — Project scoped. Honeypot domain registered.
- **2026-08-12** — Honeypot live, 2,237 pages, submitted to Google/Bing
  and IndexNow. First traffic within hours; four classes of automated
  client observed. Harness stack built.
- **2026-08-12 evening** — Varnish panic under 2 MB cache. All
  measurements from that configuration discarded. Corpus enlarged 10×,
  cache resized to 13% of working set, VUs resized per Little's law.
- **2026-08-13 00:23 CEST** — Honeypot regenerated at 18,720 pages.
  **Discontinuity: any analysis of honeypot logs must treat this
  timestamp as a change point.**
- **2026-08-13** — Null test passes. Generator ceiling 4000 req/s
  (cached) and 800 req/s (application). GIL identified as the binding
  constraint on `/health`; I/O-bound workload established as a
  precondition for sweeps.