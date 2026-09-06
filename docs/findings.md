# Findings

Results as obtained, including predictions that failed and diagnoses
later retracted. Companion to `decisions.md` (why things were done),
`contribution-boundary.md` (what is ours to claim) and `setup.md` (how to
rebuild the apparatus).

Three sources, three roles:

| source | establishes | scale |
|---|---|---|
| **Cloudflare Radar** | that the problem is real and mishandled | global |
| **controlled testbed** | why it happens, and that it can be fixed | one origin |
| **honeypot** | that the behavioural classes are not invented | one site |

**Terminology.** The testbed's two synthetic classes are named for what
distinguishes them: **high-locality** (Zipf(1) over popularity, standing
in for human browsing) and **low-locality** (uniform non-repeating
traversal, standing in for exhaustive crawling). α is the low-locality
fraction, not the agentic fraction — only one of nine workload parameters
is varied, and the ablations that would justify the stronger word have
not been done.

**Two hosts.** x86 (Ryzen AI 7 350, 8 physical cores with SMT, WSL2) for
12–23 August; ARM (Ampere Neoverse-N1, 6 physical cores, no SMT, Oracle
Cloud) from 26 August. Absolute numbers are host properties. Only
normalised relations are claimed to transfer, and O5 is what earns that.

---

# Part 1 — Global scale (Cloudflare Radar)

Radar API, 28-day window to 2026-08-22. Cloudflare's network covers
roughly a fifth of the web; bot figures are shares of HTML requests, not
of all requests and not of bytes. Cloudflare sells bot management — but
these are its own measurements, published openly, and the comparisons
below are ones it has not itself drawn.

## G1. The web refuses the wrong traffic

Response codes by declared crawl purpose:

| | **Training** | **Search** | **User Action** |
|---|---|---|---|
| | *nobody waiting* | | ***a person waiting*** |
| 200 OK | **63.7%** | 53.9% | **25.0%** |
| 403 Forbidden | 17.6% | 19.0% | **34.5%** |
| 404 Not Found | 5.5% | 10.3% | 18.6% |
| 429 Too Many | 2.6% | 4.1% | 6.7% |
| **refused** | **25.7%** | 33.4% | **59.8%** |

The class in which a human is waiting in real time is blocked at twice
the rate of the batch class and receives a valid response one time in
four. The batch class — where nobody waits and service could be deferred
at no cost — succeeds nearly two times in three.

Blocking policy is organised around **identity** (is this an AI bot?),
not cost or urgency. The agent acting for a person is caught in the net
built for the training crawler.

**Caveat.** A 403 may express deliberate publisher policy — paywalls,
licensing disputes, a decision not to serve AI at all — not only
misclassification. The data cannot separate intent. What they show is the
outcome.

## G2. Class composition is re-proportioning fast

Weekly series, 2025-08-18 → 2026-08-17:

| class | Aug 2025 | Aug 2026 | change |
|---|---|---|---|
| **User Action** | 2.20% | **5.06%** | **+130%** |
| **Search** | 9.03% | **17.24%** | **+91%** |
| Training | 36.42% | 39.35% | +8% |
| Mixed Purpose | 51.68% | 36.67% | −29% |

The interactive classes double annually while training is flat.

**Caveat.** The Mixed decline is partly reclassification: Cloudflare
relabelled categories during this window, rewriting monthly views but not
quarterly ones. Prefer quarterly views and state the discontinuity.

## G3. Nobody revalidates

304 Not Modified is **0.53%** of all AI bot requests — Training 0.52%,
User Action 0.68%, Search absent from the top status codes.

Conditional requests exist so a client can ask "has this changed?" and
receive a few hundred bytes instead of the whole document. They are
essentially unused.

## G4. The classes fetch different things

| | Training | Search | User Action |
|---|---|---|---|
| HTML | 75.6% | 67.9% | **78.5%** |
| Plain text | 8.7% | 8.1% | **14.0%** |
| JavaScript | 1.7% | **12.5%** | 0.9% |
| Images | 6.0% | 7.2% | 1.9% |

