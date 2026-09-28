# Esito della fase 1 del simulatore — validazione sul lab
**28 settembre 2026.** Confronto contro `docs/PREREG-simulatore-fase1.md` (commit `c026e0b`,
pushato prima di qualunque confronto) con l'emendamento 1 (`5c9597a`, pushato prima del
secondo tentativo dei cancelli). Codice in `tools/sim/`, uscite in `data/sim/fase1/`.
**Ogni numero di questo documento e' SIMULATO**, salvo le colonne «lab».

## Verdetto

Cancelli G0, G1, G2 **passano** al secondo tentativo, senza ricalibrazione (H = 512 byte,
intestazioni 250 byte, come pre-registrato). T1, T2, T3, M1, M2 **passano tutti**. Secondo la
regola scritta prima: **simulatore valido per segni e ampiezze** nella fase 2.

## Cancelli

**Primo tentativo** (26 set, commit `66b2818`, `data/sim/fase1/gates_tentativo1.csv`): G0 PASSA,
G1 a quota 13% **NON PASSA** (4 982,9 contro 5 263, −5,32%), G1 a quota 30% PASSA (−4,96%),
G2 PASSA (+4,18%). Causa verificata nel sorgente di PostgreSQL 16.15 (`ts_headline` senza
corrispondenza mostra 15 parole, non 30); correzione in `tools/sim/object_sizes.py`;
emendamento 1. T e M non calcolati.

**Secondo tentativo** (28 set, commit `c56ef12`, `data/sim/fase1/gates.csv`):

| cancello | simulato | lab | scarto | soglia | esito |
|---|---|---|---|---|---|
| G0 contiguita' a S12, 5 semi | 66,87% | 66,9% | −0,03 punti | ±0,5 punti | **PASSA** |
| G1 oggetti in cache, scope 0,20, quota 13% | 5 183,3 ± 5,7 | 5 263 | −1,51% | ±5% | **PASSA** |
| G1 oggetti in cache, scope 0,20, quota 30% | 5 203,4 ± 3,9 | 5 263 | −1,13% | ±5% | **PASSA** |
| G2 byte per richiesta a S12 | 25 259,3 ± 22,7 | 25 249,3 | +0,04% | ±5% | **PASSA** |

## Criteri

Commit `ef89c24`, `data/sim/fase1/criteri.csv` e `reps.csv`; 20 semi per punto.

**T1 — miss per classe** (soglia |Δ| ≤ 0,02): **18 su 18, PASSA**.

| scope | quota | classe | simulato | lab | Δ |
|---|---|---|---|---|---|
| 0,02 | 13% | umana | 0,2304 | 0,2270 | +0,0034 |
| 0,02 | 30% | umana | 0,2344 | 0,2318 | +0,0026 |
| 0,02 | 13% | esaustiva | 0,8246 | 0,8214 | +0,0032 |
| 0,02 | 30% | esaustiva | 0,7993 | 0,8000 | −0,0007 |
| 0,02 | 13% | agentica | 0,1853 | 0,1796 | +0,0057 |
| 0,02 | 30% | agentica | 0,0452 | 0,0444 | +0,0008 |
| 0,06 | 13% | umana | 0,2330 | 0,2324 | +0,0006 |
| 0,06 | 30% | umana | 0,2422 | 0,2410 | +0,0012 |
| 0,06 | 13% | esaustiva | 0,8169 | 0,8134 | +0,0035 |
| 0,06 | 30% | esaustiva | 0,8030 | 0,7998 | +0,0032 |
| 0,06 | 13% | agentica | 0,3841 | 0,3758 | +0,0083 |
| 0,06 | 30% | agentica | 0,2342 | 0,2314 | +0,0028 |
| 0,20 | 13% | umana | 0,2351 | 0,2324 | +0,0027 |
| 0,20 | 30% | umana | 0,2489 | 0,2466 | +0,0023 |
| 0,20 | 13% | esaustiva | 0,8131 | 0,8114 | +0,0017 |
| 0,20 | 30% | esaustiva | 0,7915 | 0,7884 | +0,0031 |
| 0,20 | 13% | agentica | 0,5460 | 0,5464 | −0,0004 |
| 0,20 | 30% | agentica | 0,4746 | 0,4704 | +0,0042 |

**T2 — `origin_rps`** ai 5 punti della replica (soglia 3%): **PASSA**. S12 38,017 contro 37,678
(+0,90%); S36 36,935 contro 36,706 (+0,62%); C12 37,136 contro 36,796 (+0,92%); C36 36,096
contro 35,834 (+0,73%); P0 36,605 contro 36,468 (+0,37%). Come dichiarato nella
pre-registrazione, T2 da sola non valida gli effetti.

