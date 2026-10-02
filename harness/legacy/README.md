# harness/legacy

Campaign runners from the earlier phases of the project (August to mid-September 2026):
thread-pool and budget sweeps, the mediator campaign, the overnight batches and the
partitioned-cache (`split`) nights. They are kept unmodified as a record of how the
project got to its final design; see `docs/decisions.md` and `docs/retractions.md`.

**No run in `docs/registry.csv` depends on them.** Every registered run (`tre-*`) was
produced by `harness/load/treclassi.sh`, directly or through the wrappers that remain in
`harness/load/`.

They were moved here from `harness/load/` and still use paths relative to that directory
(`load/sweep.sh`, `load/budget.sh`, `split.sh`). They are not maintained and are not
expected to run as they are.

| script | what it ran |
|---|---|
| `sweep.sh` | composition sweep at constant total rate (share of the low-locality class) |
| `budget.sh` | per-class resource budget at the origin: does it protect interactive traffic? |
| `mediator.sh` | intervention on the cache size, to test it as the mediator of the knee |
| `poolfix.sh` | the sweep at several application thread-pool sizes (can the pool be too large?) |
| `overnight.sh` | four campaigns in sequence (`budget.sh`, `sweep.sh`) with a drift check |
| `notte.sh` | unattended rate sweep on the partitioned-cache profile (`load/split.sh`) |
| `notte2.sh` | 3 September re-measurement on the same profile after the `TRAV_SKIP` fix |