Agents fetch text and little else — 92.5% HTML and plain text, under 1%
JavaScript. Search crawlers fetch JavaScript at seven times that rate,
consistent with rendering. Different resource footprints, measured,
before any testbed is involved.

---

# Part 2 — Origin behaviour (controlled testbed)

Varnish → gunicorn/Flask (bounded thread pool) → PostgreSQL, CPU-pinned,
VictoriaMetrics at 1 s, k6 open-loop (`constant-arrival-rate`, avoiding
coordinated omission). Corpus: 495 Gutenberg books, 16,954 chapters,
measured cached-object footprint 438 MB. Cold cache before each
measurement, warm-up discarded, randomised order.

## O1. Composition alone produces a regime transition

ARM host, `THREADS=8`, `VARNISH_SIZE=128m`, **λ = 220 req/s constant at
every point**, 65 measurements, 5–10 repetitions.

| α | p99 median (ms) | p95 | hit ratio | pool occupancy |
|---|---|---|---|---|
| 0.00 | 82.9 | 46.9 | 0.827 | 21% |
| 0.05 | 105.9 | 57.4 | 0.791 | 25% |
| 0.10 | 141.9 | 80.3 | 0.753 | 40% |
| 0.15 | 184.6 | 115.1 | 0.713 | 53% |
| 0.20 | 407.1 | 232.4 | 0.673 | 72% |
| **0.25** | **1970.8** | 1390.4 | 0.636 | **89%** |
| 0.30 | 2547.1 | 2430.8 | 0.601 | 95% |
| 0.50 | 2626.4 | 2527.5 | 0.452 | 97% |

Offered load is identical at every point; only composition changes. This
is not "more load breaks things".

Pre-registered criterion (p99 > 10 × 82.9 = 829 ms): **knee at α = 0.25**.

**Amplification.** Origin load is λ(1 − h): 38 req/s at α = 0, 80 at
α = 0.25. A 25-point change in composition produces a **110% increase in
origin load**. With h_A = 0 (O4), r = 1/(1 − h_H) = **4.8**: at equal
request counts, exhaustive traffic imposes nearly five times the origin
load of human traffic.

## O2. The stability boundary is resource-based, not composition-based

Across six campaigns on two architectures:

| host | date | knee at α | pool occupancy |
|---|---|---|---|
| x86, 16 threads, SMT | 08-15 | 0.15 | 96% |
| x86 | 08-16 | 0.30 | 97% |
| x86 | 08-18 | not reached | max 75% |
| x86 | 08-19 | 0.20 | 93% |
| **ARM, 6 cores, no SMT** | **08-27** | **0.25** | **89%** |

**The composition at which the knee occurs varies from 0.15 to 0.30
across architectures, core counts, SMT presence and database warmth. The
pool occupancy at which it occurs stays between 89% and 97%.**

The 08-18 campaign is the control: it never exceeded 75% occupancy and
produced no knee at any α. It was a repeat of an earlier campaign with
**identical hit ratios to 1%** — the cache behaved the same, but
PostgreSQL's working set had migrated into `shared_buffers` (blks_hit
99.96%), origin capacity had risen from 74 to 92 req/s, and ρ had fallen
from 0.98 to 0.75.

**There is no universal AI-percentage limit. There is a
resource-utilisation boundary.** An operator cannot use someone else's α;
they can watch their own ρ, which is already in their monitoring.

*Found by accident, from a campaign that produced nothing. It changed the
project's central question — see `decisions.md` §23.*

## O3. Cache contention is the causal mediator

α drives every link of the chain by construction, so correlations along
it identify nothing. This is an intervention on the hypothesised
mediator: cache capacity varied at fixed λ (x86 host, 08-16).

| cache | knee | p99 at α = 0.50 |
|---|---|---|
| 128 MB | α = 0.30 | 3096 ms |
| 256 MB | α = 1.00 | 252 ms |
| 512 MB | **absent** | **1 ms** |

