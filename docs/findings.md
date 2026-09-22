> **DOCUMENTO SUPERATO — 22 September 2026.** Non usare i numeri contenuti qui: sei
> affermazioni sono state ritirate (vedi `docs/retractions.md`). La fonte di
> verita e `docs/claims.md`. Questo file sara riscritto nella fase di scrittura.

# Findings

Results as obtained, including predictions that failed and diagnoses
later retracted. Companion to `decisions.md` (why things were done),
`contribution-boundary.md` (what is ours to claim), `thesis.md` (the
argument) and `setup.md` (how to rebuild the apparatus).

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
fraction, **not** the agentic fraction — only one of nine workload
parameters is varied, and the ablations that would justify the stronger
word have not been done. There is at present **no agentic class in the
testbed**; see Q11.

**Two hosts.** x86 (Ryzen AI 7 350, 8 physical cores with SMT, WSL2) for
12–23 August; ARM (Ampere Neoverse-N1, 6 physical cores, no SMT, Oracle
Cloud) from 26 August. Absolute numbers are host properties. Only
normalised relations are claimed to transfer.

**Measurement protocol, fixed 2026-09-07 and mandatory from that date.**
`WARMUP=300`, `MEASURE=620`, validity gate on every run (a measurement
with dropped iterations or error rate above 1% is repeated, not averaged
in), shared reference repeated at the start and end of every campaign as
a drift control. `MEASURE` is set so the low-locality class covers the
whole corpus: see `decisions.md` §28. Every result below this line was
taken under that protocol unless stated.

---

# Part 1 — Global scale (Cloudflare Radar)

Radar API. Cloudflare's network covers roughly a fifth of the web; bot
figures are shares of HTML requests, not of all requests and not of
bytes. **Note the two denominators in circulation:** Cloudflare's April
2026 blog states 32% of network traffic is automated, while Radar
reports over 57% of HTML requests. Always cite the denominator.

## G1. The web refuses the wrong traffic — and the series has a break

Response codes by declared crawl purpose, 28 days to 2026-08-30:

| | **Training** | **Search** | **User Action** |
|---|---|---|---|
| | *nobody waiting* | | ***a person waiting*** |
| 200 OK | **62,8%** | 51,7% | **23,2%** |
| 403 Forbidden | 18,4% | 22,7% | **38,2%** |
| refused (403+404+429) | **26,4%** | 36,7% | **62,8%** |

The 28-day average conceals a step change. Weekly, User Action:

| week | 200 OK | 403 |
|---|---|---|
| 2026-06-01 | 56,0% | 19,2% |
| 2026-07-13 | 51,3% | 23,9% |
| 2026-07-20 | 37,1% | 26,9% |
| 2026-08-24 | **21,3%** | **52,4%** |

The break falls in the week of 20 July, immediately after Cloudflare's
1 July announcement. More than half of agentic requests are now refused
outright, **before** the 15 September default change takes effect.

**Caveats, both mandatory in the paper.** (a) A 403 may express
deliberate publisher policy — paywalls, licensing disputes — not only
misclassification; the data cannot separate intent. (b) The composition
series has its own step (User Action from ~2,5% to 5,0–6,7% in the week
of 3 August). Two discontinuities inside the weeks of Cloudflare's own
reclassification: behavioural change and relabelling **cannot be
separated**. Say so before a referee does.

## G2. Class composition is re-proportioning

User Action +130% year on year, Search +91%, Training +8%. The
interactive classes double annually while training is flat. An
`Undeclared` category (1,76%) exists and is absent from earlier tables.

*Caveat:* partly reclassification. Prefer quarterly views; state the
discontinuity.

## G3. Nobody revalidates

304 Not Modified is 0,53% of all AI bot requests globally. Corroborated
at site level by H7.

---

# Part 2 — Origin behaviour (controlled testbed)

Varnish → gunicorn/Flask (bounded thread pool) → PostgreSQL, CPU-pinned,
VictoriaMetrics at 1 s, k6 open-loop (`constant-arrival-rate`). Corpus:
495 Gutenberg books, 16 954 chapters, measured cached-object footprint
438 MB.

