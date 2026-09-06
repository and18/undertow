# The argument

The one document that states what this project claims. Everything else
is apparatus or evidence. If a result does not serve a paragraph here, it
does not belong in the paper.

Written 2026-08-31, after the third change of central question. The two
previous framings and why they were abandoned are in `decisions.md` §23
and in the record at the end of this file.

---

## 1. The premise

Web infrastructure encodes a model of its visitor. Caches assume that
some pages are requested far more than others and that requests repeat.
Thread and connection pools are sized against a concurrency derived from
human think time. Conditional requests assume a client that keeps a copy.
Connection reuse assumes a session. Capacity planning assumes a diurnal
cycle and a mean.

None of these are laws. They are calibrations against a population that,
for thirty years, was human.

That population changed. Automated clients now issue the majority of HTML
requests on Cloudflare's network, and they violate every one of those
assumptions at once. That much is now widely reported. What is not
reported is that they do not violate them *uniformly*, and that the
differences between automated clients are larger than the difference
between automated and human.

## 2. The classes have opposite footprints

A training crawler traverses a site exhaustively, once, at high volume,
with nobody waiting for the result. An agentic fetch retrieves two or
three pages, at low volume, with a person waiting in real time. A search
crawler sits between them and is constrained by expected value per page.

These differ in the two dimensions that matter operationally:

- **Cost.** Exhaustive traversal has no locality to exploit. Its cache
  hit ratio is not low, it is zero (measured: h = 0.000 against a corpus
  larger than the cache). Every request becomes a database query. At
  equal request counts it imposes roughly five times the origin load of
  human browsing.
- **Urgency.** The batch class can be deferred at no cost to anyone. The
  agentic class cannot be deferred at all without a person noticing.

Cost and urgency are **anti-correlated**: the expensive class is the one
that could wait.

## 3. The current policy is organised around identity, and it inverts

The web decides by identity — is this an AI bot, is it signed, is it on a
published address range. Cloudflare shipped Search / Agent / Training
classification in July 2026 and will change defaults on 15 September to
block Training and Agent by default on ad-supported pages for new and
free-tier sites.

Classification is the right primitive and this project takes it as input.
But identity-based *decision* produces a measurable misallocation. From
Radar, weekly, for the class with a human waiting in real time:

| week | 200 OK | 403 |
|---|---|---|
| 2026-06-01 | 56.0% | 19.2% |
| 2026-07-13 | 51.3% | 23.9% |
| 2026-08-24 | **21.3%** | **52.4%** |

More than half of agentic requests are now refused outright, before the
September default change has taken effect. The batch class — the
expensive one, the deferrable one — succeeds roughly two times in three.

**The agent acting for a person is caught in the net built for the
training crawler.** A 403 may also express deliberate publisher policy,
and the data cannot separate intent; and the July–August break coincides
with Cloudflare's own reclassification, so behaviour change and
relabelling cannot be fully separated. Both caveats belong in the paper.
Neither dissolves the outcome.

## 4. Identity does not predict cost, and this is not incidental

The IETF working groups are building admission on cryptographic identity
right now. On the honeypot, the only operator sending Web Bot Auth
signatures opens exactly one TCP connection per request. The largest
unsigned operator reuses connections 686 times — three orders of
magnitude apart. One operator running HTTP/2 across 331 addresses opens a
fresh connection per request, defeating the only reason HTTP/2 exists.

A policy that admits the signed and rejects the unsigned admits the
expensive and rejects the cheap. This is one counterexample from one
site: sufficient to refute "identity predicts cost", not sufficient to
characterise the relationship. It is enough to matter, because the
standard is being written now.

## 5. What a cost-based policy requires, and what it costs

If policy should follow cost, cost must be measurable, and the mechanism
by which each class imposes it must be known. Three results establish
this on a controlled origin.

**The boundary is a resource, not a composition.** Across six campaigns
on two architectures the composition at which the origin collapses varies
from 0.15 to 0.30; the origin utilisation at which it collapses stays
between 0.89 and 0.97. There is no universal "AI percentage limit". There
is a utilisation boundary, and an operator already monitors it.

A refinement measured on 2026-08-31: utilisation predicts when the origin
queue explodes, **not** how much a given class suffers, because that also
depends on the class's own miss fraction. Where the system breaks and who
pays for it are two questions.

**Cache contention is the mediator, and protecting the cache is not the
answer.** Intervention establishes the mechanism: varying only cache
capacity moves the knee from α=0.30 to α=1.00 to absent. The proposed
industry response — scan-resistant eviction and separate tiers for AI
traffic — follows from that mechanism, and it has a cost this project
measures and nobody else reports.

Under a shared cache the exhaustive class free-rides: it samples the
corpus uniformly, so it hits whatever the human class happens to have
made resident, without displacing the human class's hot set. Measured
free ride: **16.3%** of exhaustive requests. Partitioning removes it, and
all of it becomes origin load.