**At α = 0.50, changing only the cache size takes p99 from 3096 ms to
1 ms** — identical traffic, application and database.

At 512 MB the low-locality workload reaches hit = 1.000 against Zipf's
0.980: the cost inverts. This is textbook scan-versus-LRU behaviour and
is stated to illustrate the mechanism, **not as a finding**. Its
consequence is the argument: *the cost of the low-locality workload is
not a property of the workload; it emerges from its interaction with
bounded cache capacity.*

**Caveat.** Three repetitions per point; cache sizes are configured
capacity, and 512 MB against a 438 MB footprint is close enough that
"above the working set" cannot be claimed confidently.

## O4. For uniform access, hit ratio is cache over footprint — and here it is zero

A client sampling uniformly hits a cached object with probability equal
to the resident fraction of the corpus. That prediction is elementary
probability and is used as **testbed validation, not as a finding**.

On the ARM host, measured **h_A = 0.000**. A sequential scan over an
object set larger than the cache causes LRU to evict precisely the object
needed next. It matches the honeypot, where GPTBot, AhrefsBot and
Amazonbot all show requests-per-URL of exactly 1.00 and Gini 0.00.

Its architectural consequence is not elementary: for this class **there
is no locality to exploit, so no eviction policy can do better than
chance.** Caching stops being a question of *what to keep* and becomes
one of *who gets to keep*.

## O5. A per-class resource budget restores the interactive class

**The mitigation.** The application admits at most N concurrent
low-locality requests; excess receives 503 with `Retry-After: 2` — a
deferral, not a refusal. Implemented as a semaphore acquired
non-blocking, which matters: see the retraction of 08-23.

ARM host, α = 0.25, λ = 220, 25 measurements, 5 repetitions.

| budget | p99 interactive | vs reference | batch throughput | pool |
|---|---|---|---|---|
| **off** | **1343.5 ms** | — | 9870 | **90%** |
| **5** | **270.7 ms** | **5.0× better** | 8623 (−12.6%) | 72% |
| **4** | **174.4 ms** | **7.7× better** | 8078 (−18.2%) | 61% |
| 3 | 147.6 ms | 9.1× better | 7578 (−23.2%) | 49% |
| 2 | 119.5 ms | 11.2× better | 6644 (−32.7%) | 38% |

Pre-registered criterion — interactive p99 below 500 ms with batch
throughput within 20% — is met at **budgets 5 and 4**.

**The same quantity that predicts collapse predicts recovery.**
Composition drives occupancy past 90% and the system breaks; a budget
returns it to 72% and the system recovers. Across six campaigns the knee
sits between 89% and 97%; dropping below, it disappears. The boundary of
O2 works in both directions.

**Isolation is near-perfect: two deferrals on the interactive class
across 148,000 requests in 25 measurements.** (Those two are unexplained;
the semaphore applies only to the low-locality class. Probably
misclassification during an application restart between budget values.)

**Interactive throughput is unchanged** — 29,615 at reference against
29,693 at budget 5. The class was not starved of completed requests, it
was starved of latency. Total system throughput therefore falls with
batch throughput: 39,485 → 38,316, **−3.0%**.

The honest statement is therefore: *at equal requests served to the
interactive class, a per-class budget reduces its latency fivefold at a
cost of 3% of total system work.*

**Retracted claim.** It was first reported that the batch class was also
served faster (p99 1493 → 344 ms). This is probably a survivorship
artefact: the deferred requests are plausibly those that would have
waited longest, so the p99 of the survivors improves by construction.
Service time for the batch class falls only from ~117 to ~104 ms, 11%,
not fourfold.

**Open.** k6 does not honour `Retry-After`, so deferrals appear as lost
work. If a crawler retries — which a batch class with nobody waiting can
afford — the 3% may be entirely temporal. Under test.

## O6. The transition is sharper on the noisier machine

Dispersion across repetitions at the knee:

