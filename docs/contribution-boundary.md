# Contribution boundary

The one page to keep in front of you during every experiment. It exists
to prevent spending weeks measuring something already published.

Rule: no experiment is started unless it maps to a row in the third
column. If a result lands in the first column, it is cited, never
claimed.

---

## The thesis

> Web infrastructure classifies automated traffic by **identity** and
> decides by identity. But the classes have opposite resource footprints
> and opposite urgency: training crawling is high-volume with nobody
> waiting; agentic retrieval is low-volume with a person waiting in real
> time. The measurable consequence is that the web refuses most of the
> urgent traffic and serves most of the traffic that could wait. A policy
> organised around **cost and urgency** rather than identity requires
> knowing what each class actually costs — which nobody has measured.

Position relative to prior work:

| layer | question | who answered it |
|---|---|---|
| classification | *what kind of traffic is this?* | Cloudflare (Search/Agent/Training, July 2026) |
| cache policy | *what should the cache keep?* | Zhang et al., SoCC 2025 |
| **resource allocation** | **what should each class cost, and get?** | **open** |

Competing on classification would be futile: Cloudflare has global
telemetry, operator verification, and behavioural signals. Their taxonomy
is taken as **input**, not as a problem to re-solve.

---

## Column 1 — Not ours. Cite, never claim.

**AI/scan traffic has low locality and degrades cache efficiency.**
Zhang, Cai, Wildani, Klimovic, *Rethinking Web Cache Design for the AI
Era*, SoCC 2025, doi:10.1145/3772052.3772255. Measured: Varnish miss
ratio 17.3% → 32.2% at 25% AI traffic, → 51.8% at 100%.

**Cache degradation increases backend pressure.** Same paper, stated
explicitly (§3.1): bypassing AI traffic to the backend *"increases
pressure on application servers, storage systems, and databases"*.
Qualitative, not measured — see Column 3.

**Differentiated cache treatment for human and AI traffic is needed.**
Same paper: distinct tiers, tailored admission and eviction. The flag is
planted; we do not get to plant it again.

**Scan workloads are pathological for LRU below the working set and
benign above it.** ARC (Megiddo & Modha, FAST 2003), LIRS (Jiang & Zhang,
SIGMETRICS 2002), 2Q (Johnson & Shasha, VLDB 1994), SIEVE (NSDI 2024),
S3-FIFO (SOSP 2023). The inversion we observed at 512 MB is a direct
consequence of this and **was mistakenly described internally as a
finding on 2026-08-16; withdrawn the same day.**

**Hit ratio rises with cache size; miss-ratio curves are a standard
tool.** Mattson stack distances and successors. Our cache-size sweep
re-measures a textbook relation and is used as instrumentation.

**Queueing delay grows sharply as utilisation approaches capacity.**
Pollaczek–Khinchine; Little. Any non-linear latency growth near
saturation is expected. A measured threshold in a specific setting is a
data point, not a discovery.

**Traffic classification into Search / Agent / Training.** Cloudflare,
shipped July 2026, defaults changing 15 September 2026.

**Automated traffic exceeds human traffic.** Cloudflare Radar: 57.5% of
HTML requests. Note the denominator — HTML requests, not all requests,
not bytes, on a network covering roughly a fifth of the web.

**Scanning for exposed AI infrastructure** (`/v1/models`, MCP
transports). SANS ISC diary 33150; Knostic, July 2025. Our honeypot
observations are independent confirmation only.

---

## Column 2 — Ours. Measured, defensible, with stated limits.

**C1 — The web refuses the wrong traffic.**
Source: Cloudflare Radar API, `/radar/ai/bots/summary/RESPONSE_STATUS`
filtered by `crawlPurpose`, 28 days to 2026-08-22.

| | Training | Search | User Action |
|---|---|---|---|
| 200 | 63.7% | 53.9% | **25.0%** |
| 403 | 17.6% | 19.0% | **34.5%** |
| 404 | 5.5% | 10.3% | 18.6% |
| 429 | 2.6% | 4.1% | 6.7% |
| refused | 25.7% | 33.4% | **59.8%** |

