# Reproducing the experiment

How to rebuild the apparatus on a new machine and reach the point where a
measurement is valid. Written because that knowledge was spread across
chat logs, and because moving from x86 to ARM took four attempts — each
failure being a component confined to one core rather than saturated by
the workload.

**The rule that governs everything below: absolute numbers do not
transfer between machines.** Capacity, hit ratios and the composition at
which the knee occurs are properties of the host. Only normalised
relations are claimed to transfer, and the recalibration below is what
earns the right to claim them.

---

## What you need

- A host with **at least 6 physical cores**. Fewer means components share
  cores and the null test cannot separate generator from target.
- 16 GB RAM. The corpus is 245 MB of text in PostgreSQL, ~438 MB as
  cached response objects.
- 50 GB disk.
- Docker Engine with the Compose plugin.
- The corpus: 495 Project Gutenberg books in `cache/`. **Do not
  re-download** — Gutenberg rate-limits and some ISPs are blocked; copy
  the directory from an existing host.

Both x86-64 and aarch64 work. Every image in the stack has an arm64
build, verified 2026-08-26.

---

## Bring-up

```bash
git clone git@github.com:and18/undertow.git && cd undertow
rsync -avz <existing-host>:~/undertow/cache/ ./cache/
ls cache/*.txt | wc -l          # expect ~495

cd harness
cp env.x86-16 .env              # or env.arm6, or write your own
cat .env.example >> .env        # then set the two passwords in .env
nproc                           # confirm the cpusets in .env fit
docker compose up -d && sleep 30
docker compose ps
curl -s localhost:8428/api/v1/targets | jq -r '.data.activeTargets[] | "\(.labels.job) \(.health)"'
```

Four targets `up`. Then load the corpus:

```bash
docker compose --profile tools run --rm loader
```

Expect **495 books, 16,954 chapters, 203,437 links**. Different numbers
mean a different corpus and nothing downstream is comparable.

---

## CPU allocation

Every component is pinned. The allocation is not cosmetic: three of the
four attempts on the ARM host failed because one component was confined
to a single core and saturated there regardless of offered load.

**The diagnostic for a bad allocation:** a component whose CPU is *flat*
across a wide range of offered load. Varnish at 100% from 500 to 16,000
req/s is not saturated by traffic — it is confined by its allocation, and
everything measured behind it is measuring that confinement.

Working allocations:

| host | k6 | Varnish | app | PostgreSQL | obs |
|---|---|---|---|---|---|
| 16-thread x86 (8 physical, SMT) | 0–3 | 4–7 | 8–9 | 10–11 | 14–15 |
| 6-core ARM (no SMT) | 0 | 1 | 2 | 3–5 | 0 |

Two principles, learned by getting them wrong:

- **PostgreSQL needs the most.** It is the intended bottleneck, but it
  must saturate *gradually* with load, not sit at one pinned core. On six
  cores it needs three.
- **The application needs one.** Python's GIL makes a second core
  useless: observed ceiling is 80–95% of a single core regardless of
  allocation.

---

## Validation, in order. No shortcuts.

### 1. Null test — is the generator the bottleneck?

```bash
bash load/null-test.sh                  # or RATES="200 400 800 1600"
```

A rate is clean only if `dropped_iterations == 0` **and** failures below
0.1% **and** p99 below 200 ms. Zero drops alone is not sufficient: a
point with p99 of 17 seconds and 3% failures once passed that check while
describing a system already broken.

Read the CPU columns. Varnish must scale with rate, not sit flat.

**Target:** a clean ceiling at least 5× the intended operating rate.

### 2. Calibration — is the workload I/O-bound?

```bash
bash load/calibrate.sh                  # or RATES="20 40 60 80 120 160"
```

**Required:** pool occupancy above 70% while application CPU stays below
60%. That combination means threads are *blocked* on PostgreSQL, not
computing — which is the precondition for the pool to be the resource
under study rather than the interpreter.

Also check that database CPU **rises** with rate. Flat at 100% means one
saturated core; go back to the allocation.

The `/health` endpoint is for the null test only. It does no I/O, so it
measures the GIL.