| host | α | individual p99 (ms) | spread |
|---|---|---|---|
| x86 | 0.20 | 645, 1301, 2681, 2787, 2991 | **4.6×** |
| ARM | 0.30 | 2495 … 2597 (10 runs) | **1.04×** |

On x86 the same configuration produced outcomes differing by more than
four times; on ARM, by 4%.

**This weakens the earlier "bimodal" reading.** The unstable band was
recorded as a property of the phenomenon; the ARM data suggest it is
largely a property of the platform — SMT, competing processes, a
virtualisation layer. Without them the transition is sharp but
deterministic.

What survives is the operational point, and it is unchanged: **variance
moves before the median does**, so an operator watching medians sees
nothing until collapse. What varies is how much variance a given
deployment has.

*A dedicated experiment — α 0.22–0.28 at 0.02, 20 repetitions — is
running to settle this.*

## O7. The plateau is set by the socket backlog (hypothesis, untested)

p99 settles near 2600 ms for every α above the knee. With `BACKLOG=128`
and the origin saturated near 90 req/s the queue drains in ~1.4 s;
with service time this is consistent. Requests are queued, not shed.

If varying `BACKLOG` moves the plateau while leaving the knee position
unchanged, this separates **where** the system breaks from **how badly**.
Arithmetic, not evidence.

## O8. The cost of scan-resistance, and its inversion

ARM host, α = 0.50, total cache 128 MB, 45 valid measurements with the
validity gate active, 3 repetitions per point. The shared reference was
repeated at the start and end of the campaign: 59.85 versus 59.61 req/s,
**0.39% drift over two hours**.

### O8a. The free ride exists and is 16%

Under a shared cache the low-locality class obtains **h = 0.163**, while
sampling uniformly from a 438 MB corpus against a 128 MB cache. It has no
locality: it encounters what the high-locality class made resident. Under
any partition it obtains **h = 0.000**.

This directly replaces the 28% estimate written at the top of `split.sh`,
which came from h_A values retracted on 26 August.

### O8b. The cost is a step, not a curve

| reserved fraction | high hit | low hit | origin (req/s) |
|---|---:|---:|---:|
| shared | 0.747 | **0.163** | **59.7** |
| 0.50 | 0.731 | 0.073 | 65.8 |
| 0.75 | 0.787 | 0.000 | 66.9 |
| 0.90 | 0.800 | 0.000 | 65.6 |
| 1.00 | 0.800 | 0.000 | 66.2 |

The first byte of separation costs the full price: origin load rises
**10.6%** at every reserved fraction, while high-locality hit ratio
saturates at 0.800. The 0.50 partition is strictly dominated by sharing.

### O8c. The benefit reverses at saturation

| λ | shared p99 high | r=1.00 p99 high | shared origin | r=1.00 origin |
|---:|---:|---:|---:|---:|
| 110 | 141.4 | **132.0** | 60.3 | 65.9 |
| 125 | 365.7 | **259.9** | 66.3 | 74.6 |
| 135 | 494.8 | **321.0** | 68.7 | 80.1 |
| 145 | 2243.0 | **1498.8** | 82.0 | 85.4 |
| 155 | **2438.5** | 2958.0 | 83.8 | 86.1 |

Through λ = 145 partitioning improves high-locality p99 by 7–35%, despite
the extra origin load. At λ = 155 it is 21% worse. Partitioning reduces
the protected class's miss exposure from 0.253 to 0.200, but increases
the queue all requests traverse; as ρ approaches 1, the queue term wins.

The defensible form is: *scan-resistance buys latency for the human class
at low utilisation and removes it at high utilisation, exactly when
protection is needed.*

### O8d. Capacity is visible in the pin

Origin load calculated as λ(1 − h) agrees with measured load within 1%
through λ = 135 and diverges by 3–6% at λ = 145 and 155, with served load
fixed at **about 86 req/s**. The divergence above a constant threshold is
the signature of saturation and gives C without a dedicated campaign.

### O8e. Where it breaks is not who pays

