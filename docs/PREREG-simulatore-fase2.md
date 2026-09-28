# Pre-registrazione — simulatore, fase 2 (politiche di sostituzione e sessioni realistiche)
**28 settembre 2026 — approvata. Scritta prima di qualunque esecuzione della fase 2.**
Una volta approvata va committata e pushata **prima** di implementare le politiche e di
generare qualunque traccia della fase 2; dopo il push si modifica solo con emendamenti datati
in coda. Ogni numero della fase 2 ha stato **SIMULATO** (`claims.md`, legenda) e non e' mai
equiparato a MISURATO.

## Domanda

La dipendenza del marginale agentico dall'ampiezza dell'insieme di lavoro (A1: segno negativo a
scope 0,02, positivo a 0,06 e 0,20) e l'effetto della sovrapposizione (A3: la mappatura separata
costa ~0,9 req/s in piu' della condivisa) reggono

- **(a)** con altre politiche di sostituzione, a parita' di generatore;
- **(b)** con sessioni agentiche realistiche, a parita' di politica (LRU);
- **(c)** con entrambe insieme?

## Base: cosa resta uguale alla fase 1

Simulatore validato nella fase 1 (`docs/RISULTATO-simulatore-fase1.md`, commit `56bb487`):
generatore di `workload.js`, oggetti da `data/derived/chapter_sizes.csv` (emendamento 1),
capienza 134 217 728 byte, footprint = corpo + H con **H = 512**, TTL 86 400 s, cache vuota a
ogni ripetizione, warm-up 300 s + misura 620 s, 20 semi per punto (**semi 1…20**), SE =
deviazione standard / √20. Stessi punti della fase 1:

| punto | λ | α | β | scope | AGENT_MUL |
|---|---|---|---|---|---|
| S12, S36 | 95 / 119 | 0,2947 / 0,2353 | 0,1263 / 0,3025 | 0,02, 0,06, 0,20 | 3266489917 |
| C12, C36 | 95 / 119 | 0,2947 / 0,2353 | 0,1263 / 0,3025 | 0,02 | 2654435761 |
| P0 | 83 | 0,3373 | 0 | — | — |

Nessun dato del lab e' necessario: tutto e' nel repository (`books.csv`, `chapter_sizes.csv`,
`honeypot_contiguity.csv`). Se servisse un file del lab, si legge dalla copia locale
`~/undertow-backup/lab-20260928` (il lab e' spento) e lo si dichiara nell'uscita.

## Fattore 1 — politiche di sostituzione

Tutte a **capienza in byte**, stessa capienza e stesso H. Parametri fissati qui; nessuna
variante adattiva. Perche' queste: S3-FIFO (SOSP '23) e SIEVE (NSDI '24), che il blog Cloudflare
del 2 aprile 2026 (<https://blog.cloudflare.com/rethinking-cache-ai-humans/>) indica come
direzione a breve termine; W-TinyLFU come politica con ammissione. **Autori, sedi e dettagli
degli algoritmi sono da verificare sui paper originali** (vedi «Verifiche richieste»); se un
dettaglio verificato diverge da quanto scritto qui, si corregge con un emendamento datato
**prima** di implementare.

**P-LRU — riferimento.** Quella della fase 1 (`tools/sim/cache.py`), invariata.

**P-SIEVE.** «SIEVE is Simpler than LRU: an Efficient Turn-Key Eviction Algorithm for Web
Caches», NSDI '24 (autori da verificare; a memoria Zhang, Yang, Yue, Vigfusson, Rashmi). Una coda FIFO, un bit `visited` per
oggetto, una «lancetta».
- Inserimento in testa, `visited = 0`. Hit: `visited = 1`, nessuno spostamento.
- Sfratto: la lancetta parte dalla sua posizione (dalla coda alla prima volta); finche'
  l'oggetto puntato ha `visited = 1`, lo azzera e avanza verso la testa (tornando alla coda
  quando arriva in testa); sfratta il primo con `visited = 0` e la lancetta resta sul suo
  successore. A byte: si sfratta finche' il nuovo oggetto entra.
- Nessun parametro.

**P-S3FIFO.** «FIFO queues are all you need for cache eviction», SOSP '23 (autori da
verificare; a memoria Yang, Zhang, Qiu, Yue, Rashmi). Tre FIFO: piccola S, principale M, fantasma G (solo chiavi).
- **S = 10% della capienza in byte**, M = 90%; G contiene al piu' tante chiavi quanti sono gli
  oggetti in M in quel momento (regola del paper, qui fissata come numero di chiavi).