**On ARM the search endpoint is unusable** — `ts_rank` and `ts_headline`
time out at every rate. Experiments run on the cacheable chapter
endpoint, which is also the right one for the thesis. Declare it as a
limitation.

The k6 pool is sized for the saturated regime: `preAllocatedVUs = RATE ×
2`, `maxVUs = RATE × 20`, capped at 20,000. The pool must be sized for the
worst regime, not the nominal one; a run with dropped iterations measures
the generator rather than the system.

### 3. Model parameters — h_H, h_A and C on *this* machine

```bash
bash load/measure-model.sh              # or CAP_RATES="50 60 70 80 90 100"
```

C is the origin rate beyond which pool occupancy exceeds 90%. Choose the
rate ladder so that at least two points sit **below 60%** occupancy: with
no unsaturated regime there is no curve, only a plateau.

Expected shape: h_H ≈ 0.79–0.83, **h_A ≈ 0** (a sequential scan over an
object set larger than the cache causes LRU to evict exactly the object
needed next), C between 70 and 120 req/s depending on the host.

If h_A comes out well above zero, the warm-up is too short to exceed
cache capacity and you are measuring overlap, not steady state.

---

## Deriving the operating point

Origin load under a mixture:

    λ_origin(α) = λ · [(1 − h_H) + α(h_H − h_A)]

The knee falls where this reaches C. To place it at a chosen α\*:

    λ = C / [(1 − h_H) + α*(h_H − h_A)]

Worked example, ARM host: h_H = 0.791, h_A = 0.000, C ≈ 90, α\* = 0.25
gives λ = 220 req/s, with baseline utilisation u₀ = 0.51. Observed knee:
α = 0.25 at 89% pool occupancy.

Check before running: **λ must stay well under the generator ceiling from
step 1.**

## Split profile and reference control

The `split` profile resolves `router.conf.tpl` to `router.active.conf` in
`split.sh`. The `low-locality` class is routed by user agent matching
`~*lowloc`: to `varnish-h` for the shared reference and to `varnish-l` for
partitioned configurations. The two Varnish sizes come from `.env`; the
resolved router file is not versioned. Both paths remain behind nginx.

The shared reference must run twice per campaign, at the beginning and at
the end, to detect drift. A mismatch invalidates the campaign.

---

## Campaign hygiene

Non-negotiable, each learned from a run that had to be discarded:

- **Cold cache before every measurement.** With randomised execution
  order, inheriting the previous point's cache is fatal.
- **Warm-up discarded, and long enough.** 180 s at 128 MB; 600 s at
  512 MB. Too short and hit ratios at different cache sizes come out
  identical, because you are measuring cache fill rather than steady
  state.
- **Randomised order within each configuration.** Machines drift over a
  six-hour campaign. Monotonic order turns drift into a plausible,
  entirely false trend.
- **Nothing random unseeded.** See `decisions.md` §20.
- **Measure C in the same campaign.** It drifts as PostgreSQL warms —
  74 → 92 req/s over four days on one host.
- **Report ρ alongside α.** ρ transfers; α does not.

---

## Long runs

Campaigns take 3–8 hours. Detach them:

```bash
nohup bash load/treclassi.sh > /tmp/treclassi.log 2>&1 &
```

Results land in `harness/results/tre-<timestamp>/points.csv`, one row
written per completed measurement, so an interruption costs only the
run in flight. Each run directory also gets `env.txt`, the full
environment of the launching shell: check it 30 seconds after launch, and
do not publish it as is (in an SSH session it contains the client
address). The earlier runners (`sweep.sh`, `budget.sh`, ...) are in
`harness/legacy/` and are not maintained.

A laptop is not a suitable host for these campaigns: two kernel panics
(`WORKER_INVALID`) occurred on the x86 development machine during
long runs under WSL2, each costing a full campaign.

---

## Verifying a port

Moving to a new host is also the **invariance test**. Run the same
campaign and compare in normalised terms: the composition at which the
knee occurs will differ, the pool occupancy at which it occurs should
not.

Across five campaigns on two architectures: α from 0.15 to 0.30, pool
occupancy from 89% to 97%. That gap is the result.