At λ = 135, the partitioned run is at ρ = 0.93 with p99 321 ms; the
shared run is at ρ = 0.80 with p99 495 ms. Utilisation predicts when the
origin queue explodes, not how strongly a class feels it: that also
depends on its miss exposure. Both configurations break between ρ = 0.90
and 0.95.

### O8f. Open anomaly

Shared-cache `hit_low` is non-monotone in λ: 0.161, 0.203, 0.239, **0.108**,
0.117. The leading hypothesis is that, as ρ approaches 1, origin capacity
starves long-tail insertions, which are the insertions that create the
free ride. This is a hypothesis from a partial window and does not enter
the paper until measured separately.

---

# Part 3 — Operator behaviour (honeypot)

`theslowshelf.org`, 18,720 pages of public domain literature, robots.txt
permitting all AI crawlers, live since 2026-08-12. **17 days, ~186,000
requests.** Author's browsing and deployment health checks excluded.

**One site. These are case-study observations.** Where Radar corroborates
them at global scale, that is stated.

## H1. Each operator arrives once, exhaustively, then leaves

Daily volume by operator (extract):

| date | Meta | GPTBot | Ahrefs | Semrush | Amazonbot | agents |
|---|---|---|---|---|---|---|
| 08-13 | 266 | 7 | 0 | 0 | 0 | 6 |
| 08-14 | **16,735** | 0 | 106 | 0 | 0 | 0 |
| 08-15 | 1,965 | **19,220** | 1,334 | 0 | 0 | 2 |
| 08-16 | 160 | 0 | 2,282 | 4 | 1 | 14 |
| 08-18 | 12 | 0 | **9,070** | **7,055** | 730 | 2 |
| 08-19 | 23 | 0 | 6,304 | 6,716 | **12,325** | 4 |
| 08-22 | 49 | 44 | 3 | 0 | 1,165 | **279** |
| 08-24 | 19 | 775 | 2 | 2 | 1,021 | **2,542** |
| 08-28 | 22 | 190 | 4 | 3,739 | 324 | **1,160** |

**GPTBot covered 102% of the site in a single day and did not return for
nine.** Meta did the same on 08-14. Ahrefs and Semrush on 08-18.

**Training-crawler load is not a daily average. It is an event.** A site
is flooded by one operator for a day, then another, then another. An
operator who provisions for the mean meets a twenty-fold peak when their
turn comes.

This connects directly to Part 2: the threshold measured there is not a
theoretical limit but **a condition a site actually crosses, one day at a
time**.

## H2. The site's traffic has a life cycle

```
12–15 Aug   exhaustive training crawling     Meta, GPTBot
16–19 Aug   SEO crawling                     Ahrefs, Semrush, SERanking, Amazonbot
22–28 Aug   agentic retrieval                ChatGPT-User, Perplexity, Claude
```

Agentic traffic went from **34 requests in the first week** to **2,542 on
08-24 alone**. First the site is scraped for training, then indexed, then
people reach it through assistants.

**This required a site instrumented before it existed**, which is why
nobody has it.

## H3. SEO crawlers outweigh AI crawlers

Ahrefs, Semrush, SERankingBacklinksBot and DotBot together exceed
**40,000 requests** — more than all AI operators combined. SERanking
alone, at 19,229, is the site's second-largest client and was initially
unclassified.

The public narrative is about AI crawlers. On this site, over these 17
days, the largest exhaustive load was not AI.

## H4. Verifiable identity does not predict cost

**AhrefsBot is the only operator sending Web Bot Auth signature
headers** — cryptographically identified under the emerging IETF scheme —
and opens exactly **1.0 requests per TCP connection**. GPTBot, unsigned,
reuses connections **686 times**.

A policy that admits the signed and rejects the unsigned admits the
expensive and rejects the cheap.

One counterexample, one signing operator. Sufficient to refute "identity
predicts cost"; not sufficient to characterise the relationship.

## H5. Connection reuse varies by three orders of magnitude