- Contatore di frequenza a 2 bit (0…3). Hit in S o M: `freq = min(freq + 1, 3)`.
- Miss: se la chiave e' in G, l'oggetto entra in testa a M (e la chiave esce da G), altrimenti
  in testa a S; `freq = 0`.
- Sfratto da S (quando S supera il 10%): se `freq > 1` l'oggetto passa in testa a M con
  `freq = 0`, altrimenti esce e la chiave entra in G.
- Sfratto da M: se `freq > 0`, `freq − 1` e reinserimento in testa a M; altrimenti esce.

**P-WTLFU — politica con ammissione, variante size-aware.** Einziger, Friedman, Manes,
«TinyLFU: A Highly Efficient Cache Admission Policy», ACM Transactions on Storage, 2017, e la
variante per oggetti di dimensione diversa di Einziger et al., ACM Transactions on Storage,
2022 (titolo, autori e regola esatta da verificare).
- Finestra LRU = **1%** della capienza in byte; principale SLRU = 99%, di cui **80% protetta**
  e **20% in prova**.
- Stima di frequenza: Count-Min Sketch, **4 righe**, larghezza = potenza di 2 ≥ numero di
  oggetti del corpus (**32 768**), contatori a 4 bit (saturano a 15), hash deterministici
  con semi fissati (1, 2, 3, 4). **Reset**: dopo **10 × 5 263** richieste registrate, tutti
  i contatori si dimezzano (divisione intera). Nessun doorkeeper.
- Ogni richiesta incrementa lo sketch. Miss: l'oggetto entra in testa alla finestra. Quando
  la finestra supera l'1%, il suo ultimo oggetto e' il candidato. **Regola size-aware**: le
  vittime sono gli oggetti che andrebbero sfrattati, nell'ordine, dalla coda della parte in
  prova (e, se non bastano, dalla coda della protetta) per fare spazio al candidato; il
  candidato e' **ammesso solo se** `stima(candidato) > somma delle stime delle vittime`. Se
  ammesso, le vittime escono tutte e il candidato entra in testa alla prova; altrimenti esce
  il candidato e le vittime restano. Motivo: gli oggetti arrivano a 1,9 MB, e confrontando con
  una sola vittima un oggetto grande entrerebbe troppo facilmente. Solo questa variante,
  nessuna analisi di sensibilita'.
- Hit in prova: l'oggetto passa in testa alla protetta; se la protetta supera l'80%, il suo
  ultimo oggetto torna in testa alla prova.
- Nessuna finestra adattiva (hill climbing di Caffeine escluso).
- Un oggetto non ammesso resta un miss per il traffico che lo chiede: nessuna risposta
  stantia, come nel VCL (grace e keep a 0).