**Corpus object sizes are heavy-tailed** and this matters for every
measurement: median 9,5 KB, mean 15,0 KB, standard deviation 32,4 KB,
maximum 1,9 MB. The standard deviation is twice the mean. A measurement
covering only part of the corpus is a biased sample; see the retraction
of 2026-09-06 and `decisions.md` §28.

## O1. Composition alone produces a regime transition

ARM host, `THREADS=8`, `VARNISH_SIZE=128m`, **λ = 220 req/s constant at
every point**, 65 measurements.

| α | p99 median (ms) | hit ratio | pool occupancy |
|---|---|---|---|
| 0,00 | 82,9 | 0,827 | 21% |
| 0,10 | 141,9 | 0,753 | 40% |
| 0,20 | 407,1 | 0,673 | 72% |
| **0,25** | **1970,8** | 0,636 | **89%** |
| 0,30 | 2547,1 | 0,601 | 95% |
| 0,50 | 2626,4 | 0,452 | 97% |

Offered load is identical at every point; only composition changes. This
is not "more load breaks things".

*Status:* the phenomenon is Zhang et al. (SoCC '25) replicated. What is
ours is that it is a **latency** transition at constant total volume,
and the chain below it. Cite, do not claim.

## O2. The stability boundary is resource-based, not composition-based

Across six campaigns on two architectures:

| host | knee at α | occupancy |
|---|---|---|
| x86, 16 threads, SMT | 0,15 | 96% |
| x86 | 0,30 | 97% |
| x86 | not reached | max 75% |
| x86 | 0,20 | 93% |
| **ARM, 6 cores** | **0,25** | **89%** |

**The composition at which the knee occurs varies 0,15–0,30 across
architectures, core counts and database warmth. The occupancy at which
it occurs stays between 0,89 and 0,97.**

There is no universal AI-percentage limit. There is a
resource-utilisation boundary, and an operator already monitors it.

*Found by accident*, from a campaign that produced nothing: see
`decisions.md` §23.

**O2a — refinement, 2026-08-31.** ρ predicts **when the origin queue
explodes, not how much a given class suffers**, because that also
depends on the class's own miss fraction. At λ=135 the partitioned
configuration sits at ρ=0,93 with p99 321 ms while the shared sits at
ρ=0,80 with p99 495 ms. Where the system breaks and who pays are two
questions.

## O3. Cache contention is the causal mediator

α drives every link of the chain by construction, so correlations along
it identify nothing. This is an **intervention on the hypothesised
mediator**: cache capacity varied at fixed λ.

| cache | knee | p99 at α = 0,50 |
|---|---|---|
| 128 MB | α = 0,30 | 3096 ms |
| 256 MB | α = 1,00 | 252 ms |
| 512 MB | **absent** | **1 ms** |

At α=0,50, changing only the cache size takes p99 from 3096 ms to 1 ms —
identical traffic, application and database.

*Caveat:* three repetitions per point, taken on x86 before the
measurement protocol was fixed. **Due for re-measurement** under the
current protocol; the effect size is far larger than any known artefact,
so the conclusion is not in doubt, but the numbers are provisional.

## O4. For uniform access, hit ratio is residency — used as validation

A client sampling uniformly hits a cached object with probability equal
to the resident fraction of the corpus. Elementary; used as **testbed
validation, not as a finding**. With a private cache the low-locality
class measures h = 0,000 at every capacity from 32 to 384 MB (16 runs,
2026-09-06): with nobody else filling the cache, a non-repeating scan
never finds anything.

## O5. A per-class resource budget restores the interactive class

The application admits at most N concurrent low-locality requests;
excess receives 503 with `Retry-After: 2` — a **deferral, not a
refusal**. Implemented as a non-blocking semaphore acquire, which
matters: see the retraction of 08-23.

ARM host, α = 0,25, λ = 220, 25 measurements.

| budget | p99 interactive | vs reference | batch throughput | pool |
|---|---|---|---|---|
| **off** | **1343,5 ms** | — | 9870 | **90%** |
| **5** | **270,7 ms** | **5,0× better** | 8623 (−12,6%) | 72% |
| **4** | **174,4 ms** | **7,7× better** | 8078 (−18,2%) | 61% |
| 2 | 119,5 ms | 11,2× better | 6644 (−32,7%) | 38% |

**The same quantity that predicts collapse predicts recovery.**
Composition drives occupancy past 90% and the system breaks; a budget
returns it to 72% and it recovers.

**Interactive throughput is unchanged** — 29 615 at reference against
29 693 at budget 5. The class was not starved of completed requests, it
was starved of latency. Total system work falls 3,0%.

Isolation is near-perfect: two deferrals on the interactive class across
148 000 requests.

**Open, and it is the existential risk to this result.** k6 does not
honour `Retry-After`, so deferrals appear as lost work. If a real
crawler retries — which a batch class with nobody waiting can afford —
the 3% may be entirely temporal. **Nobody has measured whether real
crawlers honour Retry-After** (Kim et al., IMC '25, measure robots.txt
and crawl-delay compliance, not 503/429). See Q12.

## O6. Dispersion is a property of the platform, not the phenomenon

x86 produced up to 4,6× spread across repetitions at the knee; ARM 1,04×.
The "unstable band" recorded in August was largely platform variance —
SMT, competing processes, a virtualisation layer — plus, as later
established, the generator's VU ceiling. What survives is the
operational point: **variance moves before the median does**, so an
operator watching medians sees nothing until collapse.

## O7. The plateau is set by the socket backlog (hypothesis, untested)

p99 settles near 2600 ms for every α above the knee. With `BACKLOG=128`
and the origin saturated near 90 req/s the queue drains in ~1,4 s.
Arithmetic, not evidence.

## O8. The free ride, its scaling law, and the sign flip

ARM host, λ=110, α=0,25, current protocol, 3 repetitions per point,
`shared` repeated at start and end of each campaign as drift control
(worst observed drift **under 1%**).

### O8a. The low-locality class free-rides on residency it did not create

Under a shared cache the low-locality class obtains a **non-zero hit
ratio while sampling uniformly** from a corpus larger than the cache. It
has no locality: it encounters what the high-locality class has made
resident. Under a private cache of any size it obtains **0,000** (O4).

**The value a class extracts from a cache is not a property of that
class. It is created by the other class's residency.**

### O8b. The free ride scales with the cache-to-corpus ratio

| cache | cache/corpus | h high-locality | **h low-locality** | origin req/s |
|---|---|---|---|---|
| 32 MB | 0,073 | 0,590 | **0,048** | 60,0 |
| 64 MB | 0,146 | 0,686 | **0,089** | 51,0 |
| 128 MB | 0,292 | 0,791 | **0,195** | 39,4 |
| 256 MB | 0,584 | 0,909 | **0,537** | 20,2 |
| 384 MB | 0,877 | 0,964 | **0,804** | 8,3 |

The free ride is, to a good approximation, the resident fraction of the
corpus. **On a production site, where the cache holds a minute fraction
of the content, the free ride is negligible.** This is the result that
bounds the practical importance of everything in O8c.

### O8c. The cost of partitioning changes sign with scale

Full reservation for the high-locality class (r = 1,00) against the
shared reference, same total capacity:

| cache | shared | partitioned | **cost** |
|---|---|---|---|
| 32 MB | 60,0 | 57,5 | **−3,8%** |
| 128 MB | 39,5 | 41,8 | **+5,8%** |
| 384 MB | 8,4 | 35,4 | **+321%** |

At small cache, partitioning **helps**. At large cache it multiplies
origin load by more than four.

**The decomposition that explains the sign flip:**

```
cost = λ·α·h_low^shared  −  λ(1−α)·(h_high^part − h_high^shared)
       free ride destroyed    what the protected class gains
```

| cache | predicted | measured |
|---|---|---|
| 32 MB | −2,56 | **−2,3** |
| 128 MB | +2,31 | **+2,3** |
| 384 MB | +22,1 | **+27,0** |

The second term is normally positive — partitioning helps the human
class. **At 384 MB it goes negative**: h_high falls from 0,964 shared to
0,905 partitioned, *with the same capacity*. In shared mode the
low-locality class was loading the corpus for the high-locality class.
**The free ride runs both ways.** That is where the sign flips.

The algebra is an identity; what is new is that both terms are measured
and that the second changes sign.

### O8d. A private cache is worth less than a smaller shared one

At 384 MB with r=0,75 the low-locality class has **96 MB to itself** and
obtains h = 0,028. With 32 MB **shared**, it obtained 0,048 — nearly
double, with a third of the memory.

Directly falsifies the additivity of isolated utility curves assumed by
utility-based cache partitioning (Qureshi & Patt, MICRO 2006): a class's
isolated utility curve does not predict its behaviour in a mixture.

**Operational form: give the exhaustive class zero, or give it
additional capacity. Never a slice of what you already have.**

### O8e. Capacity reads off the saturation pin

Origin load computed as λ(1−h) agrees with measurement within 1% below
saturation and diverges 3–6% above it, with served load pinned at
**~86 req/s**. Offered and served diverging above a constant threshold
is the signature of saturation, and gives C directly.

### O8f. Residual dependence on warm-up — open

After fixing `MEASURE` to cover the corpus, h_low still varies 0,204 /
0,198 / 0,174 for warm-up 120 / 300 / 600 s. Excursion fell from 1,50×
to **1,17×**; internal repetitions agree to 0,5%, so it is systematic,
not noise. Origin load rises 39,3 → 40,0 while the high-locality hit
ratio does not move.

Leading hypothesis, **untested**: the warm-up leaves the cache in a
state that depends on its duration, so the composition of the cache at
t=0 of the measurement differs. This is a real property of the system,
not a generator artefact: the exhaustive class's hit ratio is a function
of prior state, not a scalar.

**Decision:** the protocol fixes warm-up at 300 s and the residual is
declared as a limit. A ±8% residual on a quantity whose effect sizes
range from −3,8% to +321% does not change any conclusion. Stopping here
is a judgement, and it is recorded as one.

---

# Part 3 — Operator behaviour (honeypot)

`theslowshelf.org`, 18 720 pages of public domain literature, robots.txt
permitting all AI crawlers, live since 2026-08-12. **26 days, 378 747
requests, 0 unparsed lines.**

**One site. These are case-study observations.**

**Measurement ceiling to declare:** `max_req_one_conn` is exactly 1000
for three distinct operators — that is nginx's `keepalive_requests`
default closing the connection. **All connection-reuse figures are lower
bounds.** Raise the limit before drawing quantitative conclusions.

## H1. Each operator arrives once, exhaustively, then leaves

Peak-to-mean ratio per operator reaches **15,8×** (Googlebot), 10,9×
(AhrefsBot), 10,8× (Amazonbot), 10,0% (GPTBot). **Training-crawler load
is not a daily average. It is an event.** An operator who provisions for
the mean meets a fifteen-fold peak when their turn comes.

This connects to Part 2: the boundary measured there is not a
theoretical limit but **a condition a site actually crosses, one
operator at a time**.

## H2. The site's traffic has a life cycle

Exhaustive training crawling (12–15 Aug, Meta then GPTBot) → SEO
crawling (16–19 Aug, Ahrefs, Semrush, SERanking, Amazonbot) → agentic
retrieval (from 22 Aug). Agentic traffic went from 34 requests in the
first week to 947 in a single day on 24 August.

**This required a site instrumented before it existed**, which is why
nobody has it.

## H3. SEO crawlers outweigh AI crawlers

By class over 26 days: unclassified 34,4%, **SEO 30,9%**, AI-training
20,4%, AI-search 6,0%, search 6,0%, **AI-agent 1,4%**, scanners 0,7%.

SemrushBot alone is 56 787 requests — more than any AI operator. The
public narrative is about AI crawlers; on this site the largest
exhaustive load was not AI.

## H4. Verifiable identity does not predict cost — restated correctly

**AhrefsBot is the only operator sending Web Bot Auth signatures**
(19 217 of 19 217 requests signed) **and is also the only operator that
revalidates**: 22 of the 23 conditional responses in the entire dataset
are its. It also opens one TCP connection per request.

The defensible statement is therefore **not** "the signed operator
behaves worst". It is:

> **There is no such thing as "the cost". Verifiable identity predicts
> protocol conformance and does not predict transport efficiency. An
> admission policy must declare which cost it is optimising.**

Admitting the signed and rejecting the unsigned admits the operator that
wastes connections but saves bandwidth, and rejects the opposite.

*Caveat:* one site, one signing operator.

## H5. Connection reuse varies by operator

GPTBot **24,0** requests per connection over 26 days; Google-CloudVertex
10,3; YandexBot 6,3; Googlebot and GoogleOther 5,2; SemrushBot,
AhrefsBot, DotBot, Meta, Amazonbot, Applebot all **1,0**.

**Supersedes the 686 figure** reported over 7 days, which was an artefact
of a short window. Not found in prior measurement — searched IMC/PAM
proceedings and the Cloudflare, Fastly, Akamai, Vercel and Bunny
engineering blogs, which report requests per minute and per IP but not
per connection.

*Caveats:* nginx `$connection` is a per-worker serial, so the key (ip,
connection) undercounts connections and overcounts reuse; and the 1000
ceiling above truncates the top of the distribution.

## H6. Selective versus exhaustive crawling

Googlebot covers 27,3% of the site with **Gini 0,38** — some pages matter
more. SERanking (Gini **0,001**), AhrefsBot (0,003), GPTBot (0,072),
Applebot (0,102), GoogleOther (0,116) cover it near-uniformly.

Economic before technical: search crawling is constrained by expected
value per page, training crawling is not. **Gini is computable from any
access log.**

## H7. Zero revalidation

**23 conditional responses in 378 747 requests (0,0061%)**, of which 22
from AhrefsBot and 1 from Bingbot. Corroborates G3 at site level.

**Instrumentation gap:** the log does not record `If-None-Match` or
`If-Modified-Since`, so this rests on the response code and is an
inference. Add both fields to the nginx log format; until then the claim
is "no 304 responses were issued", not "no conditional requests were
sent".

## H8. A third of the traffic is unclassified, and it is mostly hostile

`browser-like` 86 635 requests (22,9%) and `other` 43 465 (11,5%).
Decomposition:

| | browser-like | other |
|---|---|---|
| duplication ratio | 4,04 | 1,86 |
| requests per connection | 1,6 | 1,8 |
| 404 rate | 6,3% | 18,4% |
| **with referer** | **0,0%** | **0,0%** |

Zero referer in 130 000 requests presenting as browsers. Top paths are
`/`, `/.env`, `/index.php`, `/.git/config`, `/wp-admin/install.php`,
`/signup`, `/proxy`, `/fetch`. **This is not unclassified browsing; it is
vulnerability scanning and credential probing wearing a browser user
agent.** It should be reported as such and separated from the traffic
classes under study.

## H9. The agentic class receives 404 two times in three — open

| operator | 200 | 404 |
|---|---|---|
| Claude-User | **0,7%** | 66,0% |
| Perplexity-User | **0,3%** | 67,0% |
| ChatGPT-User | 29,4% | 49,2% |
| OAI-SearchBot | 37,1% | 42,6% |
| ClaudeBot | 0,5% | 69,5% |
| Google-Extended | 0,2% | 68,2% |

Six independent operators converge on 66–69,5% of 404s **on a site that
blocks nobody**. Six companies do not converge on the same number by
chance.

For Claude-User, 200 + 404 sums to 66,7%: **a third of the responses are
some other code and are not being printed.** The status-code histogram
must be run before this is interpreted. Until then it is an observation,
not a finding.

If it survives, it says the degraded agentic experience is not only the
fault of those who block: **agents request addresses that do not exist**.
That is an architecture problem, and it connects directly to llms.txt,
AI Index and Markdown-for-Agents — the mechanisms meant to expose a map
of what exists. Adoption is thin: 10,1% of domains have llms.txt, and
97% of those files received no requests at all in a month.

---

# Open questions

**Q1 — Do real crawlers honour Retry-After?** The existential risk to
O5. Nobody has measured it. Testable on the honeypot: serve 503 with
`Retry-After` to one operator at a time and count who returns.

**Q5 — Does the shape survive a different bottleneck?** PostgreSQL CPU
throughout. Constraining the connection pool below the thread pool, or
introducing a downstream service, would move it.

**Q6 — Which behavioural factor produces the effect?** Only locality is
varied. Until connection reuse, burstiness, session state and arrival
process are ablated, "low-locality" cannot become "agentic".

**Q8 — Behaviour under realistic dynamics.** All measurements use
stationary arrival rates. H1 shows real load is impulsive.

**Q9 — Why does h_low still depend on warm-up?** See O8f.

**Q10 — Does the free ride survive production scale?** Partly answered
by O8b: it scales with cache/corpus, so on a large site it is small.
What remains open is whether the *sign flip* has any regime of practical
relevance.

**Q11 — There is no agentic class in the testbed.** The thesis concerns
a class with a person waiting; the testbed has humans and crawlers. The
largest remaining gap. Parameters available from H6 and H9.

**Q12 — Status-code histogram for the honeypot.** Blocks H9.

**Q13 — Re-measure O3 under the current protocol.**

---

# Corrections and retractions

Nothing is deleted. Fifteen entries. **Four of the first ten are the same
error: an elegant explanation built on a partial window, formed within
minutes of an interesting measurement.** The moment a result is exciting
is the moment the check is least likely to happen.

- **08-12.** All measurements at `VARNISH_SIZE=2m` discarded: Varnish was
  in a crash-restart cycle, misdiagnosed as CPU saturation.
- **08-14.** Hit-ratio measurements without a discarded warm-up are
  invalid.
- **08-15.** The pre-registered prediction of a knee at α = 0,35 is
  superseded by observation at 0,15.
- **08-16.** "The α=1 inversion at large cache is counterintuitive and
  unreported" — **withdrawn**. Textbook scan-versus-LRU behaviour.
- **08-16.** "Cache larger than the working set" — the 245 MB figure was
  corpus text in PostgreSQL, not cached-object footprint (438 MB).
- **08-18.** The campaign that produced no knee was read as a failure.
  It is O2, and it changed the project's central question.
- **08-23 and 08-27.** Two budget campaigns **invalid**: the semaphore
  was acquired with a 0,5 s timeout, so a waiting request held a worker
  thread. The runner carried a contradicting default and silently
  overrode the fix for five days.
- **08-26.** All h_low measurements before this date **retracted**: the
  traversal profile used a random per-run offset, making the result a
  lottery over cache overlap.
- **08-28.** "Agentic traffic is concentrated, not rare — a factor of 40
  under-representation" — **withdrawn**. Measured over the first seven
  days, before the site was indexed.
- **08-28.** "GPTBot completed its scan and does not return" —
  **withdrawn**. It returned on 08-24.
- **08-30.** "There is a metastable band: the same configuration
  produces two distinct latency regimes" — **withdrawn**. All nine runs
  in the high regime had `vus` at the exact ceiling of 2λ, 6 120–7 002
  dropped iterations and 18% errors. The ~4,4 s plateau was the latency
  at which the virtual-user pool exhausts. See `decisions.md` §26.
- **08-30.** Campaign `split-20260830-123521` is **void**. The router
  routed the classes to separate instances even in `shared` mode, so the
  shared reference did not exist. See `decisions.md` §27.
- **08-30.** "Cache contention between classes does not exist: h_high
  stays 0,827 when 25% exhaustive traffic is added" — **withdrawn**, and
  it is the inverted reading of the previous bug: the high-locality class
  had a private cache in every configuration, so α could not touch it by
  construction.
- **08-31.** Registered prediction: "the protected configuration
  collapses **before** the shared one, at λ ≈ 134 against 146, because
  +10% origin load moves it closer to the knee." **Failed.** The
  protected configuration was better up to λ=145 and worse only at 155.
  The error was structural: the model contained only the queueing term
  and ignored the exposure term — half the mechanism.
- **09-06.** All h_low measurements before the `MEASURE=620` protocol
  are **superseded**. Two compounding causes. (a) Warm-up and measurement
  were separate k6 invocations, so `iterationInTest` restarted and the
  exhaustive class revisited exactly the objects inserted `WARMUP`
  seconds earlier; h_low measured the cache's survival curve, not the
  free ride. Signature: 0,163 at warm-up 180 s against 0,089 at 300 s.
  (b) After fixing that, `MEASURE=180` covered only 29% of a
  heavy-tailed corpus, so different windows sampled objects of different
  sizes. Excursion 1,50×, invisible because the traversal order is
  deterministic and three repetitions returned the same number.
  **A diagnosis proposed on 09-07 — that the cause was correlation
  between the traversal order and the popularity rank — was itself
  wrong**: changing the permutation multiplier left the effect
  unchanged. See `decisions.md` §28.