The cost is **+10.6% origin load, and it is a step, not a gradient** —
identical at every reserve fraction from 0.50 to 1.00, because the free
ride is destroyed by the first byte of separation while the human class's
gain saturates well below full reservation. A half reservation is
strictly dominated: worse than sharing for *both* classes.

And the benefit reverses. Below saturation the partition still wins on
latency, because it lowers the human class's exposure to the origin more
than it raises the queue. At saturation the queue term diverges and the
partition loses by 21%.

> **Scan-resistance buys the human class latency at low utilisation and
> takes it away at high utilisation — that is, exactly when protection is
> needed.**

This is not a refutation of Zhang et al.: their result about cache
efficiency stands and we replicate it. It is the consequence they state
qualitatively and do not measure, quantified, with a sign that changes.

Its shape is also familiar. Utility-based cache partitioning (Qureshi &
Patt, MICRO 2006) allocates by marginal utility computed from *isolated*
miss-ratio curves. The exhaustive class's isolated utility is zero, so
UCP would give it nothing — precisely the full partition — and total
misses would rise. The free-riding term breaks the additivity that
utility-based partitioning assumes. **A class's utility is not a property
of the class; it is created by the other class's residency.**

**What does work is a budget at the origin.** Bounding concurrent
low-locality requests, with deferral rather than refusal, returns
interactive p99 fivefold for 3% of total system work, and interactive
throughput is unchanged — that class was never starved of completed
requests, it was starved of latency. The isolation is near-total: two
deferrals on the interactive class across 148,000 requests.

Every layer below the application solved this decades ago — DiffServ,
weighted fair queueing, T-CONT scheduling, network slicing, Oracle
Resource Manager consumer groups, application-server work managers. The
web application layer never did, because with only human clients it never
needed to.

## 6. Load is an event, so a budget is not optional

All of the above assumes stationary arrival. Real load is not.

On the honeypot each operator arrives once, covers the site exhaustively
within a day, and leaves for a week. One operator covered 102% of the
site in twenty-four hours. The site then passed through three regimes in
seventeen days: exhaustive training crawling, then SEO indexing, then
agentic retrieval — the last going from 34 requests in the first week to
2,542 in a single day.

**A site whose mean utilisation sits comfortably below the boundary can
spend a full day above it.** Provisioning for the mean meets a
twenty-fold peak. This is why the boundary of §5 is not a theoretical
limit but a line a site actually crosses, one operator at a time — and
why admission control has to be resident rather than provisioned around.

## 7. The transition, and what comes after it

**Where we are.** A mixed population. The problem is interference between
classes and the protection of interactive traffic. Partitioning,
admission control and resource isolation apply. Every result above lives
here.

**Where it goes.** If the automated share approaches one, the fraction of
automated traffic stops being a useful design variable — you cannot plan
around "when agents are 70% I do X" if they are 100%. What remains is the
difference *between* automated clients: selective versus exhaustive,
polling versus bursting, sessioned versus connectionless. The
foundational distinction stops being human/agent and becomes
behaviour/behaviour.

The results that survive that transition are the ones expressed in
resources rather than in composition. Utilisation survives. The knee
survives. Per-class budgets survive. "Human versus AI" does not.

**This section is argument, not result.** Seventeen days of one site and
one testbed do not support a forecast, and any claim here is offered as a
position to be argued with, not a measurement. Stating that plainly is
what keeps the rest of the document credible.

## 8. What would falsify this

- If the free ride is an artefact of corpus scale — 16,954 objects
  against a production site's millions — the partitioning cost may
  vanish. The predicted scaling is resident-set over corpus size with a
  logarithmic correction, which stays non-negligible at production scale,
  but this is derived and not measured.
- If the utilisation boundary moves under a different bottleneck
  (connection pool, I/O-bound database, a downstream service), the
  central transferable claim weakens.
- If a per-class budget fails when the deferred class does not retry,
  the mitigation costs real throughput rather than deferred throughput.
- If the July–August discontinuity in the Radar series is entirely
  reclassification, §3 becomes a statement about labelling and not about
  the web's behaviour.

Each of these is an open experiment, listed in `findings.md`.

---

## Record of previous framings

**Framing 1 — "at what fraction of automated traffic does an origin
collapse?"** Abandoned 2026-08-19. The threshold is not transferable: it
varied 0.15 to 0.30 across machines while the resource boundary did not.

**Framing 2 — "AI breaks the cache."** Abandoned 2026-08-23. Published
by Zhang et al. with the same experimental model, and the second half of
the chain (saturation produces non-linear latency) is Pollaczek–Khinchine.

**Framing 3 — the present one.** Cost and urgency instead of identity.
Adopted 2026-08-26, unchanged by the results of 30–31 August, which
sharpened §5 rather than displacing it.