**Collaudo prima dell'uso (cancello K).** Per ogni politica, in `tools/sim/test_policies.py`,
**committato prima di qualunque traccia della fase 2**:
1. **Tracce piccole scritte a mano**, oggetti di dimensione unitaria e capienza 3-4, con la
   sequenza hit/miss attesa **derivata a mano** e scritta nel test prima di eseguirlo:
   LRU (traccia canonica); SIEVE (la lancetta che salta gli oggetti visitati e li azzera);
   S3-FIFO (oggetto visto una volta che esce da S senza toccare M; ritorno dal fantasma
   direttamente in M; oggetto con `freq > 1` promosso); W-TinyLFU (candidato respinto contro
   una vittima piu' frequente; scansione che non sposta la protetta).
2. **Invarianti su tracce casuali** (10 000 richieste, dimensioni reali): byte occupati ≤
   capienza sempre; hit ⇔ oggetto presente; con capienza ≥ somma di tutti gli oggetti, le
   quattro politiche danno esattamente i soli miss obbligatori (prima richiesta di ogni
   oggetto).
3. **Regressione (cancello R0).** Con LRU e le sessioni originali (LRU × Q-GEN), la fase 2
   deve riprodurre **esattamente** i numeri della fase 1: per tutti i 9 punti e i 20 semi,
   richieste e miss per classe, `origin_rps`, oggetti in cache e byte per richiesta
   identici a `data/sim/fase1/reps.csv` (commit `ef89c24`), gli interi uguali e i decimali
   uguali cifra per cifra come scritti nel file. Uno scarto qualunque ferma la fase 2 finche'
   non e' spiegato e corretto nel codice.

Se un test non passa si corregge il codice (non i parametri) e si ripete; se una politica non
passa, non si usa e si dichiara.

## Fattore 2 — sessioni agentiche

**Q-GEN — generatore.** Quello di `workload.js`, validato nella fase 1: sessioni di 3 capitoli
contigui da una base. Contiguita' 66,9%, ripetizioni 0%.

**Q-REAL — sessioni calibrate sull'honeypot.** Stesso insieme di lavoro, sequenza diversa.
- **Insieme e popolarita' invariati.** Una «estrazione nuova» sceglie la base come nel
  generatore (rango Zipf(0,6) sullo scope, `permuteAgent`) e poi uno scostamento uniforme
  k ∈ {0, 1, 2}: oggetto = base + k. Gli oggetti raggiungibili sono gli stessi del
  generatore (1 017 / 3 051 / 10 170 ai tre scope) e la probabilita' marginale di ogni base
  e' la stessa.
- **Sequenza per VU** (stessa assegnazione iterazione → VU della fase 1), catena a tre esiti
  per ogni richiesta agentica dopo la prima del VU nella fase:
  - con probabilita' **p_r**: stesso oggetto della richiesta precedente (ripetizione);
  - con probabilita' **p_c**: oggetto adiacente dentro lo stesso blocco di 3 (k = 0 → 1,
    k = 2 → 1, k = 1 → 0 o 2 con probabilita' 1/2);
  - altrimenti: estrazione nuova.
- **Bersagli** (`data/derived/honeypot_contiguity.csv`, classe `agent`, stessa metrica di C5):
  **4,25%** coppie contigue, **19,44%** ripetute, su 1 929 coppie.
- **Calibrazione, prima di qualunque cache.** p_r e p_c si scelgono a S12 (λ 95, β 0,1263,
  scope 0,02, mappatura separata), sola misura, **semi di calibrazione 101…105** (distinti
  da quelli sperimentali), per bisezione indipendente su ciascuna quota finche' la media sui
  5 semi e' entro 0,1 punti dal bersaglio (le estrazioni nuove possono essere contigue o
  ripetute per caso: la calibrazione lo assorbe). I valori trovati si scrivono in
  `data/sim/fase2/calibrazione.csv` e **non cambiano piu'** per tutti i punti e gli scope.
- **Cancello G0-R.** Con p_r e p_c fissati, semi 1…5, S12: contiguita' **4,25% ± 0,5 punti**
  e ripetizioni **19,44% ± 1,0 punti**. Se non passa, Q-REAL non si usa e (b) e (c) non si
  valutano.
