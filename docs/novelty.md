# Novelty ledger

One row per claim the project might make, with an explicit status. Kept
current as results accumulate; the basis for the related-work section.

This document exists because of a specific failure mode. On 2026-08-16 a
result was described internally as "counterintuitive and not reported"
when it is in fact textbook caching theory. Enthusiasm at the moment of a
result is exactly when the check is least likely to happen, so it is
written down instead.

**Status values**

| status | meaning |
|---|---|
| `known` | established in the literature; cite, never claim |
| `partial` | the phenomenon is known; our angle, method or setting differs |
| `not found` | no prior work located; a candidate contribution |
| `unchecked` | not yet searched |

`not found` is not `novel`. Absence of evidence in a search is weak
evidence of absence. Every `not found` states what was searched.

---

## Established — cite, do not claim

**Access locality determines cache hit ratio, and hit ratio determines
performance.**
`known`. Foundational. Miss-ratio curves as a function of cache size are
a standard tool.

**Cyclic scan workloads are pathological for LRU below the working set,
and benign above it.**
`known`. The standard rationale for scan-resistant eviction (ARC, LIRS,
SIEVE, S3-FIFO). This is the explanation for our α = 1 inversion at
512 MB: it illustrates the mechanism and must not be presented as a
finding.

**Hit ratio rises with cache size.**
`known`. Our cache-size sweep re-measures a textbook relation; its value
here is as an instrument, not a result.

**AI crawler traffic has low locality and degrades cache efficiency.**
`known`. Zhang, Cai, Wildani, Klimovic, *Rethinking Web Cache Design for
the AI Era*, SoCC 2025, doi:10.1145/3772052.3772255. 25% AI traffic takes
Varnish miss ratio from 17.3% to 32.2% on a Wikimedia-replica testbed.
This is our starting point, not our contribution.

**Queueing delay grows sharply as utilisation approaches capacity.**
`known`. Pollaczek–Khinchine; Little's law. Any non-linear latency growth
near saturation is expected, not discovered. What can be contributed is a
measured threshold in a specific setting, not the existence of the
phenomenon.

**Automated traffic exceeds human traffic in volume.**
`known`. Cloudflare Radar, Imperva Bad Bot Report, Fastly threat
insights. Vendor-reported, methodologically heterogeneous, and to be
cited with those caveats.

**Automated scanning for exposed AI infrastructure (`/v1/models`, MCP
transports).**
`known`. SANS ISC diary 33150; Knostic's survey of exposed MCP servers,
July 2025; Bitsight, December 2025. Our honeypot observations are
independent confirmation only.

---

## Candidate contributions

**C1 — Tracing the effect through the cache to origin-tier saturation,
with a measured threshold.**
`not found`. Zhang et al. state that cache bypass "increases pressure on
application servers, storage systems, and databases" but do not measure
it: their experiment ends at the cache tier. No located work traces the
chain to a bounded origin resource and identifies where it breaks.
*Searched*: ACM DL (SoCC, SIGCOMM, IMC, EuroSys, Middleware), USENIX
(NSDI, ATC, OSDI), arXiv cs.NI/cs.DC, engineering blogs from Cloudflare,
Fastly, Vercel, Akamai.
*What we add*: the composition threshold at which an origin crosses from
stable to collapsed, at constant total arrival rate.

**C2 — Per-class cache hit ratios are not invariant under composition,
and the interaction is bidirectional.**
`not found`. Cache interference between workloads is studied, but the
specific decomposition — high-locality class loses 0.052 while
low-locality class gains 0.105 as its share grows, net positive — was not
located, nor the practical consequence that a mixture model parameterised
with isolated per-class hit ratios misestimates the tolerable fraction by
2.3× in the optimistic direction.
*Searched*: cache partitioning and multi-tenant caching literature;
miss-ratio-curve work.
*Caveat*: this may exist in the shared-cache CPU literature under
different terminology. Not yet searched there. **Priority check.**

