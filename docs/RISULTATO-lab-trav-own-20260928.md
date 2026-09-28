# Esito del rilancio sul lab con la traversata esaustiva in uno scenario proprio
**28 settembre 2026.** Confronto contro `docs/PREREG-lab-trav-own-20260928.md` (commit `204459c`,
pushato prima del lancio e non modificato: `git diff 204459c HEAD` su pre-registrazione e harness
e' vuoto). Analisi con `tools/trav_own_analysis.py` (commit `188b8cb`, collaudato prima della
fine della campagna sulla replica del 25-26 set, che riproduce senza differenze). Le misure sono
**MISURATO**; le previsioni con cui si confrontano sono SIMULATO. `claims.md` non e' modificato:
le decisioni si prendono dopo, sui numeri.

## Campagna

Lanciata sul lab con `tools/replica-own-20260928.sh` a `204459c` (hash nell'ultima riga di ogni
`env.txt`), inizio 13:41:41 UTC, fine 20:22:42 UTC del 28 settembre. Cinque punti nell'ordine
pre-registrato, tutti con esito gate `ok` (nessuna ripetizione con iterazioni scartate o errori
> 1%), 5 ripetizioni ciascuno, nessun punto rifatto. In ogni `env.txt`: `TRAV_MODE=scen`,
`AGENT_SCOPE=0.02`, `AGENT_MUL`, `LAMBDA` e `POINTS` come da disegno.

| punto | run | inizio (UTC) | gate |
|---|---|---|---|
| C12 | `tre-20260928-134141` | 13:41 | ok |
| S12 | `tre-20260928-150154` | 15:01 | ok |
| S36 | `tre-20260928-162206` | 16:22 | ok |
| P0 | `tre-20260928-174217` | 17:42 | ok |
| C36 | `tre-20260928-190230` | 19:02 | ok |

**Controllo dei conteggi** (prima ripetizione di C12, soglia 2%): esaustiva 17 356 contro
17 357,8 attese (−0,01%), agentica 7 502 contro 7 439,1 (+0,85%), umana 34 041 contro 34 103,1
(−0,18%): passato, lo script ha proseguito.