- **Si riportano** (senza soglia): la distribuzione marginale degli scostamenti k (la catena
  sposta un po' di peso verso k = 1) e il numero di oggetti distinti toccati in 620 s a S12,
  contro Q-GEN.
- Limite gia' dichiarato in C5: sull'honeypot la sessione e' una connessione TCP, qui un VU.
  Q-REAL riproduce due statistiche di coppia, non il comportamento degli agenti reali.

## Combinazioni

8 combinazioni = 4 politiche × 2 modelli di sessione. **(a)** = {SIEVE, S3-FIFO, W-TinyLFU} ×
Q-GEN; **(b)** = LRU × Q-REAL; **(c)** = {SIEVE, S3-FIFO, W-TinyLFU} × Q-REAL. LRU × Q-GEN e'
il riferimento: deve riprodurre esattamente la fase 1 (cancello R0). Ogni combinazione: 9 punti
× 20 semi. Stesso seme = stessa sequenza di sorteggi di classe fra le politiche con la stessa
sessione (numeri casuali comuni); le formule di SE restano quelle della fase 1 (punti trattati
come indipendenti).

## Grandezze

Per ogni combinazione:

1. **m ai tre scope**: m_s = (Ō(S36_s) − Ō(S12_s)) / 23,9990, SE = √(SE² + SE²) / 23,9990.
2. **Miss umano con e senza traffico agentico**: miss umano a P0 (β = 0) e a S12 e S36 ai tre
   scope; Δ_h = miss_h(Sq_s) − miss_h(P0), con SE. Umana 55 ed esaustiva 28 req/s sono uguali
   nei tre punti, cambia solo la classe agentica. E' la metrica del blog Cloudflare citato
   sopra («allow human traffic to achieve the same hit rate with or without AI
   interference»; frase da verificare sulla pagina prima di citarla nel paper), qui espressa
   come miss.
3. **Netto P0 → 36** a scope 0,02: n = Ō(S36) − Ō(P0), IC 95% con t di Welch (come R3).
4. **d₁₂, d₃₆** a scope 0,02: Ō(Sq) − Ō(Cq).

Si riportano anche miss per classe e oggetti in cache a ogni punto.

## Criteri di lettura (decisi ora)

Per ogni combinazione, con t = valore / SE:

- **Segno negativo di A1 a scope 0,02 regge** se m₀,₀₂ < 0 e t ≤ −3; **si inverte** se
  m₀,₀₂ > 0 e t ≥ 3; altrimenti **indeterminato**.
- **Dipendenza dall'insieme di lavoro regge** se m₀,₀₂ < m₀,₀₆ < m₀,₂₀ con ciascuna differenza
  consecutiva a t ≥ 3 (Welch). Il **cambio di segno** regge se in piu' m₀,₀₂ < 0 (t ≤ −3) e
  m₀,₂₀ > 0 (t ≥ 3).
- **A3 regge** se d₁₂ > 0 e d₃₆ > 0, ciascuno con t ≥ 3; **si inverte** se uno dei due e'
  < 0 con t ≤ −3; altrimenti indeterminato.
- **Netto**: «non negativo» se t > −2 (come R3); «negativo» se t ≤ −2; IC riportato sempre.
- **Miss umano**: nessuna soglia; si riporta Δ_h con SE e segno.

Risposta alla domanda: (a) regge se i criteri di A1 (segno a 0,02 e dipendenza) e di A3
reggono per **tutte** e tre le politiche di (a); si riporta politica per politica. Stesso per
(b) con LRU e per (c) con le tre politiche. «Regge in parte» si scrive con l'elenco di cosa
regge e dove.

## Previsioni (scritte prima di eseguire)

Meccanismo di riferimento (B2, fase 1): a scope 0,02 il marginale e' negativo perche' la
crescita dell'agentica da 12 a 36 req/s riduce molto il miss delle 12 req/s gia' presenti (da
0,18 a 0,045): sotto LRU, le scansioni esaustive (28 req/s di oggetti quasi tutti visti una
volta) accorciano il tempo di permanenza, e a 12 req/s la coda dell'insieme agentico non
resta in cache.

| combinazione | m₀,₀₂ | dipendenza e cambio di segno | A3 (d₁₂, d₃₆) | netto P0 → 36 | Δ miss umano | fiducia |
|---|---|---|---|---|---|---|
| LRU × GEN (riferimento) | negativo (≈ −0,045) | reggono | positivi (≈ +0,85) | ≈ +0,33 | piccolo, positivo | alta (e' la fase 1) |
| SIEVE × GEN | verso zero; **previsto positivo o indeterminato** | dipendenza regge; cambio di segno **probabilmente no** | positivi, piu' piccoli | positivo | piu' piccolo che in LRU | media |
| S3-FIFO × GEN | come SIEVE: **positivo o indeterminato** | dipendenza regge; cambio di segno probabilmente no | positivi, piu' piccoli | positivo | piu' piccolo che in LRU | media |
| W-TinyLFU × GEN | **positivo** | dipendenza regge; cambio di segno no | positivi, piu' piccoli | positivo | il piu' piccolo | media-bassa |
| LRU × REAL | negativo, **meno** negativo che in GEN | reggono | positivi, simili a GEN | positivo, piu' piccolo che in GEN | simile a GEN | media |
| SIEVE × REAL | positivo o indeterminato | dipendenza regge; cambio di segno no | positivi | positivo | piccolo | bassa |
| S3-FIFO × REAL | positivo o indeterminato | dipendenza regge; cambio di segno no | positivi | positivo | piccolo | bassa |
| W-TinyLFU × REAL | positivo | dipendenza regge; cambio di segno no | positivi | positivo | il piu' piccolo | bassa |

**Perche'.**
- **Politiche resistenti alle scansioni (SIEVE, S3-FIFO, W-TinyLFU).** Gli oggetti esaustivi
  visti una volta escono presto (SIEVE: `visited = 0`; S3-FIFO: escono da S senza entrare in
  M; W-TinyLFU: non superano l'ammissione). Gli oggetti riusati restano piu' a lungo, quindi
  gia' a 12 req/s il miss agentico e' basso e resta poco da ridurre: il termine negativo di
  B2 si restringe e prevale il costo delle nuove richieste. Ci aspettiamo che il segno
  negativo a 0,02 sia **una proprieta' dell'LRU sotto scansione**, non delle cache condivise
  in generale. La dipendenza dall'ampiezza (marginale che cresce con lo scope) dovrebbe
  restare, perche' a scope 0,20 l'insieme agentico (1,93× la capienza) non entra con nessuna
  politica.
- **W-TinyLFU** in piu' puo' rifiutare gli oggetti agentici poco frequenti della coda Zipf:
  a scope 0,20 il marginale potrebbe essere **piu' alto** che in LRU.
- **A3.** Con la mappatura separata l'insieme agentico occupa spazio in piu' in ogni politica:
  d > 0 dovrebbe reggere ovunque; piu' piccolo con le politiche che liberano spazio dalle
  scansioni.
- **Sessioni realistiche.** Il 19,4% di ripetizioni sono quasi sempre hit (l'oggetto e'
  appena stato richiesto), a entrambi i tassi; la contiguita' non cambia la popolarita'
  degli oggetti ma solo l'ordine, e a questi tempi (secondi fra richieste dello stesso VU)
  conta poco sotto LRU. Il termine negativo di B2 e il costo delle nuove richieste si
  riducono entrambi di circa un quinto: il segno a 0,02 sotto LRU dovrebbe restare, con
  modulo minore; il netto scende.
- **Miss umano.** Sotto LRU l'agentica sposta poco la testa umana (A8: 0,20 millesimi per
  richiesta); con le politiche resistenti alle scansioni la testa umana e' piu' protetta e
  l'effetto dovrebbe essere ancora minore.

Queste previsioni **si riportano tutte**, qualunque sia l'esito. Non sono criteri di
validita' del simulatore: una previsione sbagliata e' un risultato.

## Regole

1. **Nessun parametro si tocca dopo aver visto un risultato** della fase 2 (politiche,
   capienze delle code, sketch, p_r e p_c calibrati, semi, criteri). Unica sequenza ammessa
   prima dei risultati: collaudo K, regressione R0, calibrazione Q-REAL, cancello G0-R.
2. Ordine: commit del codice e dei test → K → R0 → calibrazione → G0-R → tutte le 8
   combinazioni in un solo lancio → lettura. Nessuna combinazione si esegue o si legge da
   sola prima delle altre.
3. Un errore di codice trovato dopo si corregge solo se e' una divergenza dall'algoritmo
   descritto qui, si dichiara con il commit, e si rieseguono **tutte** le combinazioni.
4. Uscite in `data/sim/fase2/`, con commit e `stato = SIMULATO` in testa a ogni file.
5. Niente lab (spento); niente log dell'honeypot (si usa solo l'aggregato
   `honeypot_contiguity.csv`); nessun testo Gutenberg.

## Verifiche richieste (prima di implementare)

Decisioni del 28 settembre: attribuzioni come nella sezione «Fattore 1»; metrica del miss umano
dal blog Cloudflare; W-TinyLFU solo nella variante size-aware; soglie di G0-R (±0,5 e ±1,0
punti) e t = 3 approvate; cancello R0 aggiunto. Restano da verificare; se qualcosa diverge,
si emenda con una sezione datata in coda **prima** di implementare:

1. Sui paper originali: autori e sedi di SIEVE (NSDI '24), S3-FIFO (SOSP '23), TinyLFU (ACM
   TOS 2017) e della variante size-aware (ACM TOS 2022). Per S3-FIFO: soglia di promozione
   (`freq > 1`), dimensione del fantasma, reinserimento in M. Per SIEVE: movimento della
   lancetta. Per TinyLFU: periodo di reset e larghezza dello sketch. Per la variante
   size-aware: la regola di ammissione.
2. Sulla pagina del blog Cloudflare del 2 aprile 2026: data, frase citata, e l'indicazione di
   S3-FIFO e SIEVE come direzione a breve termine. La pagina non e' stata letta in questa
   sessione.
