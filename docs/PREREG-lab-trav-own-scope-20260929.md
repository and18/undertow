# Pre-registrazione — rilancio degli scope 0,06 e 0,20 con la traversata esaustiva in scenario proprio
**29 settembre 2026 — scritta e committata PRIMA del lancio.** Il commit che la contiene e' quello
che il lab esegue (hash nell'ultima riga di ogni `env.txt`). Dopo il push non si modifica. Le
previsioni vengono dal simulatore (SIMULATO); le misure saranno MISURATO. Si riporta tutto,
qualunque sia l'esito.

## Motivo

Il rilancio del 28 settembre a scope 0,02 con `TRAV_MODE=scen`
(`docs/RISULTATO-lab-trav-own-20260928.md`) ha superato V1-V5: m₀,₀₂ = **−0,0348 ± 0,0043**
(t −8,01). I marginali di A1 agli scope 0,06 e 0,20 (+0,1605 e +0,4383) vengono ancora dallo
sweep del 21-22 settembre con la traversata a indice globale. Questo rilancio li rimisura con la
traversata corretta, cosi' che i tre punti di A1 abbiano lo stesso generatore. Nel simulatore
(LRU, `data/sim/esplorativo-artefatto/`) la correzione sposta questi due marginali di circa −0,015
senza cambiare segno ne' ordinamento.

## Disegno

Stesso protocollo del 28 settembre (`docs/PREREG-lab-trav-own-20260928.md`) e dello sweep del
21-22 settembre: mappatura separata, umana 55 ed esaustiva 28 req/s fisse, agentica 12 → 36 req/s.

| punto | AGENT_SCOPE | AGENT_MUL | α | β | λ | run di riferimento (`glob`, 21-22 set) |
|---|---|---|---|---|---|---|
| S12_006 | 0.06 | 3266489917 | 0,2947 | 0,1263 | 95 | `tre-20260921-214946` |
| S36_006 | 0.06 | 3266489917 | 0,2353 | 0,3025 | 119 | `tre-20260921-230947` |
| S12_020 | 0.20 | 3266489917 | 0,2947 | 0,1263 | 95 | `tre-20260922-002958` |
| S36_020 | 0.20 | 3266489917 | 0,2353 | 0,3025 | 119 | `tre-20260922-015010` |

Ordine **S12_006, S36_006, S12_020, S36_020**: ogni coppia di uno scope e' adiacente, come nello
sweep. `TRAV_MODE=scen`, `REPS=5`, `WARMUP=300`, `MEASURE_FORCE=620`, `GATE=0`, `TOTAL_MB` 128.
Lancio: `tools/replica-own-scope-20260929.sh`, copia di `tools/replica-own-20260928.sh` con
`AGENT_SCOPE` per punto e gli stessi controlli: harness uguale a `HEAD`, nessun container attivo,
`env.txt` a 30 s (con `TRAV_MODE=scen` e `AGENT_SCOPE` attesi), conteggi per classe della prima
ripetizione del primo punto entro il 2% (a S12_006 il 2% per l'agentica vale circa 1,9 SE: circa
6% di arresti per solo rumore; un arresto si dichiara e si rilancia dall'inizio), gate a fine
punto, un solo rifacimento a fine coda. **Durata stimata: circa 5 h 20 min** (80 min per punto).

## Grandezze

Come il 28 settembre: `origin_rps` di `points.csv`; Ō e SE = s/√5; m_s = (Ō(S36_s) − Ō(S12_s))
/ 23,9990; SE di m = √(SE² + SE²) / 23,9990; differenze fra marginali con t = Δ / √(SE² + SE²).
m₀,₀₂ e' quello **misurato il 28 settembre** con `TRAV_MODE=scen` (−0,0348 ± 0,0043): giorno
diverso, come nello sweep originale, dove i tre scope erano stati misurati in giorni diversi
(21 e 22 settembre).

## Previsioni (dal simulatore, con IC 95%)

Metodo del 28 settembre: valore del lab nel run di riferimento + variazione simulata (SCEN −
indice globale, LRU, 20 semi) riscalata con k = Ō_lab / Ō_sim; IC 95% = ± 1,96 · √(2·SE_rif² +
SE_var²). La deriva fra giorni (fino a 0,154 req/s, R4) **non** e' negli IC.

| grandezza | riferimento (`glob`) | variazione simulata | previsto | IC 95% |
|---|---|---|---|---|
| S12_006 `origin_rps` | 40,098 ± 0,055 | +0,374 ± 0,068 | 40,469 | [40,269, 40,670] |
| S36_006 | 43,950 ± 0,151 | +0,019 ± 0,091 | 43,969 | [43,514, 44,424] |
| S12_020 | 42,128 ± 0,061 | +0,369 ± 0,071 | 42,496 | [42,278, 42,714] |
| S36_020 | 52,646 ± 0,116 | +0,002 ± 0,076 | 52,648 | [52,293, 53,003] |
| **m₀,₀₆** | +0,1605 | | **+0,1458** | **[+0,1251, +0,1665]** |
| **m₀,₂₀** | +0,4383 | | **+0,4230** | **[+0,4057, +0,4404]** |

**Limite dichiarato:** i valori di riferimento (+0,1605 e +0,4383) stanno gia' dentro gli IC
previsti. Lo spostamento previsto (circa −0,015) e' piu' piccolo della meta' ampiezza degli IC
(circa 0,02): questo rilancio verifica segno e ordinamento con la traversata corretta, ma **non
basta a distinguere** l'ampiezza dello spostamento dal rumore.

## Criteri (fissati ora)

- **W1 — segno.** m₀,₀₆ > 0 e m₀,₂₀ > 0, ciascuno con t ≥ 3 contro zero; insieme a m₀,₀₂ < 0 del
  28 settembre (t −8,01), il **cambio di segno** regge.
- **W2 — ordinamento.** m₀,₀₂ < m₀,₀₆ < m₀,₂₀, con t ≥ 3 per ciascuna differenza consecutiva
  (m₀,₀₆ − m₀,₀₂ e m₀,₂₀ − m₀,₀₆).
- **W3 — valori.** m₀,₀₆ dentro [+0,1251, +0,1665] **e** m₀,₂₀ dentro [+0,4057, +0,4404].
- **W4 — livelli, solo descrittivo.** Per ognuno dei 4 punti si riporta se Ō cade nell'IC
  previsto (deriva fra giorni non inclusa).

Ogni criterio si riporta PASSA / NON PASSA, senza ripetere ne' reinterpretare. Si riportano
anche, senza soglia: miss agentico ai due tassi e fattore 13% → 30% per scope (A2, B3, B4), e il
confronto con i run di riferimento.

## Regole

1. Stesse regole del 28 settembre: gate per ripetizione (scartate > 0 o errori > 1%), un solo
   rifacimento per punto a fine coda, nessun terzo tentativo; arresto per configurazione a 30 s;
   nessuna analisi prima della fine della campagna.
2. Non modifica `claims.md`: le decisioni su A1, A2, B3, B4 si prendono dopo.
3. Lab: `git pull --ff-only` al commit di questo file, lancio con
   `nohup setsid bash tools/replica-own-scope-20260929.sh > harness/results/replica-own-scope-20260929.log 2>&1 < /dev/null &`,
   verifica di `env.txt` 30 s dopo il lancio.