686.7 requests per connection for GPTBot; exactly 1.0 for Meta,
AhrefsBot, SemrushBot and Amazonbot; 2.8 for Googlebot. Meta runs HTTP/2
across 331 addresses and opens a fresh connection per request, defeating
the only reason HTTP/2 exists.

Not found in prior measurement — searched IMC/PAM proceedings and the
Cloudflare, Fastly, Akamai, Vercel and Bunny engineering blogs, which
report requests per minute and per IP but not per connection.

**Caveat.** nginx `$connection` is a per-worker serial; the key is (ip,
connection), so connections are undercounted and reuse overcounted. The
error direction is known: 1.0 is a floor no collision can produce
spuriously.

## H6. Selective versus exhaustive crawling

Googlebot covers 17% of the site with Gini 0.18 — some pages matter more.
GPTBot, AhrefsBot and Amazonbot cover it entirely with **Gini 0.00**:
perfectly uniform, every page once.

Economic before technical. Search crawling is constrained by expected
value per page; training crawling is not. Gini is the discriminant, and
it is computable from any access log.

**Caveat.** Googlebot's low coverage may reflect crawl budget on a new
domain rather than policy. Note also that Google operates at least four
distinct crawlers here — Googlebot, GoogleOther (9,459),
Google-CloudVertexBot (625), Google-Extended (285) — which a single label
would conflate.

## H7. Zero revalidation

**One 304 response in ~186,000 requests.** Corroborates G3 at site level:
what Radar measures at 0.53% globally is effectively zero here.

## H8. A quarter of the traffic is unclassified

45,031 requests present a browser-like user agent with no `compatible;`
token. This includes real browsing, but also the undeclared crawler that
on day one presented Chrome 42 / Edge 12 (a 2015 string) and fetched
every page twice.

**Unresolved, and the largest single gap in the honeypot data.**
Behavioural decomposition of this bucket — by connection reuse,
duplication ratio and 404 rate — is outstanding.

Also present: scanners (feroxbuster 708, l9explore 419, Infrawatch 208)
and probes for `/v1/models`, `/mcp`, `/api/mcp`, `/sse` — automated
traffic searching for exposed AI infrastructure. Already documented by
SANS ISC (diary 33150) and Knostic; recorded as independent confirmation.

---

# Open questions

**Q1 — Does the batch class recover its throughput if it retries?**
If honouring `Retry-After` restores throughput, the budget's 3% cost is
temporal rather than real and the conflict between classes is entirely
apparent. *Under test.*

**Q2 — Does the boundary hold at other pool sizes?** **Closed.** The
29 August poolfix campaign varied the pool at fixed volume across 3, 4, 8
and 12. The knee appeared each time and throughput matched to three
figures. The pool is not the resource that saturates; it is the queue in
front of that resource.

**Q3 — Is the unstable band real or platform variance?** **Closed in
favour of platform variance.** See the 30 August retraction below: part
of the band was the load-generator ceiling.

**Q4 — Per-class hit ratio interaction.** **Closed.** See O8a: the
low-locality class gets h=0.163 from shared residence and h=0.000 under
partitioning.

**Q5 — Does the shape survive a different bottleneck?** PostgreSQL CPU
throughout. Constraining the connection pool below the thread pool, or
introducing a downstream service, would move it.

**Q6 — Which behavioural factor produces the effect?** Only locality is
varied. Until connection reuse, burstiness, session state and arrival
process are ablated, "low-locality" cannot become "agentic".

**Q7 — Decompose the browser-like bucket.** A quarter of honeypot traffic
is unattributed. See H8.

**Q8 — Behaviour under realistic dynamics.** All measurements use
stationary arrival rates. H1 shows real load is impulsive: a system whose
mean utilisation sits below the knee may spend a full day above it.

**Q9 — Why does `hit_low` halve at saturation?** See O8f. The leading
hypothesis is throttled insertion of long-tail objects at the origin;
measure it separately before treating it as a result.