**Fonte dei dati per l'analisi.** Il lab e' stato spento dopo la campagna. I run sono letti dalla
copia locale `~/undertow-backup/lab-20260928-own/results/` (impronte di 1 795 file in
`~/undertow-backup/lab-20260928-own/SHA256SUMS`, calcolate prima dell'analisi) tramite un finto
`ssh` (`~/undertow-backup/shim-own/ssh`) che risponde solo a `cat ~/undertow/harness/results/...`
leggendo dalla copia. `tools/trav_own_analysis.py` non e' stato modificato.

## Verdetto: V1, V2, V3, V4 passano

| criterio | misura | soglia pre-registrata | esito |
|---|---|---|---|
| **V1** (A1) | m = **−0,0348 ± 0,0043**, t = −8,01 (df 7,90) | m < 0 e dentro [−0,0450, −0,0076] | **PASSA** |
| **V2** (A3) q = 12 | d₁₂ = **+0,926 ± 0,096**, t = 9,63 (df 7,30) | > 0, t ≥ 3, dentro [+0,355, +1,422] | PASSA |
| **V2** (A3) q = 36 | d₃₆ = **+0,800 ± 0,079**, t = 10,14 (df 6,17) | > 0, t ≥ 3, dentro [+0,624, +1,147] | PASSA |
| **V2** | | entrambi | **PASSA** |
| **V3** (A9) | netto = **+1,102 ± 0,080**, t = 13,71 (df 6,46), IC 95% [+0,909, +1,295] | dentro [+0,74, +1,46] | **PASSA** |
| **V4** (D8, B2) | Δ miss esaustivo = **−0,0324 ± 0,0015** (0,8576 → 0,8252) | dentro [−0,0341, −0,0207] | **PASSA** |

**V5 — livelli, solo descrittivo** (gli IC non includono la deriva fra giorni, fino a 0,154 req/s):

| punto | Ō misurato | IC 95% previsto | |
|---|---|---|---|
| C12 | 37,302 ± 0,057 | [36,842, 37,495] | dentro |
| S12 | 38,228 ± 0,078 | [37,635, 38,479] | dentro |
| S36 | 37,394 ± 0,069 | [37,271, 37,580] | dentro |
| P0 | 36,292 ± 0,041 | [36,000, 36,651] | dentro |
| C36 | 36,594 ± 0,038 | [36,329, 36,752] | dentro |

**Riportati senza soglia:** termine esaustivo di B2 fra S12 e S36 **−0,288 ± 0,047 req/s**
(miss esaustivo 0,8356 → 0,8252; α·λ 27,9965 → 28,0007).

## Confronto con la replica del 25-26 settembre (traversata globale) e con le previsioni

Stesso disegno, stesso ordine, stessa configurazione salvo `TRAV_MODE`. Giorni diversi (25-26 e 28
set): la deriva fra giorni misurata in R4 era fino a 0,154 req/s sui livelli.

| grandezza | replica, `glob` (MISURATO) | rilancio, `scen` (MISURATO) | previsto (SIMULATO) |
|---|---|---|---|
| m a 0,02 | −0,0405 ± 0,0061 | **−0,0348 ± 0,0043** | −0,0263 [−0,0450, −0,0076] |
| d₁₂ | +0,882 ± 0,183 | **+0,926 ± 0,096** | +0,889 |
| d₃₆ | +0,872 ± 0,064 | **+0,800 ± 0,079** | +0,886 |
| netto S36 − P0 | +0,238 ± 0,110, IC [−0,060, +0,536] | **+1,102 ± 0,080**, IC [+0,909, +1,295] | +1,100 [+0,740, +1,460] |
| miss esaustivo P0 → S36 | 0,8580 → 0,8014 (Δ −0,0566) | **0,8576 → 0,8252 (Δ −0,0324)** | Δ −0,0274 [−0,0341, −0,0207] |
| termine esaustivo di B2 | −0,551 ± 0,025 | **−0,288 ± 0,047** | (simulatore, LRU OWN: −0,303) |

Letture numeriche, senza decisioni sui claim:
- il segno negativo di m a scope 0,02 resta, con modulo di poco minore (−0,0348 contro −0,0405);
  il valore sta dentro l'IC previsto, piu' vicino alla replica che al centro della previsione;
- l'effetto della sovrapposizione (A3) resta a entrambi i tassi;
- il netto da 0 a 36 req/s agentiche passa da +0,24 (IC che contiene lo zero) a **+1,10** (IC
  [+0,91, +1,30]), come previsto;
- il calo del miss esaustivo da P0 a S36 resta ma e' circa il **57%** di quello con la traversata
  globale (−0,0324 contro −0,0566), vicino al bordo inferiore dell'IC previsto;
- il termine esaustivo di B2 si dimezza circa (−0,288 contro −0,551).

## Dichiarazioni

1. **Scostamenti dalla pre-registrazione:** nessuno nel disegno, nell'ordine, nella
   configurazione, nei gate o nelle formule. Nessun run rifatto, nessuna analisi prima della
   fine della campagna.
2. **Fonte:** copia locale con impronte e finto `ssh`, come descritto sopra; e' l'unica
   differenza operativa rispetto a `ssh lab cat`.
3. **Arrivi esaustivi regolari.** Con `TRAV_MODE=scen` l'esaustiva arriva a intervalli regolari
   invece che estratti a caso: il confronto con la replica cambia anche questo, oltre al
   contatore della traversata (nel simulatore SCEN ≈ OWN).
4. **Giorni diversi.** Il confronto con la replica e' fra giorni diversi; i criteri V1-V4 usano
   solo i run di questa campagna.

## Da decidere (non fatto qui)

Come aggiornare in `claims.md` A1 (valore a scope 0,02), A9 (netto), B2 (termine esaustivo), D8
(ampiezza del calo esaustivo) e le righe S del simulatore che citano l'artefatto; se il paper
riporta i run `scen` come primari per questi punti; se rimisurare gli scope 0,06 e 0,20 con
`TRAV_MODE=scen`.
