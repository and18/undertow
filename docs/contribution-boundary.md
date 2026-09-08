# Contribution boundary

The one page to keep in front of you during every experiment. It exists
to prevent spending weeks measuring something already published.

Rule: no experiment is started unless it maps to a row in Column 3. If a
result lands in Column 1, it is cited, never claimed.

Last novelty audit: **2026-09-08**, systematic, against SoCC, IMC, NSDI,
OSDI, SOSP, ATC, MICRO proceedings and the Cloudflare, Fastly, Akamai,
Vercel and Bunny engineering blogs.

---

## The thesis

> Overload control and resource isolation as published assume
> **cooperative clients inside a trust boundary**: they declare their
> class, hold credits, or attach tokens. Automated web traffic is the
> first population where none of that holds — the client cannot be
> modified, its declared identity is forgeable, a third of it is
> unclassifiable, and the only return channel is an HTTP status code.
> In that regime the class must be **inferred from behaviour** and the
> policy must be based on **measured cost**, which requires knowing what
> each class actually costs.

Position relative to prior work:

| layer | question | who answered it |
|---|---|---|
| classification | *what kind of traffic is this?* | Cloudflare (Search/Agent/Training, July 2026) |
| cache policy | *what should the cache keep?* | Zhang et al., SoCC '25 |
| isolation among cooperating tenants | *who gets which share?* | Pisces, Memshare, UCP |
| overload control for cooperating clients | *whose request do I drop?* | DAGOR, Breakwater, Rajomon |
| **cost and admission for uncooperative external clients** | **what does each class cost, and what does it deserve?** | **open** |

Competing on classification would be futile: Cloudflare has global
telemetry and operator verification. Their taxonomy is **input**.

---

## Column 1 — Not ours. Cite, never claim.

**AI/scan traffic degrades cache efficiency.** Zhang, Cai, Wildani,
Klimovic, *Rethinking Web Cache Design for the AI Era*, SoCC '25,
doi:10.1145/3772052.3772255. Varnish miss ratio 17,3% → 32,2% at 25% AI
traffic, → 51,8% at 100%. Prototype on Wikimedia architecture, Locust
generator, enwiki dump 2025-05-20. **Note: two of four authors are
Cloudflare employees and the work is hosted on research.cloudflare.com.
The April 2026 Cloudflare blog is that company communicating its own
paper, not an independent adoption.** 0 citations as of January 2026.

**Cache degradation increases backend pressure.** Same paper, stated
explicitly, qualitative and not measured. This is the sentence our O8
quantifies.

**Separate cache tiers and deferral for AI traffic.** Cloudflare, *Why
we're rethinking cache for the AI era*, 2 April 2026. Proposes
SIEVE/S3FIFO, a deeper cache tier routed by activity type, and —
verbatim — serving AI requests from deep tiers *"or even delayed using
queue-based admission or rate-limiters to prevent backend overload"*,
opening *"the opportunity to defer bulk scraping when infrastructure is
under load"*. **The deferral idea is theirs, published before our
measurement. We quantify it; we did not originate it.**