**C3 — Variance diverges before the median does: the unstable band.**
`not found` for this phenomenon. That variance grows near saturation is
implied by queueing theory; that a system becomes *bimodal* — the same
configuration yielding 486 ms or 1654 ms — at a specific composition, and
that this precedes any median degradation, was not located as a
documented observation with an operational reading.
*Searched*: tail-latency literature (Dean & Barroso and successors), SRE
practice literature.
*Caveat*: five and three repetitions respectively. Bimodality is not
established; only anomalous dispersion is. Q7 addresses this.

**C4 — The position of the regime transition shifts with cache capacity,
and the transition disappears above a sufficient capacity.**
`not found`. Note carefully what is and is not claimed: that larger
caches improve hit ratio is `known` (above). The candidate contribution
is that **the location of a downstream regime transition** is a function
of cache capacity, which makes cache capacity usable as an *intervention
on the mediator* and separates mechanism from correlation.
*Searched*: as C1, plus cache-sizing and capacity-planning literature.
*What we add*: knee at α = 0.30 with 128 MB, α = 1.00 with 256 MB, absent
at 512 MB; and the method — intervening on the mediator rather than
correlating along the chain.

**C5 — Cryptographic identity and infrastructure cost are independent.**
`not found`. AhrefsBot is the only operator on our honeypot signing under
Web Bot Auth and opens one TCP connection per request; GPTBot is unsigned
and reuses connections 217 times. The consequence — that identity-based
admission admits expensive traffic and rejects cheap traffic — was not
located as a stated argument.
*Searched*: IETF webbotauth drafts and mailing list; Cloudflare, Akamai,
Vercel bot-management documentation.
*Caveat*: four days, one site, n = 1 operator per class. Suggestive only.

**C6 — Per-operator HTTP behaviour at connection granularity.**
`partial`. Per-operator crawler measurement exists (Vercel/MERJ on
JavaScript execution and 404 rates; Fastly on volume share; Kim et al.,
IMC 2025, on robots.txt compliance). **Connection reuse** — requests per
TCP connection, per operator — was not located in any of them.
*What we add*: one dimension, on one site, over a short window.

**C7 — An open workload generator with explicit, calibrated access
models for mixed human/automated traffic.**
`not found` for the HTTP-origin layer. Agentic benchmarks exist for the
LLM inference layer (AgenticSwarmBench, Applied Compute's replay harness)
but measure token serving, not origin load.
*Status*: an artefact, not a finding. Its value depends on adoption.

**C8 — Origin-level per-class resource budgeting for automated traffic.**
`unchecked` as a contribution — the experiment has not been run. The
components are `known`: DiffServ, weighted fair queueing, WebLogic work
managers, Oracle Resource Manager consumer groups, MySQL resource groups,
CockroachDB admission control, Atropos (SOSP 2025). What is not located
is an evaluation of class-based budgeting for automated web traffic at
the origin, as an alternative to edge allow/deny. Q8.

---

## Rejected claims

Kept so the same mistake is not made twice.

**"The α = 1 inversion at large cache is counterintuitive and
unreported."** Stated internally 2026-08-16, **withdrawn the same day**.
It is a direct consequence of standard caching theory and is the reason
scan-resistant eviction policies exist. Retained in `findings.md` §F6 as
an illustration of the mechanism, explicitly not as a finding.

**"Cache larger than the working set."** Used repeatedly before
2026-08-16. The 245 MB figure is the corpus size in PostgreSQL, not the
footprint of cached responses; 256 MB exceeds it and still shows
contention. Replaced everywhere with configured capacity, which is what
was actually varied.

---

## Checks still owed

1. **C2 against the CPU shared-cache literature.** Cache interference
   between co-running workloads is heavily studied there and may contain
   the composition-dependence result under other terminology. Highest
   priority.
2. **C3 against the queueing and tail-latency literature.** Variance
   divergence before mean divergence near saturation may be a known
   result with a name.
3. **C1 against database and storage buffer-pool literature.** The
   scan-versus-locality contention pattern is old there; the question is
   whether anyone has traced it to a regime transition with a threshold.
4. **All rows against Google Scholar forward citations of Zhang et al.**
   The paper is recent; work citing it is where a direct collision would
   appear.