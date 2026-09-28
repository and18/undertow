# Pre-registrazione — rilancio sul lab con la traversata esaustiva in uno scenario proprio
**28 settembre 2026 — scritta e committata PRIMA del lancio.** Il commit che la contiene e'
quello che il lab esegue (hash nell'ultima riga di ogni `env.txt`). Dopo il push non si
modifica. I valori previsti vengono dal simulatore (stato SIMULATO); le misure del rilancio
saranno MISURATO. Si riporta tutto, qualunque sia l'esito.

## Il problema

`harness/load/workload.js` (fino a questo commit, ed e' ancora il default) sceglie il capitolo
esaustivo con `permuteTrav(offset + TRAV_SKIP + exec.scenario.iterationInTest)`, e
`iterationInTest` conta le iterazioni di **tutte** le classi. Lo stesso capitolo torna quindi
all'esaustiva ogni N/λ secondi (204 s a λ = 83, 142 s a λ = 119): a parita' di α·λ = 28 req/s
il percorso esaustivo dipende da λ totale, che cambia fra P0, S12 e S36.

Nel simulatore (LRU validato sul lab nella fase 1):
- **fase 2b** (`docs/PREREG-simulatore-fase2b.md`, `data/sim/fase2b/`): con un contatore
  proprio della classe il calo del miss esaustivo da P0 a S36 **resta** (−0,0315 ± 0,0007,
  |Δ|/SE 46): e' un effetto della cache, ma e' circa **meta'** (53%) di quello con il contatore
  globale (−0,0600, che coincide con il lab: 0,858 → 0,801);
- **esplorativo** (`tools/sim/esplora_artefatto.py`, `data/sim/esplorativo-artefatto/`, non
  pre-registrato): i marginali di A1 si spostano di circa 0,015 ai tre scope (cambio di segno e
  ordinamento reggono), A3 e A7 non cambiano, il netto di A9 passa da +0,33 a circa +1,1.

Toccati: **D8** (hit esaustivo che sale con la quota agentica), il **termine esaustivo di B2**,
**A9** e l'ampiezza di **A1** a scope 0,02.

## La modifica all'harness

`TRAV_MODE=scen` (`workload.js`, passato da `treclassi.sh`, registrato in `env.txt`):
l'esaustiva diventa uno **scenario k6 proprio** (`trav`, `constant-arrival-rate` a α·λ req/s)
e il suo `iterationInTest` conta solo le richieste esaustive; umana e agentica stanno nello
scenario `load` a (1 − α)·λ req/s, con agentica a probabilita' β/(1 − α). I rate sono
espressi per 10 000 s (k6 vuole un intero; scarto < 10⁻⁵ req/s). Stesso `TRAV_SKIP`
= int(300·λ·α) nella misura. Senza `TRAV_MODE` il comportamento e' quello di tutti i run
passati (un solo scenario, stessa sequenza di sorteggi).

**Dichiarato:**
- gli **arrivi esaustivi diventano regolari** (uno ogni 1/(α·λ) s) invece che estratti a caso
  iterazione per iterazione;
- l'assegnazione dei VU agentici avviene sulle sole iterazioni dello scenario `load`;
- nel simulatore la variante che riproduce questo schema (SCEN) e il contatore proprio con
  arrivi casuali (OWN) danno gli stessi risultati entro l'errore (m a 0,02: −0,0308 ± 0,0022 e
  −0,0313 ± 0,0027).

**Verifica dell'implementazione** (28 set, prima del commit): `workload.js` eseguito con
`grafana/k6:0.52.0` contro un server locale finto (λ 119, α 0,2353, β 0,3025, 30 s,
TRAV_SKIP 8400). Con `TRAV_MODE=scen` la sequenza dei capitoli esaustivi e' **identica**,
capitolo per capitolo (841 su 841), a `permuteTrav(offset + 8400 + k)` e alla variante SCEN
del simulatore; intervallo fra richieste esaustive 0,0357 s (atteso 0,0357); quota agentica fra
le non esaustive 0,406 (attesa 0,396, +1,1 SE); tutte le richieste agentiche nell'insieme di
lavoro. Senza `TRAV_MODE` ogni capitolo esaustivo corrisponde all'indice globale di iterazione,
come prima.

## Disegno

Identico alla replica del 25-26 set (`docs/PREREG-replica-20260924.md`) salvo `TRAV_MODE=scen`.

| punto | mappatura | AGENT_MUL | α | β | λ |
|---|---|---|---|---|---|
| C12 | condivisa | 2654435761 | 0,2947 | 0,1263 | 95 |
| S12 | separata | 3266489917 | 0,2947 | 0,1263 | 95 |
| S36 | separata | 3266489917 | 0,2353 | 0,3025 | 119 |
| P0 | — | 2654435761 | 0,3373 | 0 | 83 |
| C36 | condivisa | 2654435761 | 0,2353 | 0,3025 | 119 |

Ordine **C12, S12, S36, P0, C36**; `REPS=5`, `WARMUP=300`, `MEASURE_FORCE=620`, `GATE=0`,
`AGENT_SCOPE=0.02`, `TOTAL_MB` 128. Lancio: `tools/replica-own-20260928.sh`, copia di
`tools/replica-20260924.sh` con `TRAV_MODE=scen` e gli stessi controlli (harness uguale a
`HEAD`, nessun container attivo, `env.txt` a 30 s con `TRAV_MODE=scen` fra le chiavi attese,
gate a fine punto, un solo rifacimento a fine coda). **Controllo in piu'**: dopo la prima
ripetizione del primo punto, i conteggi per classe di k6 (hit + miss) devono stare entro il 2%
di α·λ·620, β·λ·620 e (1 − α − β)·λ·620, altrimenti lo script si ferma. *Nota:* a C12 il 2% per
l'agentica vale circa 1,9 deviazioni standard del campionamento binomiale (circa 6% di arresti
per solo rumore); un arresto per questo motivo si dichiara e si rilancia dall'inizio.