The class with a human waiting in real time is blocked at twice the rate
of the batch class and succeeds one time in four. This is a direct
consequence of identity-based policy: the agent is caught in the net
built for the crawler.

*Status:* the data are Cloudflare's, public and freely queryable. The
**framing** — that this is a misallocation, and why — is ours. Anyone
could have run this query; nobody appears to have published the
comparison. To be re-verified before submission.

*Caveat:* 403 may also reflect deliberate publisher policy (paywalls,
licensing disputes), not only misclassification. The data cannot
distinguish intent. Say so.

**C2 — Class composition is re-proportioning fast.**
Radar `timeseries_groups/CRAWL_PURPOSE`, 52 weeks, weekly:

| class | Aug 2025 | Aug 2026 | change |
|---|---|---|---|
| User Action | 2.20% | 5.06% | **+130%** |
| Search | 9.03% | 17.24% | **+91%** |
| Training | 36.42% | 39.35% | +8% |
| Mixed Purpose | 51.68% | 36.67% | −29% |

*Caveat:* the Mixed decline is partly reclassification, not only traffic
shift. Cloudflare relabelled categories during this window. Use quarterly
views and state the discontinuity.

**C3 — Nobody revalidates.**
Radar: 304 responses are 0.53% of all AI bot requests. Honeypot: zero out
of 153,680. Every crawler re-downloads unchanged content in full.
Conditional requests (`If-None-Match`, `If-Modified-Since`) exist
precisely for this and are essentially unused. Read the Docs reported the
same qualitatively (73 TB in one month, no ETag support); we have the
measurement.

**C4 — Identity does not predict cost.**
Honeypot: AhrefsBot is the only operator sending Web Bot Auth signature
headers — cryptographically identified under the emerging IETF scheme —
and opens exactly 1.0 requests per TCP connection. GPTBot, unsigned,
reuses connections 686 times. A policy that admits the signed and rejects
the unsigned admits the expensive and rejects the cheap.

*Caveat:* one site, one signing operator, seven days. This establishes
the existence of a counterexample, not a statistical claim.

**C5 — Requests per TCP connection, per named operator.**
Not found in any prior measurement. GPTBot 686; Meta-ExternalAgent,
AhrefsBot, SemrushBot, Amazonbot all exactly 1.0; Googlebot 2.8. Meta
runs HTTP/2 and opens a fresh connection per request, which defeats the
protocol's purpose.

*Caveat:* nginx `$connection` is per-worker; the key used is (ip,
connection), so distinct connections are underestimated and
requests-per-connection overestimated. The direction of the error is
known: 1.0 is a floor no collision can produce spuriously.

**C6 — Selective versus exhaustive crawling, quantified.**
Googlebot: 17.3% site coverage, Gini 0.18. GPTBot, AhrefsBot, Amazonbot:
~100% coverage, Gini **0.00** — perfectly uniform, every page once.
Search crawling is constrained by expected per-page value; training
crawling is not. Gini is the discriminant.

*Caveat:* Googlebot's low coverage may reflect crawl budget on a
one-week-old domain with no backlinks, not policy. Distinguishable only
by continued collection.

**C7 — Cache contention is the causal mediator (F6).**
Intervention, not correlation: varying cache capacity 128/256/512 MB
moves the knee from α=0.30 to α=1.00 to absent. At α=0.50, changing only
cache size takes p99 from 3096 ms to 1 ms.

**C8 — The stability boundary is resource-based, not composition-based
(F7).** Across four campaigns the knee always occurred at 90–97% thread
pool occupancy, while the α at which that happened varied (0.15, 0.20,
0.30) as origin capacity drifted 74 → 92 req/s. **There is no universal
"AI percentage limit"; there is a resource-utilisation boundary.** An
operator cannot use someone else's α. They can watch their own ρ.

*How this was found:* by accident, when a repeat of an earlier campaign
produced no knee at identical hit ratios. The database had warmed. It is
recorded as a discovery, not hidden as a failed run.

**C9 — Per-class hit ratios are not invariant under composition (F2).**
High-locality class falls 0.829 → 0.764 as α goes 0 → 0.5; low-locality
class *rises* 0.330 → 0.392. Bidirectional, net positive. Consequence: a
mixture model parameterised with per-class hit ratios measured in
isolation misestimates the tolerable aggressive-class fraction by 2.3×,
in the optimistic direction.

