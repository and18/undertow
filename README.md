# Undertow

What each class of automated web traffic costs an origin, and what
resource budget it deserves.

> **Status: active research, private repository.** Nothing here is
> peer-reviewed. Every number is provisional and carries the campaign
> that produced it. Retracted results are kept, not deleted — see
> `docs/findings.md`.

---

## The question

Automated clients now issue the majority of HTML requests on Cloudflare's
network. The public discussion is about *volume* and about *identity*:
how many requests, and which bot is allowed in. Both miss the operational
problem.

Web infrastructure was calibrated on human behavioural assumptions —
think time, browser caching, session persistence, connection reuse,
preferential access to popular content. Automated clients violate all of
them at once, and they do not violate them uniformly. A training crawler
is high-volume with nobody waiting. An agentic fetch is low-volume with a
person waiting in real time. These are opposite resource footprints and
opposite urgencies, and the web currently treats them with a single
identity-based decision.

The measurable consequence, from Cloudflare's own published data: in the
week of 24 August 2026, the class with a human waiting received a 403 in
**52.4%** of cases and a valid response in **21.3%**, while the batch
class — where nobody waits and service could be deferred at no cost —
succeeded roughly two times in three.

**A policy organised around cost and urgency instead of identity requires
knowing what each class actually costs. That is what this project
measures.**

The full argument is in `docs/thesis.md`.

---

## Three sources, three roles

| source | establishes | scale |
|---|---|---|
| **Cloudflare Radar** | that the problem is real and mishandled | global |
| **controlled testbed** | why it happens, and that it can be fixed | one origin |
| **honeypot** (`theslowshelf.org`) | that the behavioural classes are not invented | one site |

Radar is queried through the public API. The testbed is a CPU-pinned
Varnish → gunicorn/Flask → PostgreSQL stack driven by k6 in strict
open-loop mode. The honeypot is a public site of 18,720 pages of public
domain literature whose `robots.txt` explicitly permits every AI crawler
— the inverse of current practice, and deliberate: a site that blocks
crawlers cannot observe them.

---

## Results that currently stand

Full statements, evidence and caveats in `docs/findings.md`. Ownership
relative to prior work in `docs/contribution-boundary.md`.

**The stability boundary is a resource, not a composition.** Across six
campaigns on x86 and ARM, the fraction of low-locality traffic at which
the origin collapses varies from 0.15 to 0.30, while the origin
utilisation at which it collapses stays between 0.89 and 0.97. An
operator cannot use someone else's traffic percentage; they can watch
their own utilisation, which is already in their monitoring.

**Cache contention is the causal mediator, established by intervention.**
Varying only cache capacity moves the knee from α=0.30 to α=1.00 to
absent. At α=0.50, cache size alone takes p99 from 3096 ms to 1 ms.

**Scan-resistance has a cost, and it reverses.** Reserving the cache for
the human class raises origin load by 10.6% at every reserve fraction
tested — a step, not a gradient. Below saturation this still buys the
human class latency; at saturation it costs 21% more p99 than a shared
cache. The protection helps until the point at which it is needed.

**A per-class resource budget restores the interactive class.** Bounding
concurrent low-locality requests at the origin, with deferral rather than
refusal, cuts interactive p99 fivefold for 3% of total system work.

**Verifiable identity does not predict cost.** On the honeypot the only
operator sending Web Bot Auth signatures opens one TCP connection per
request; the largest unsigned operator reuses connections 686 times. A
policy admitting the signed and rejecting the unsigned admits the
expensive and rejects the cheap.

**Crawling load is an event, not an average.** Each operator arrives
once, covers the site exhaustively within a day, and leaves. An operator
provisioning for the mean meets a twenty-fold peak when their turn comes.

**Nobody revalidates.** One 304 response in ~186,000 requests on the
honeypot; 0.53% of all AI bot requests globally.

---

## Repository layout