**Scan workloads are pathological for LRU below the working set.** ARC
(FAST '03), LIRS (SIGMETRICS '02), 2Q (VLDB '94), SIEVE (NSDI '24),
S3-FIFO (SOSP '23).

**Scan-resistance is a documented production problem.** Brooker et al.,
*On-demand Container Loading in AWS Lambda*, arXiv:2305.13162.

**Utility-based cache partitioning.** Qureshi & Patt, MICRO 2006,
doi:10.1109/MICRO.2006.49. Partitions by marginal utility from miss-ratio
curves measured **in isolation**. Our O8d falsifies that additivity
assumption empirically.

**Shared beats partitioned in aggregate, and it costs backend load.**
Cidon, Rushton, Rumble, Stutsman, *Memshare*, USENIX ATC '17,
arXiv:1610.08129. Verbatim: a shared policy gives superior overall hit
rate *"at the expense of a 1% drop in application 3's hit rate. This
would result in 43% higher database load"*. **The closest prior work to
O8c and it must be cited as the foundation.** Differences: their classes
are ordinary applications that both benefit from cache, ours has zero
intrinsic locality; they *infer* database load from hit ratio, we measure
origin req/s; they have no scaling law and no sign flip.

**Free riding in shared caches is a named problem.** Pu, Li, Zaharia,
Ghodsi, Stoica, *FairRide*, NSDI '16. Formalises free-riding as a
**fairness** problem with an impossibility triangle. The term is theirs.

**Performance isolation trades against utilisation.** Pisces (OSDI '12),
Cliffhanger (NSDI '16), RobinHood (OSDI '18), Cake, IOFlow, SQLVM,
A-Cache, Intel CAT/RDT, NVIDIA MIG, KPart (HPCA '18). *"Static
partitioning leads to under-utilization of cache resources"* is the
standard opening sentence of this literature. **Generalising our result
to "shared resource contention" moves it into this field, not away from
it.**

**Overload control with priorities and deadlines.** DAGOR (WeChat 2018),
Breakwater (OSDI '20), Rajomon (NSDI '25), TopFull (SIGCOMM '24), SEDA
(SOSP '01), Cinnamon (Meta), Persephone (SOSP '21), plus priority-based
admission control for web servers from the early 2000s. **All assume
cooperative clients**: credits, tokens, or caller-declared priority.

**Queueing delay grows sharply near capacity.** Kingman (1961),
doi:10.1017/S0305004100036094; Pollaczek–Khinchine; Little. Any
non-linear latency growth near saturation is expected.

**Crawler compliance with robots.txt is partial and measured.** Kim,
Bock, Luo, Liswood, Wenger, *Scrapers Selectively Respect robots.txt
Directives*, IMC '25, doi:10.1145/3730567.3764471, arXiv:2505.21733. 130
bots, 40 days, ~3,9M requests, 36 sites; mean compliance 0,397; SEO
0,704; AI assistants 0,665. **Does not measure 503/429/Retry-After
compliance.**

**Robots.txt and NoAI efficacy.** Liu et al., *Somesite I Used To Crawl*,
IMC '25, arXiv:2411.15091.

**Operator reports of crawler load.** Wikimedia Diff, 1 April 2025 —
verbatim, *"at least 65% of this resource-consuming traffic we get for
the website is coming from bots, a disproportionate amount given the
overall pageviews from bots are about 35% of the total"*. Read the Docs,
73 TB in one month. SourceHut, GNOME, Fedora.

**Automated traffic exceeds human traffic.** Cloudflare: 32% of network
traffic (April 2026 blog) or >57% of HTML requests (Radar). **Two
different denominators; always state which.**

**Crawl-to-refer ratios.** Cloudflare Radar Q1 2026: ~1 276:1 for GPTBot,
~23 951:1 for ClaudeBot. Crawling is extraction, not discovery.

**Scanning for exposed AI infrastructure.** SANS ISC diary 33150;
Knostic. Our H8 observations are independent confirmation only.

---

## Column 2 — Ours. Measured, defensible, with stated limits.

**C1 — The web refuses the wrong traffic, and the series has a break.**
Radar, weekly: User Action 200 OK from 56,0% (1 June) to 21,3% (24
August); 403 from 19,2% to 52,4%; step in the week of 20 July. See
findings G1.
*Status:* the data are Cloudflare's, public and queryable. The
**framing** — that this is a misallocation, plus the identification of
the break — is ours.
*Caveats:* 403 may express publisher policy, not misclassification; and
the composition series has its own step in the week of 3 August, inside
Cloudflare's reclassification window. **Behavioural change and
relabelling cannot be separated.** Re-verify before submission.

**C2 — Class composition is re-proportioning.** User Action +130%,
Search +91%, Training +8% year on year. Same reclassification caveat.

**C3 — Nobody revalidates.** Radar 0,53% globally; honeypot 23 of
378 747 (0,0061%), of which 22 from a single operator.
*Caveat:* the honeypot log does not capture `If-None-Match` /
`If-Modified-Since`; the claim rests on response codes and is an
inference until the log format is extended.

**C4 — Verifiable identity predicts protocol conformance, not transport
cost.** The only Web Bot Auth signer on the honeypot is also the only
operator that revalidates (22 of 23 conditional responses) **and** opens
one TCP connection per request. **There is no such thing as "the cost";
an admission policy must declare which cost it optimises.**
*Caveat:* one site, one signing operator. A counterexample to "identity
predicts cost", not a characterisation.
*Relevance:* IETF working groups are building identity-based admission
now, without this data.

**C5 — Requests per TCP connection, per named operator.** GPTBot 24,0
over 26 days; Google-CloudVertex 10,3; Googlebot 5,2; SemrushBot,
AhrefsBot, DotBot, Meta, Amazonbot, Applebot all 1,0. Not found in prior
measurement.
*Caveats:* nginx `$connection` is a per-worker serial, so reuse is
overcounted; and `keepalive_requests` = 1000 truncates the distribution,
making every figure a lower bound. The earlier 686 figure is superseded.

**C6 — Selective versus exhaustive crawling, quantified by Gini.**
Googlebot 27,3% coverage, Gini 0,38; SERanking 0,001, AhrefsBot 0,003,
GPTBot 0,072. Gini is computable from any access log.

**C7 — Cache contention is the causal mediator.** Intervention on the
mediator, not correlation: cache capacity 128/256/512 MB moves the knee
from α=0,30 to α=1,00 to absent; at α=0,50 cache size alone takes p99
from 3096 ms to 1 ms.
*Caveat:* taken on x86 before the measurement protocol was fixed. Due
for re-measurement; effect size is far larger than any known artefact.

**C8 — The stability boundary is resource-based, not
composition-based.** Six campaigns, two architectures: knee at α from
0,15 to 0,30, occupancy at the knee always 0,89–0,97. **No universal AI
percentage; a utilisation boundary an operator already monitors.**
*Refinement:* ρ predicts when the origin queue explodes, not how much a
given class suffers — that also depends on the class's miss fraction.
*Risk:* a referee may call it Kingman applied. Mitigation: the empirical
invariance across architectures and the miss-fraction corollary are the
contribution, not the queueing theory.

**C9 — A class's hit ratio is not its own property.** Under a shared
cache the exhaustive class obtains a non-zero hit ratio while sampling
uniformly; under a private cache of any size it obtains 0,000. **Its
utility is created by the other class's residency.**
*Foundation to cite:* FairRide (the term), Memshare (the direction).
*What is ours:* the measurement for a class with zero intrinsic
locality, and the scaling law.

**C10 — The free ride scales with the cache-to-corpus ratio.** 0,048 at
7% to 0,804 at 88%. **Bounds the practical importance of C11: on a
production site the free ride is small.** Reporting this is what makes
the work honest rather than alarmist.

**C11 — The cost of partitioning changes sign with scale.** −3,8% at
32 MB, +5,8% at 128 MB, +321% at 384 MB, same total capacity. Explained
by a decomposition whose second term goes negative at large cache:
partitioning stops helping the protected class because in shared mode
the exhaustive class was loading the corpus for it. **The free ride runs
both ways.**
*Foundation to cite:* Memshare.
*Caveats:* one corpus, one popularity distribution, α=0,25, residual
warm-up dependence of ±8% (findings O8f). **Does not refute Cloudflare's
proposal**, which adds a deeper tier rather than splitting fixed
capacity. What it establishes is a condition of validity nobody has
written down.

**C12 — A private cache is worth less than a smaller shared one.** At
384 MB the exhaustive class with 96 MB reserved obtains 0,028; with
32 MB **shared** it obtained 0,048. Directly falsifies the additivity of
isolated utility curves assumed by UCP.
**Operational form: give the exhaustive class zero, or additional
capacity. Never a slice of what you already have.**

**C13 — A per-class budget restores the interactive class.** Deferral,
not refusal: interactive p99 5× better at 3% of total system work,
interactive throughput unchanged, two deferrals on the interactive class
across 148 000 requests.
*Status:* the mechanism is Netflix 2018 and Cloudflare April 2026. **The
measurement is ours.** Frame as quantification, never as invention.
*Existential caveat:* rests on the crawler retrying. See D2.

**C14 — Crawling load is an event, not an average.** Peak-to-mean up to
15,8× per operator; each arrives once, covers the site in a day, leaves.
A site whose mean utilisation sits below the boundary can spend a full
day above it.

**C15 — A third of honeypot traffic presents as a browser and is
hostile.** 130 100 requests, 0,0% with a referer, top paths `/.env`,
`/.git/config`, `/wp-admin/install.php`. **Vulnerability scanning
wearing a browser user agent — not unclassified browsing.** Must be
separated from the traffic classes under study rather than reported as
an open gap.

---

## Column 3 — Must still be demonstrated.

**D1 — There is no agentic class in the testbed.** *Highest priority.*
The thesis concerns a class with a person waiting; the testbed has
humans and crawlers. Build a third profile — few pages, correlated, no
client cache, latency-sensitive — calibrated on H6 and H9, and re-run
C13 with three classes.

**D2 — Do real crawlers honour Retry-After?** The existential risk to
C13, and **not measured by anyone**: Kim et al. cover robots.txt and
crawl-delay, not 503/429. Testable on the honeypot, one operator at a
time. Both outcomes are contributions: if they return, the conflict
between classes is apparent rather than real; if they do not, deferral
is unimplementable until clients change, which is a protocol
specification.

**D3 — Comparison of policies on one bench.** No policy / identity-based
blocking / static budget / urgency-based scheduling, same load, same
capacity. **This is where the work stops measuring and starts
proposing.**

**D4 — Generality.** Does the shape survive a different bottleneck —
connection pool, I/O-bound database, downstream service? All six
campaigns used PostgreSQL CPU.

**D5 — Agentic behaviour is not modelled from data.** Volume from Radar;
behaviour must be generated by querying commercial assistants against
the site.
*Note:* the earlier claim that agentic traffic is under-represented by a
factor of 28 was withdrawn on 08-28.

**D6 — Status-code histogram for the honeypot.** Blocks H9, where six
independent operators converge on 66–69,5% of 404s and a third of
responses are unaccounted for.

**D7 — Re-measure C7 under the current protocol.**

**D8 — Raise `keepalive_requests` and add conditional-request headers to
the honeypot log**, so C3 and C5 stop being lower bounds.

---

## Discipline

- Every Column 2 claim carries its caveat in the paper. Unstated, they
  become referee objections.
- "To our knowledge" on every novelty claim.
- Radar figures re-verified before submission; the API is live and
  Cloudflare reclassifies.
- Absolute numbers from the testbed are properties of one machine. Only
  normalised relations are claimed to transfer.
- **Generalising a wobbling result to make it more important almost
  always makes it less novel.** Novelty lives in specificity. The general
  principle has usually been written by someone; the specific case
  measured well, rarely.
- Nothing is deleted. Withdrawn claims move to the record below.

## Withdrawn

- **2026-08-16** — "The α=1 inversion at large cache is counterintuitive
  and unreported." Textbook scan-vs-LRU behaviour.
- **2026-08-16** — "Cache larger than the working set." 245 MB was
  corpus text in PostgreSQL, not cached-object footprint (438 MB).
- **2026-08-19** — The inferred in-mixture low-locality hit ratio of
  ≈0,13, and its 2026-08-21 replacement of 0,33–0,39. **Both rest on
  h_low measurements retracted on 08-26 and superseded on 09-06.** The
  value that stands is in findings O8b.
- **2026-08-21** — "The web cannot distinguish human from agent
  traffic." Cloudflare shipped exactly that in July 2026.
- **2026-08-28** — "Agentic traffic is concentrated, not rare — a factor
  of 28–40 under-representation." Measured before the site was indexed.
- **2026-08-30** — "Resource allocation for traffic classes is an open
  question nobody has addressed." Cloudflare proposed queue-based
  admission and deferral for bulk scraping in the April 2026 blog. What
  remains ours is the measurement, not the idea.
- **2026-08-30** — "The signed operator is the one that behaves worst."
  It is also the only one that revalidates. Superseded by C4.
- **2026-09-06** — "GPTBot reuses connections 686 times." An artefact of
  a seven-day window; 24,0 over 26 days. Superseded by C5.
- **2026-09-07** — "Generalising from AI traffic to resource competition
  between traffic classes would make the contribution more durable."
  **Rejected after audit:** that framing is the standard opening of
  twenty-five years of performance-isolation literature. Generalising
  removes the novelty rather than increasing it.