**Durata stimata:** circa **6 h 40 min** (80 min per punto, come la replica); ogni punto rifatto
aggiunge 80 min.

## Grandezze e calcoli

Come la replica: `origin_rps` di `points.csv` per ripetizione; Ō e SE = s/√5 per punto; SE di una
differenza √(SE₁² + SE₂²); t di Welch; rate configurati; divisore di m **23,9990**. Miss
esaustivo = 1 − `h_trav`. Solo i run di questa campagna.

## Previsioni (dal simulatore, con IC 95%)

Metodo: valore del lab nella replica del 25-26 set + variazione simulata (SCEN − contatore
globale), riscalata con k = Ō_lab / Ō_sim; IC 95% = ± 1,96 · √(SE_rif² + SE_nuova² + SE_var²),
con SE_nuova = SE_rif. Gli IC **non** includono la deriva fra giorni (R4: fino a 0,154 req/s sui
livelli). Da `data/sim/esplorativo-artefatto/criteri.csv` (commit `f684b05`).

| grandezza | replica 25-26 set | previsto | IC 95% |
|---|---|---|---|
| C12 `origin_rps` | 36,796 | 37,168 | [36,842, 37,495] |
| S12 | 37,678 | 38,057 | [37,635, 38,479] |
| S36 | 36,706 | 37,426 | [37,271, 37,580] |
| P0 | 36,468 | 36,325 | [36,000, 36,651] |
| C36 | 35,834 | 36,540 | [36,329, 36,752] |
| m a 0,02 (A1) | −0,0405 | −0,0263 | [−0,0450, −0,0076] |
| d₁₂ (A3) | +0,882 | +0,889 | [+0,355, +1,422] |
| d₃₆ (A3) | +0,872 | +0,886 | [+0,624, +1,147] |
| netto S36 − P0 (A9) | +0,238 | +1,100 | [+0,740, +1,460] |
| Δ miss esaustivo S36 − P0 | −0,0566 (0,8580 → 0,8014) | −0,0274 | [−0,0341, −0,0207] |

Δ miss esaustivo: lab 0,8580 ± 0,0022 (P0) e 0,8014 ± 0,0007 (S36); variazione simulata
+0,0292 ± 0,0011 (contatore globale −0,0600, SCEN −0,0308); nessuna riscalatura (k = 1 per un
rapporto di miss).

## Criteri (fissati ora)

- **V1 — A1.** m < 0 **e** m dentro [−0,0450, −0,0076].
- **V2 — A3.** d₁₂ > 0 e d₃₆ > 0, ciascuno con t ≥ 3, **e** ciascuno dentro il proprio IC
  ([+0,355, +1,422] e [+0,624, +1,147]).
- **V3 — A9.** netto S36 − P0 dentro [+0,74, +1,46].
- **V4 — D8 e termine esaustivo di B2.** Δ miss esaustivo S36 − P0 dentro [−0,0341, −0,0207].
- **V5 — livelli, solo descrittivo.** Per ognuno dei 5 punti si riporta se Ō cade nell'IC
  previsto; nessuna soglia, perche' la deriva fra giorni (fino a 0,154 req/s) non e' negli IC.

Ogni criterio si riporta PASSA / NON PASSA. Un criterio che non passa non si ripete e non si
reinterpreta. Si riportano anche: t di m contro zero, IC 95% del netto, Δ miss esaustivo con SE,
e il termine esaustivo di B2 (α·λ)₃₆ · miss_e(S36) − (α·λ)₁₂ · miss_e(S12) in req/s.

## Cosa non fa

Non modifica `claims.md`. L'esito si riporta; le decisioni su D8, B2, A9 e A1 si prendono dopo.
Non rimisura gli scope 0,06 e 0,20 ne' la serie di A7 (nel simulatore non cambiano segno ne'
ordinamento, o non cambiano).

## Regole

1. Stesse regole della replica: gate per ripetizione (scartate > 0 o errori > 1%), un solo
   rifacimento per punto a fine coda, nessun terzo tentativo; arresto per configurazione a 30 s.
2. Nessuna analisi prima della fine della campagna.
3. Lab: `git pull --ff-only` al commit di questo file, lancio con
   `nohup setsid bash tools/replica-own-20260928.sh > harness/results/replica-own-20260928.log 2>&1 < /dev/null &`,
   verifica di `env.txt` 30 s dopo il lancio.