```
docs/
  thesis.md                 The argument. Read this first.
  findings.md               Results, failed predictions, retractions.
  contribution-boundary.md  What is ours to claim, and what is cited.
  decisions.md              Design choices, with the evidence for each.
  setup.md                  How to rebuild the apparatus and validate it.
harness/
  app/                      Flask application under test
  load/                     k6 scripts and campaign runners
  nginx/                    per-class router (split profile)
  varnish/                  cache tier
  observability/            VictoriaMetrics + Grafana
  env.x86-16, env.arm6      per-host configuration
honeypot/
  content/                  static site generator, Gutenberg corpus
  nginx/                    server config and log format
  static/                   robots.txt, about page
tools/                      analysis and corpus utilities
```

Generated and produced material is not versioned: `cache/`, `site/`,
`harness/results/`, `harness/.env`, `harness/nginx/router.active.conf`.
The repository holds what is needed to *reproduce*, not what was
*produced*.

---

## Reproducing

`docs/setup.md` is the full procedure. The short version:

```bash
git clone git@github.com:and18/undertow.git && cd undertow
rsync -avz <existing-host>:~/undertow/cache/ ./cache/   # 495 books
cd harness && cp env.arm6 .env                          # or env.x86-16
docker compose up -d && docker compose --profile tools run --rm loader
bash load/null-test.sh        # is the generator the bottleneck?
bash load/calibrate.sh        # is the workload I/O-bound?
bash load/measure-model.sh    # h_H, h_A and C on *this* machine
```

**Absolute numbers do not transfer between machines.** Capacity, hit
ratios and the composition at which the knee occurs are properties of the
host. Only normalised relations are claimed to transfer, and the
recalibration above is what earns the right to claim them.

Requires 6 physical cores, 16 GB RAM, 50 GB disk. Both x86-64 and aarch64
work. Do not re-download the corpus from Project Gutenberg — it
rate-limits and blocks some ISP ranges; copy `cache/` from an existing
host.

---

## Method, non-negotiable

- **Open-loop load generation.** Closed-loop generators stop issuing
  requests when the system stalls, under-sampling exactly the latency
  tail that matters (coordinated omission). k6
  `constant-arrival-rate` only, with the virtual-user pool sized for the
  saturated regime rather than the nominal one.
- **Constant total rate.** Composition is the independent variable. If
  volume rose with the automated share, a collapse would demonstrate only
  that more load saturates a system — a result from 1961.
- **Validity gate on every run.** A measurement with dropped iterations
  or an error rate above 1% is repeated, not averaged in. Its raw output
  is kept.
- **Intervention, not correlation.** Where one variable drives every link
  of a chain, all correlations along it approach unity by construction.
  Mechanism is established by manipulating the hypothesised mediator.
- **Nothing random unseeded.** A generator parameter drawn at random is
  an uncontrolled variable.
- **Provenance on every run.** Commit hash, full config, seed,
  timestamps.

---

## References

- Zhang, Cai, Wildani, Klimovic. *Rethinking Web Cache Design for the AI
  Era.* SoCC 2025. doi:10.1145/3772052.3772255
- Cloudflare. *Why we're rethinking cache for the AI era.* Blog,
  2 April 2026.
- Cloudflare. *Your site, your rules: new AI traffic options for all
  customers.* Blog, 1 July 2026.
- Qureshi, Patt. *Utility-Based Cache Partitioning.* MICRO 2006.
- Megiddo, Modha. *ARC.* FAST 2003. Jiang, Zhang. *LIRS.* SIGMETRICS
  2002. Johnson, Shasha. *2Q.* VLDB 1994.
- Brooker et al. *On-demand Container Loading in AWS Lambda.*
  arXiv:2305.13162
- Liu et al. *Somesite I Used To Crawl.* IMC 2025. arXiv:2411.15091
- Tene. *How NOT to Measure Latency.*

## Licence

Code MIT. Data and figures CC BY 4.0. Corpus public domain
(Project Gutenberg).