*Note:* related to cache interference in the CPU shared-cache literature
(Intel CAT/RDT, Bubble-Up, Quasar). Search that literature before
claiming novelty. **Outstanding check.**

---

## Column 3 — Must still be demonstrated.

**D1 — The scan-resistance trade-off. Sign unknown.** *Highest priority.*

Scan-resistant eviction protects the human working set. But the scan
class free-rides on the shared cache: because it samples uniformly, it
hits whatever is resident regardless of *which* objects those are —
measured h_L ≈ S/W. Partitioning removes that free ride, and all of it
goes to the origin.

Computed on measured data at α=0.15, moving from shared LRU to full
reservation for the human class:

    human gain     221 req/s × 0.022  =  +4.9 req/s saved
    scan loss       39 req/s × 0.345  = -13.5 req/s added
    net                                  +8.6 req/s

Origin load 68.4 → 77.0. With C ≈ 88, utilisation moves 0.78 → 0.88:
**from safe to the edge of the knee.**

But substituting the harmonic model for h_H instead of the measured value
reverses the sign (68.4 → 66.8). The model error exceeds the effect.
**The sign cannot be predicted; it must be measured.** That is exactly
what makes the experiment worth running.

Three outcomes, all publishable:
- *paradox exists* → Zhang's proposal solves a cache problem and creates
  an origin problem; admission control is a required complement
- *paradox absent* → partitioning improves both; Zhang is right and
  extended
- *interior optimum* → a Pareto frontier and a quantified policy choice.
  Richest outcome.

**D2 — Optimal reserve fraction.** If a trade-off exists, vary the
reserved share r and locate the optimum for total origin load, which will
differ from the optimum for human latency.

**D3 — Origin-side per-class admission control.** Cache partitioning is
insufficient: the exhaustive stream reaches the origin regardless. Give
each class a bounded thread/connection budget and measure whether the
interactive class recovers while the batch class barely notices. The
prediction is asymmetric — the crawler was never thread-limited, it was
limited by the contention it created. If it holds, the conflict is
apparent and nobody needs blocking.

**D4 — Generality.** Does the shape survive different pool sizes and a
different bottleneck (DB CPU vs connection pool vs downstream service)?
Normalised curves should collapse onto one.

**D5 — Realistic agent workload.** The honeypot sees agentic traffic at
0.18% of AI traffic against 5.06% globally — a factor of 28. Agentic
traffic is **concentrated, not rare**: it goes where people ask
questions. Volume comes from Radar; behaviour must be generated by
querying commercial assistants against the site.

**D6 — Is C9 already published under other terminology?** Search the CPU
shared-cache contention literature before claiming it.

---

## Discipline

- Every claim in Column 2 carries its caveat in the paper. The caveats
  are not weaknesses; unstated, they become referee objections.
- "To our knowledge" on every novelty claim. A novelty search is never
  complete.
- Radar figures are re-verified before submission — the API is live and
  Cloudflare reclassifies.
- Absolute numbers from the testbed (α thresholds, req/s capacities) are
  properties of one machine. Only normalised relations are claimed to
  transfer.
- Nothing is deleted from this document. Withdrawn claims move to the
  record below.

## Withdrawn

- **2026-08-16** — "The α=1 inversion at large cache is counterintuitive
  and unreported." It is textbook scan-vs-LRU behaviour and the reason
  scan-resistant policies exist.
- **2026-08-16** — "Cache larger than the working set." The 245 MB figure
  was corpus text in PostgreSQL, not cached-object footprint, which was
  later measured at 438 MB. Cache sizes are now stated as configured
  capacity.
- **2026-08-19** — The inferred in-mixture low-locality hit ratio of
  ≈0.13. Direct per-class measurement gives 0.33–0.39 and the effect runs
  opposite to the inference.
- **2026-08-21** — "The web cannot distinguish human from agent traffic."
  Cloudflare shipped exactly that capability in July 2026. The defensible
  claim is that knowing the class is not enough without knowing its cost.