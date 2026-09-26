# Esito della replica nello stesso giorno
**26 settembre 2026.** Confronto contro `docs/PREREG-replica-20260924.md` (commit
`3abb66f`, pushato prima del lancio e non modificato). Analisi con
`tools/replica_analysis.py` (commit `dd7d6f6`, collaudato sui run di riferimento prima
di leggere i run nuovi: riproduce tutti gli Ō e gli SE della tabella di R4).

## Campagna

Lanciata con `tools/replica-20260924.sh` sul lab a `3abb66f` (hash nell'ultima riga di
ogni `env.txt`). Cinque punti nell'ordine pre-registrato, tutti con esito gate `ok`,
nessun punto rifatto. Fine alle 04:16 UTC del 26 settembre.

| punto | run | inizio (UTC) | gate |
|---|---|---|---|
| C12 | `tre-20260925-213527` | 25 set 21:35 | ok |
| S12 | `tre-20260925-225538` | 25 set 22:55 | ok |
| S36 | `tre-20260926-001550` | 26 set 00:15 | ok |
| P0 | `tre-20260926-013602` | 26 set 01:36 | ok |
| C36 | `tre-20260926-025613` | 26 set 02:56 | ok |

## Verdetto: R1, R2, R3 passano

| criterio | misura | soglia pre-registrata | esito |
|---|---|---|---|
| **R1** (A1) (a) | m = **−0,0405 ± 0,0061**, t = −6,60 (df 4,16) | m < 0 e t ≤ −3 | PASSA |
| **R1** (A1) (b) | \|m − m_ref\| = 0,00525 (m_ref = −0,035251 ± 0,005261) | ≤ 3 SE combinati = 0,02424 | PASSA |
| **R1** | | (a) e (b) | **PASSA** |
| **R2** (A3) q = 12 | d = **+0,882 ± 0,183**, t = 4,82 (df 7,47) | d > 0 e t ≥ 3 | PASSA |
| **R2** (A3) q = 36 | d = **+0,872 ± 0,064**, t = 13,62 (df 4,94) | d > 0 e t ≥ 3 | PASSA |
| **R2** | | entrambi | **PASSA** |
| **R3** (A9) | netto = **+0,238 ± 0,110**, t = 2,16 (df 4,30) | t > −2 | **PASSA** |

**IC 95% di R3** (riportato come richiesto dalla pre-registrazione):
**[−0,0601, +0,5361]**. Contiene lo zero. Il run di riferimento dava [+0,0215, +0,7625].
Il criterio e' «non significativamente negativo» e regge; i due intervalli non si uniscono.

**R2, dipendenza dal tasso.** Il 20-21 set l'effetto della sovrapposizione valeva +0,714 a
12 req/s e +1,012 a 36. Nella replica vale +0,882 e +0,872: la differenza fra i due tassi
non si ripete. Non si afferma che l'effetto cresca con il tasso.

## R4 — deriva fra giorni (misura, nessuna soglia)

Nuovo meno riferimento, `origin_rps`:

| punto | riferimento | Ō riferimento | Ō nuovo | Δ (req/s) | Δ in SE |
|---|---|---|---|---|---|
| C12 | `tre-20260920-114026` | 36,9500 ± 0,0912 | 36,7960 ± 0,1109 | −0,1540 ± 0,1436 | −1,07 |
| S12 | `tre-20260921-150237` | 37,6640 ± 0,0845 | 37,6780 ± 0,1457 | +0,0140 ± 0,1684 | +0,08 |
| S36 | `tre-20260921-162248` | 36,8180 ± 0,0938 | 36,7060 ± 0,0209 | −0,1120 ± 0,0961 | −1,17 |
| P0 | `tre-20260920-102015` | 36,4260 ± 0,1274 | 36,4680 ± 0,1083 | +0,0420 ± 0,1672 | +0,25 |
| C36 | `tre-20260920-130038` | 35,8060 ± 0,0910 | 35,8340 ± 0,0605 | +0,0280 ± 0,1093 | +0,26 |

Scarto massimo in valore assoluto: 0,154 req/s (C12); tutti entro 1,17 SE. La deriva
dentro la notte non e' misurata (nessun punto ripetuto nella notte), come dichiarato.

## Annotazioni

- **AGENT_MUL del P0 di riferimento.** `tre-20260920-102015` non ha `env.txt`. Il valore
  e' ricostruito dal codice, non letto: allora `treclassi.sh` non passava `AGENT_MUL` a
  k6 (lo fa da `9d5d016`, 21 set), quindi valeva il default di `workload.js`,
  2654435761. Il P0 nuovo ha `AGENT_MUL=2654435761` in `env.txt`. Con β = 0 il valore non
  ha effetto. Non e' uno scostamento: il disegno prevede per P0 il default.
- **Gradi di liberta' bassi in R1 e R3** (4,16 e 4,30). S36 nuovo ha una varianza fra
  ripetizioni molto piccola (SE 0,0209 contro 0,1457 di S12 e 0,1083 di P0), quindi il
  df di Welch-Satterthwaite scende verso n − 1 = 4 del gruppo piu' variabile. Il quantile
  usato per l'IC di R3 (t₀,₉₇₅ = 2,7024) ne tiene conto.
- **Nessuno scostamento dalla pre-registrazione.** Disegno, ordine, configurazione
  (verificata in `env.txt` dallo script a 30 s da ogni avvio), gate, formule e soglie
  sono quelli scritti in `3abb66f`. Nessun run rifatto, nessuna analisi prima della fine
  della campagna.

## Cosa cambia in `claims.md` (v3.6)

- **A1**: il punto a scope 0,02 ha una replica pre-registrata nello stesso giorno.
  L'ambito non cambia: lab, Varnish, generatore sintetico; replicato solo lo scope 0,02.
- **A3**: replicata a 12 e 36 req/s nello stesso giorno; nessun claim di crescita col
  tasso.
- **A9**: resta «netto non negativo», con entrambi gli IC riportati separatamente.
- **Nota metodologica** sulla deriva fra giorni (R4).