**Q10 — Does the free ride survive at scale?** The model predicts R/N with
a logarithmic correction: about 5.6% for one million pages with ten
thousand resident, versus 16.3% measured on 16,954 pages. If it vanishes
at production scale, the partitioning cost vanishes with it and O8b is a
caveat rather than a result.

---

# Corrections and retractions

Nothing is deleted. Fourteen entries; the pattern is visible and is the reason
`contribution-boundary.md` exists.

- **08-12.** All measurements at `VARNISH_SIZE=2m` discarded: Varnish was
  in a crash-restart cycle (`signal=6`, `PANIC REENTRANCY`), initially
  misdiagnosed as CPU saturation because consumption was flat at 92%
  regardless of load.
- **08-14.** Hit-ratio measurements without a discarded warm-up are
  invalid: they include compulsory misses from cache filling and are
  indistinguishable from a capacity limit.
- **08-15.** The pre-registered prediction of a knee at α = 0.35 is
  superseded by observation at 0.15.
- **08-16.** "The α = 1 inversion at large cache is counterintuitive and
  unreported" — **withdrawn**. Textbook scan-versus-LRU behaviour.
- **08-16.** "Cache larger than the working set" — the 245 MB figure was
  corpus text in PostgreSQL, not cached-object footprint, later measured
  at 438 MB.
- **08-18.** The campaign that produced no knee was read as a failure. It
  is O2, and it changed the project's central question.
- **08-23 and 08-27.** Two budget campaigns are **invalid**. The
  semaphore was acquired with a 0.5 s timeout, so a waiting request held
  a gunicorn worker thread while waiting: the budget added latency
  without freeing anything. Signature on both architectures: monotonic
  degradation as the budget tightened. Fixed in `app.py` on 08-23 and in
  `budget.sh` on 08-28 — the runner carried a contradicting default and
  silently overrode the fix for five days.
- **08-26.** All h_A measurements before this date are **retracted**. The
  traversal profile used a random per-run offset; because the permutation
  is bijective modulo corpus size, its value determined how much the
  measurement window overlapped the warm-up. Three repetitions, identical
  configuration, **exactly 7201 completed requests each**, gave h_A of
  **0.051, 0.287, 0.362**. With a seeded offset: **0.667 three times**.
  The value that stands is h_A = 0.000 under a warm-up exceeding cache
  capacity.
- **08-28.** "Agentic traffic is concentrated, not rare — a factor of 40
  under-representation" — **withdrawn**. That was measured over the first
  seven days, before the site was indexed. Over 17 days agentic traffic
  totals ~3,400 requests, reaching 2,542 in a single day. It was not rare
  and not absent; it had not arrived yet.
- **08-28.** "GPTBot completed its scan and does not return" —
  **withdrawn**. It returned on 08-24 with 775 requests. The correct
  reading is H1: operators arrive in exhaustive bursts and the
  composition rotates.
- **08-30.** "A metastable band exists: the same configuration produces
  two distinct latency regimes." **Withdrawn.** Nine high-regime runs all
  had `vus` at exactly 2λ, 6,120–7,002 dropped iterations and 18% errors;
  the ~4.4 s plateau was generator exhaustion. See `decisions.md` §26.
- **08-30.** Campaign `split-20260830-123521` is **null**: the router
  separated classes even in `shared` mode, so the reference did not exist.
  See `decisions.md` §27.
- **08-30.** "Cache contention between classes does not exist" is
  **withdrawn**. `hit_high` stayed at 0.827 because the high-locality
  class had a private cache; with a valid reference it is 0.800 private
  versus 0.747 shared.
- **08-31.** The pre-measurement prediction that the protected setup would
  collapse before sharing, at λ ≈ 134 versus 146, **failed**. It ignored
  exposure and modelled only the queue term. O8c is the corrected account.

**The pattern.** Four of these are the same error: an elegant explanation
built on a partial window, formed within minutes of an interesting
measurement. The moment a result is exciting is the moment the check is
least likely to happen.