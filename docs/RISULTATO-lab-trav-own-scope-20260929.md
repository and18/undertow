# Esito del rilancio degli scope 0,06 e 0,20 con la traversata esaustiva in scenario proprio
**29 settembre 2026.** Confronto contro `docs/PREREG-lab-trav-own-scope-20260929.md` (commit
`1147f7a`, pushato prima del lancio e non modificato: `git diff 1147f7a HEAD` su
pre-registrazione, harness e script di lancio e' vuoto). Analisi con
`tools/trav_own_scope_analysis.py` (commit `37688a5`). Le misure sono **MISURATO**; le
previsioni con cui si confrontano sono SIMULATO. `claims.md` non e' modificato.

## Campagna

Lanciata sul lab con `tools/replica-own-scope-20260929.sh` a `1147f7a` (hash nell'ultima riga di
ogni `env.txt`), inizio 06:44:11 UTC, fine 12:05:01 UTC del 29 settembre. Quattro punti
nell'ordine pre-registrato, tutti con esito gate `ok` (nessuna ripetizione con iterazioni
scartate o errori > 1%), 5 ripetizioni ciascuno, nessun punto rifatto. In ogni `env.txt`:
`TRAV_MODE=scen`, `AGENT_MUL=3266489917`, `AGENT_SCOPE`, `LAMBDA` e `POINTS` come da disegno.

| punto | run | AGENT_SCOPE | inizio (UTC) | gate |
|---|---|---|---|---|
| S12_006 | `tre-20260929-064412` | 0.06 | 06:44 | ok |
| S36_006 | `tre-20260929-080424` | 0.06 | 08:04 | ok |
| S12_020 | `tre-20260929-092436` | 0.20 | 09:24 | ok |
| S36_020 | `tre-20260929-104448` | 0.20 | 10:44 | ok |

**Controllo dei conteggi** (prima ripetizione di S12_006, soglia 2%): esaustiva 17 354 contro
17 357,8 attese (−0,02%), agentica 7 419 contro 7 439,1 (−0,27%), umana 34 120 contro 34 103,1
(+0,05%): passato.

## Tempi dello script di analisi (dichiarazione)

`tools/trav_own_scope_analysis.py` e' stato committato in `37688a5` alle **08:52:21 +0200
(06:52:21 UTC)**, cioe' dopo l'inizio del lancio (06:44 UTC) e **prima della fine** (12:05 UTC),
ed e' stato pushato alle **19:55** (ora dichiarata da Andrea), **dopo la fine** della campagna.
**Nessun risultato della campagna e' stato letto prima del commit ne' prima del push**: lo
script e' stato collaudato solo sui run dello sweep del 21-22 settembre e sul rilancio del 28
settembre, letti dalle copie locali, senza accedere al lab durante la campagna. Lo script non e'
stato modificato dopo il commit.

## Fonte dei dati per l'analisi