**T3 — ampiezza delle differenze** (soglia 3 SE combinati): **PASSA** per tutte e tre.

| grandezza | simulato | lab | \|Δ\| | soglia | esito |
|---|---|---|---|---|---|
| m (S12 → S36) | −0,0451 ± 0,0033 | −0,0405 ± 0,0061 | 0,0046 | 0,0210 | PASSA |
| d₁₂ | +0,8815 ± 0,0716 | +0,8820 ± 0,1831 | 0,0005 | 0,5898 | PASSA |
| d₃₆ | +0,8388 ± 0,0806 | +0,8720 ± 0,0640 | 0,0332 | 0,3089 | PASSA |

**M1 — segno di A1**: m < 0, t = −13,49: **PASSA**.
**M2 — segno di A3**: d₁₂ t = +12,31, d₃₆ t = +10,40: **PASSA**.

**Senza soglia.** Marginali ai tre scope −0,0451 ± 0,0033 / +0,1647 ± 0,0042 / +0,4461 ± 0,0034
(lab, A1: −0,0353 / +0,1605 / +0,4383). Fattori di A2 per l'agentica 4,10 / 1,64 / 1,15 (lab
4,05 / 1,62 / 1,16). Netto S36 − P0 +0,331 ± 0,079 (lab, replica: +0,238 ± 0,110). Oggetti in
cache fra 5 151,8 (P0) e 5 231,3 (scope 0,06, quota 30%).

## Dichiarazioni

1. **Fonte dei dati del lab: copia locale.** Il lab e' stato spento dopo il backup del 28 set.
   Testi del corpus, `points.csv` e JSON di k6 sono letti da `~/undertow-backup/lab-20260928`
   (integrita' verificata con `SHA256SUMS` prima dell'uso) tramite un finto `ssh`
   (`verifica/ssh-shim`) che serve solo `cat ~/undertow/...` e l'esecuzione di
   `object_sizes.py` sulla copia. La stessa copia riproduce senza differenze
   `docs/RISULTATO-replica-20260924.md` con `tools/replica_analysis.py`. La dichiarazione e'
   anche nell'intestazione di ogni file di `data/sim/fase1/` del secondo tentativo.
   `chapter_sizes.csv` e' stato rigenerato dalla copia (`c56ef12`), non dal lab come
   scritto nell'emendamento 1: stessi file.
2. **Correzione del codice a P0, prima che fosse stampato qualunque criterio.** Il primo
   avvio del confronto (a `c56ef12`) si e' fermato calcolando le medie per punto: a P0
   (β = 0) il miss agentico non esiste (0 richieste, NaN) e `statistics.stdev` non accetta
   NaN. Nessun criterio era stato calcolato o stampato; e' stato scritto solo `reps.csv`,
   non letto. Correzione in `ef89c24`: media e SE NaN per una classe senza richieste. Nessun
   parametro, soglia o formula cambiati (regola 1 della pre-registrazione). P0 entra solo
   in T2 e nel netto.
3. **Hash diversi fra le uscite.** `gates.csv` porta `c56ef12`; `reps.csv` e `criteri.csv`
   portano `ef89c24`. Fra i due commit cambia solo la correzione del punto 2.

## Limiti

- **Miss simulato leggermente piu' alto del lab, quasi ovunque.** `origin_rps` e' piu' alto in
  5 punti su 5 (+0,37…+0,92%) e il miss per classe in 16 valori su 18. E' entro tutte le
  soglie, ma e' sistematico, non rumore. Cause possibili, non verificate: le divergenze
  dichiarate nella pre-registrazione (LRU esatto invece di `lru_interval`, byte esatti invece
  dell'allocatore di `malloc`, oggetti ricostruiti; con l'anteprima a 15 parole gli oggetti
  con corrispondenza sono sottostimati). Oggetti in cache simulati 1,1–1,5% sotto C2.
- Valgono tutte le divergenze da Varnish elencate nella pre-registrazione.
- La validazione copre **questa** configurazione (generatore di `workload.js`, LRU, 128 MiB,
  tre scope, due mappature). Non dice nulla, di per se', su altre politiche o altre sessioni:
  e' l'oggetto della fase 2.
- Stato **SIMULATO**: nessun numero di questo documento e' una misura (`claims.md`, riga S1).
