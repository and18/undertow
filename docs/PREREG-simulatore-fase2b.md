# Pre-registrazione — simulatore, fase 2b (artefatto della traversata esaustiva)
**28 settembre 2026 — scritta e committata prima di eseguire.** Dopo il push si modifica solo
con emendamenti datati in coda. Ogni numero ha stato **SIMULATO**. Questo controllo non
modifica `claims.md`: riporta cosa implica per D8, B2 e A9, le decisioni si prendono dopo.

## Domanda

Nel lab il miss della classe esaustiva scende da 0,858 a 0,800 passando da 0 a 36 req/s
agentiche (regge D8, un termine di B2 e in parte A9); nel simulatore scende anche (fase 2: LRU
0,859 → 0,799; S3-FIFO 0,823 → 0,742, che produce il netto −2,17). Il calo e' un effetto della
cache o un artefatto del generatore?

## Il fatto di codice che motiva il controllo

`harness/load/workload.js:276-278`: la classe esaustiva chiede
`permuteTrav(offset + TRAV_SKIP + exec.scenario.iterationInTest, N)`, e `iterationInTest` conta
le iterazioni **di tutte le classi** (`workload.js:266-270`). `permuteTrav` dipende da `i mod N`
(`workload.js:244-246`). Quindi lo stesso capitolo torna disponibile all'esaustiva ogni N
iterazioni totali, cioe' ogni N/λ secondi (204 s a λ = 83, 142 s a λ = 119), ed e' chiesto con
probabilita' α ogni volta. A parita' di α·λ = 28 req/s, il percorso esaustivo dipende da λ totale,
che cambia fra P0, S12 e S36 (83, 95, 119).

## Variante del generatore

**TRAV-OWN — contatore proprio della classe.** Identica al generatore della fase 1 (`trace.phase`)
tranne l'indice esaustivo: `permuteTrav(offset + c, N)`, dove c conta **solo le richieste
esaustive**, parte da 0 all'inizio del warm-up e **prosegue** nella misura (il crawler riprende
da dove era rimasto; nessun TRAV_SKIP). Con 28 req/s esaustive lo stesso capitolo torna ogni
N / 28 ≈ 605 s, qualunque sia λ.

La variante consuma i numeri casuali esattamente come l'originale (la scelta del capitolo
esaustivo non usa numeri casuali): **a parita' di seme, le classi di ogni iterazione e i
capitoli umani e agentici sono identici**; cambia solo il capitolo esaustivo. Il confronto
originale / TRAV-OWN e' appaiato.

**TRAV-GLOB — originale**, `trace.phase` invariato.

## Disegno

- Politiche: **LRU** (validata sul lab, fase 1) e **S3-FIFO** (fase 2), implementazioni di
  `tools/sim/cache.py` e `tools/sim/policies.py` invariate.
- Sessioni: generatore originale (Q-GEN). Mappatura separata (AGENT_MUL 3266489917).
- Punti: **P0, S12, S36 a scope 0,02**, parametri della fase 1 (λ 83 / 95 / 119; α·λ esaustivo
  27,9959 / 27,9965 / 28,0007).
- Semi **1…20**; capienza, H, warm-up, misura, dimensioni degli oggetti come nella fase 2.
- 2 politiche × 2 varianti × 3 punti × 20 semi, in un solo lancio.

**Cancello R0b (regressione).** TRAV-GLOB con LRU e con S3-FIFO deve riprodurre **esattamente**
le righe di P0, S12 e S36 di `data/sim/fase2/reps.csv` (sessione GEN, stessa politica), cifra
per cifra. Se non passa, ci si ferma.

## Grandezze

Per ogni politica e variante, con SE = deviazione standard / √20 e differenze con
SE = √(SE² + SE²):

1. miss esaustivo a P0, S12, S36; **Δ_esa = miss_esa(S36) − miss_esa(P0)** e miss_esa(S12) −
   miss_esa(P0);
2. `origin_rps` a P0, S12, S36;
3. **netto** S36 − P0 con t di Welch e IC 95% (come fase 2);
4. **termine esaustivo di B2** fra S12 e S36: (α·λ)₃₆ · miss_esa(S36) − (α·λ)₁₂ · miss_esa(S12),
   in req/s, con i rate configurati; e marginale m a scope 0,02;
5. diagnostica della traversata (senza soglia): quota di richieste esaustive della misura che
   ritrovano un capitolo gia' chiesto dall'esaustiva nella stessa ripetizione (warm-up
   compreso), e intervallo mediano in secondi fra le due richieste.

## Criterio (fissato ora)

Per ciascuna politica, con TRAV-OWN:

- se **|Δ_esa| < 3 · SE(Δ_esa)**, il calo del miss esaustivo da P0 a S36 **non e' piu'
  distinguibile da zero**: il calo e' un **artefatto del generatore**;
- altrimenti **resta**: e' un **effetto della cache** (se ne riporta il segno).

Si riportano comunque Δ_esa con TRAV-GLOB, la quota del calo originale che resta con TRAV-OWN
(Δ_OWN / Δ_GLOB) e il netto nelle due varianti. Nessun'altra soglia.

## Cosa si riporta dopo (senza toccare `claims.md`)

Per **D8** (hit esaustivo che sale con la quota agentica, lab), per il **termine esaustivo di
B2** e per **A9**: cosa implica l'esito, distinguendo fra cio' che il simulatore mostra e cio'
che resterebbe da misurare sul lab (spento). Nessuna nuova riga, nessuno stato cambiato.

## Regole

1. Codice (`tools/sim/fase2b.py`) committato prima dell'esecuzione; uscite in `data/sim/fase2b/`
   con il commit e `stato = SIMULATO` in testa.
2. Nessun parametro si tocca dopo aver visto un risultato. Un errore di codice si corregge solo
   se e' una divergenza da quanto scritto qui; si dichiara e si riesegue tutto.
3. Nessun dato del lab: tutto dal repository.