Il lab e' stato spento dopo la campagna. I run sono letti dalla copia locale
`~/undertow-backup/lab-20260929-own/results/` (impronte di 1 825 file in
`~/undertow-backup/lab-20260929-own/SHA256SUMS`, calcolate prima dell'analisi) tramite un finto
`ssh` (`~/undertow-backup/shim-scope/ssh`) che risponde solo a `cat ~/undertow/harness/results/...`.
Anche i run del 28 settembre (per m₀,₀₂) e quelli dello sweep del 21-22 settembre (riferimento)
sono stati serviti da questa copia; i loro `points.csv` sono identici a quelli delle copie
precedenti (`lab-20260928-own`, `lab-20260928`).

## Verdetto: W1, W2, W3 passano

m₀,₀₂ = **−0,0348 ± 0,0043** (t −8,01), ricalcolato dai run S12 e S36 del 28 settembre indicati in
`docs/RISULTATO-lab-trav-own-20260928.md` e coincidente con il valore scritto li'.

| marginale | valore | t contro zero |
|---|---|---|
| m₀,₀₂ (28 set, `scen`) | −0,0348 ± 0,0043 | −8,01 |
| m₀,₀₆ | **+0,1430 ± 0,0050** | +28,38 |
| m₀,₂₀ | **+0,4209 ± 0,0061** | +68,92 |

| criterio | misura | soglia pre-registrata | esito |
|---|---|---|---|
| **W1** segno | m₀,₀₆ > 0 (t 28,38), m₀,₂₀ > 0 (t 68,92), m₀,₀₂ < 0 | m₀,₀₆, m₀,₂₀ > 0 con t ≥ 3; m₀,₀₂ < 0 | **PASSA** (cambio di segno regge) |
| **W2** ordinamento | m₀,₀₆ − m₀,₀₂ = +0,1778 (t 26,73); m₀,₂₀ − m₀,₀₆ = +0,2778 (t 35,09) | t ≥ 3 per ciascuna differenza | **PASSA** |
| **W3** valori | m₀,₀₆ +0,1430 in [+0,1251, +0,1665]; m₀,₂₀ +0,4209 in [+0,4057, +0,4404] | entrambi dentro | **PASSA** |

**W4 — livelli, solo descrittivo** (gli IC non includono la deriva fra giorni):

| punto | Ō misurato | IC 95% previsto | |
|---|---|---|---|
| S12_006 | 40,468 ± 0,073 | [40,269, 40,670] | dentro |
| S36_006 | 43,900 ± 0,096 | [43,514, 44,424] | dentro |
| S12_020 | 42,348 ± 0,122 | [42,278, 42,714] | dentro |
| S36_020 | 52,448 ± 0,081 | [52,293, 53,003] | dentro |

## Riportati senza soglia

**Miss agentico e fattore 13% → 30%** (A2, B3, B4):

| scope | miss agentico a 12 req/s | a 36 req/s | fattore | sweep 21-22 set (`glob`) |
|---|---|---|---|---|
| 0,06 | 0,3828 | 0,2310 | **1,6571** | 1,6240 |
| 0,20 | 0,5382 | 0,4666 | **1,1535** | 1,1616 |

**Confronto con i run di riferimento** (sweep del 21-22 settembre, traversata a indice globale;
giorni diversi):

| marginale | `glob` (21-22 set) | `scen` (29 set) | differenza | previsto (SIMULATO) |
|---|---|---|---|---|
| m₀,₀₆ | +0,1605 ± 0,0067 | +0,1430 ± 0,0050 | −0,0175 ± 0,0084 | +0,1458 (spostamento −0,015) |
| m₀,₂₀ | +0,4383 ± 0,0055 | +0,4209 ± 0,0061 | −0,0174 ± 0,0082 | +0,4230 (spostamento −0,015) |

Come dichiarato nella pre-registrazione, i valori `glob` stavano gia' dentro gli IC previsti: il
rilancio verifica segno e ordinamento con la traversata corretta, non l'ampiezza dello
spostamento. Gli spostamenti osservati (−0,0175 e −0,0174) hanno il segno e l'ordine di grandezza
previsti, ma sono circa 2,1 SE, fra giorni diversi: non distinguibili dal rumore con questo
disegno.

## Quadro dei tre marginali di A1 con la traversata corretta

| scope | m (`scen`) | data | m (`glob`, claims attuale) |
|---|---|---|---|
| 0,02 | −0,0348 ± 0,0043 | 28 set | −0,0353 ± 0,0053 (replicato −0,0405) |
| 0,06 | +0,1430 ± 0,0050 | 29 set | +0,1605 ± 0,0067 |
| 0,20 | +0,4209 ± 0,0061 | 29 set | +0,4383 ± 0,0055 |

## Dichiarazioni

1. **Scostamenti dalla pre-registrazione:** nessuno nel disegno, nell'ordine, nella
   configurazione, nei gate o nelle formule. Nessun run rifatto, nessuna analisi prima della
   fine della campagna.
2. **Fonte:** copia locale con impronte e finto `ssh`; unica differenza operativa rispetto a
   `ssh lab cat`.
3. **Tempi dello script:** committato prima della fine, pushato dopo la fine, nessun risultato
   letto prima (vedi sopra).
4. **Giorni diversi:** m₀,₀₂ e' del 28 settembre, m₀,₀₆ e m₀,₂₀ del 29, come nello sweep originale
   (21 e 22 settembre).

## Da decidere (non fatto qui)

Come aggiornare in `claims.md` A1 (tre marginali con `scen`), A2, B3 e B4 (fattori a scope 0,06 e
0,20), insieme alle decisioni ancora aperte dal 28 settembre (A9, B2, D8, righe S).
