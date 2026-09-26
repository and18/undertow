# Pre-registrazione — simulatore di cache, fase 1 (validazione sul lab)
**26 settembre 2026 — approvata. Scritta prima di qualunque confronto numerico.**
Una volta approvata va committata e pushata **prima** di eseguire il confronto; dopo il push
questo file non si modifica. Ogni numero prodotto dal simulatore ha stato **SIMULATO**, mai
MISURATO, e non entra in `claims.md` come misura.

## Scopo

A1 (marginale agentico negativo a scope 0,02, mappatura separata) e A3 (la mappatura separata
costa ~0,9 req/s in piu' della condivisa) sono misurati e replicati sul lab. Resta la validita'
esterna: l'inversione di segno potrebbe dipendere dall'LRU o dalla contiguita' del generatore
(66,9% contro 4,25% dell'honeypot, C5). La pipeline lo studia con un simulatore. **Questa fase
fa solo una cosa:** costruire il simulatore e verificare che, con il generatore e la cache del
lab, riproduca le grandezze gia' misurate. Nessuna altra politica di cache, nessuna modifica
della contiguita'. Non produce claim.

## Modello simulato

**Generatore** (`tools/sim/trace.py`), riproduzione di `harness/load/workload.js` come lo
lancia `harness/load/treclassi.sh`:

- Corpus: N = 16 954 capitoli, vettore cumulativo da `data/corpus/books.csv` (identico a
  `setup_data` di k6, verificato il 24 set; vedi `tools/generator_contiguity.py`).
- Una ripetizione = Varnish riavviato (cache vuota) → warm-up 300 s → misura 620 s. Warm-up e
  misura sono due invocazioni k6: lo stato di sessione agentica riparte vuoto alla misura, la
  cache no. Si contano solo le richieste della misura.
- Arrivi: `constant-arrival-rate`, iterazione *i* al tempo *i*/λ; λ·300 e λ·620 iterazioni.
- Classe: un solo sorteggio *u*: esaustiva se *u* < α, agentica se *u* < α + β, umana altrimenti.
- Umana: `permute(min(floor(N^u), N−1))`, moltiplicatore 2654435761, SEED 42.
- Agentica: sessioni per VU di `AGENT_SESSION` = 3 capitoli contigui da una base;
  rango r = min(S−1, floor(S·u^(1/(1−0,6)))), S = floor(N·scope); base = (r·AGENT_MUL + 42) mod N.
  VU = min(max(ceil(2λ), 200), 4000); iterazione *i* al VU *i* mod VU (coda FIFO dei VU liberi,
  stessa ipotesi di `generator_contiguity.py`).
- Esaustiva: `permuteTrav(offset + TRAV_SKIP + i)`, offset = 42·7919 mod N = 10 472,
  TRAV_SKIP = 0 nel warm-up e `printf "%d"` di 300·λ·α nella misura (8 398 a λ 95, 8 400 a
  λ 119, 8 398 a λ 83); *i* e' l'indice globale di iterazione (`iterationInTest`), di tutte
  le classi.
- Casualita': `Math.random` di k6 non ha seme; il simulatore usa `random.Random(seme)` con
  semi fissati (sotto). Riproduce la distribuzione, non la sequenza.

**Cache** (`tools/sim/cache.py`), riproduzione di `harness/varnish/default.vcl.tpl`
con `-s malloc,128m`:

- Chiave = URL, nessuna normalizzazione, nessun `Vary`: un capitolo = un oggetto, condiviso
  fra le classi.
- LRU a capienza in byte: 128 MiB = 134 217 728 byte. Un miss inserisce l'oggetto in testa e
  sfratta dalla coda finche' c'e' spazio. Un hit sposta l'oggetto in testa.
- HIT se l'oggetto e' presente al momento della richiesta (`obj.hits > 0` in `vcl_deliver`).
  Latenza di fetch zero: una richiesta concorrente allo stesso oggetto e' un hit anche su
  Varnish (coda di attesa, poi consegna dello stesso oggetto).
- TTL: i capitoli escono con `max-age=86400` (`OBJECT_TTL` non impostato), grace e keep 0.
  Il TTL e' nel modello ma non scade mai dentro i 920 s di una ripetizione.
- Footprint di un oggetto = byte del corpo della risposta + H byte fissi di intestazioni e
  struttura dell'oggetto, H fissato qui: **H = 512** (nessuna taratura).

**Dimensioni degli oggetti** da `data/derived/chapter_sizes.csv` (opzione (a) della sezione in fondo, approvata).

**Uscite per ripetizione**: miss per classe = miss / richieste della classe nella misura;
`origin_rps` = miss totali / 620; numero di oggetti in cache (media sulla misura).

## Dove il modello si discosta da Varnish (dichiarato prima)

1. Varnish sposta un oggetto in testa all'LRU solo se l'ultimo spostamento e' piu' vecchio di
   `lru_interval` (2 s di default): non e' un LRU esatto. Il simulatore si'.
2. Allocazione in `malloc`: segmenti, arrotondamenti dell'allocatore, sfratti che possono
   liberare piu' del necessario. Il simulatore conta byte esatti con H fisso.
3. Le dimensioni degli oggetti sono ricostruite, non lette dalla cache (vedi in fondo).
4. Latenza zero e ordine delle richieste = ordine degli arrivi. Nel lab una risposta lenta puo'
   riordinare di pochi ms richieste vicine.
5. Assegnazione iterazione → VU in giro: ipotesi, non misura (conta solo per la classe agentica).
6. Ignorati: la richiesta `/library` di `setup()` (un oggetto), le iterazioni scartate e le
   richieste fallite (0,008% nel run S12 della replica).
7. Nel lab `h_*` e `origin_rps` di `points.csv` sono arrotondati a 3 e 2 decimali per
   ripetizione; il simulatore non arrotonda. Le medie del lab si usano come sono.

## Controlli preliminari (gate, prima del confronto)

Si valutano nell'ordine G0, G1, G2, prima di calcolare qualunque grandezza di T1–T3 e M1–M2.

**Ricalibrazione ammessa, una sola volta.** Se G1 o G2 non passano con H = 512 e 250 byte, e'
ammessa **una** ricalibrazione di queste due costanti, usando **solo** G1 e G2, prima di
qualunque calcolo di T1–T3 e M1–M2. Si documenta in questo file (sezione aggiunta in coda,
datata) con i valori prima e dopo e con l'esito di G1 e G2 prima e dopo. Nessun altro
parametro si ricalibra. Se un cancello non passa anche dopo la ricalibrazione, ci si ferma:
il confronto non si esegue e si riporta lo scarto. Dopo aver visto una qualunque grandezza di
T o M nessun parametro si tocca.

- **G0 — generatore.** La contiguita' (metrica di C5) delle tracce del simulatore a S12
  (λ 95, β 0,1263, scope 0,02, AGENT_MUL 3266489917), sola fase di misura, 5 semi:
  **66,9% ± 0,5 punti** (valore di `data/derived/generator_contiguity.csv`: 66,89%, min 66,71,
  max 67,05). Nota: e' un controllo di codice, non una validazione indipendente, perche'
  `generator_contiguity.py` usa lo stesso algoritmo.
- **G1 — dimensioni, capienza.** Oggetti in cache nel simulatore, media sulla misura, ai due
  punti a scope 0,20: entro **±5%** di C2 = **5 263** (`data/derived/cache_capacity.csv`).
- **G2 — dimensioni, byte per richiesta.** Byte medi ricevuti per richiesta nel simulatore
  (corpo + intestazioni di risposta stimate, 250 byte) contro `data_received / http_reqs` dei
  JSON di k6 del run S12 della replica (`tre-20260925-225538`, 5 ripetizioni; 25 253 byte nella
  ripetizione 1): entro **±5%**.

## Grandezze da riprodurre

Semi: **20 ripetizioni simulate per punto**, semi 1…20; SE = deviazione standard / √20.

**T1 — miss per classe**, 18 valori di `data/derived/class_miss_by_scope.csv` (scope 0,02 /
0,06 / 0,20 × quota 13% e 30% × umana, esaustiva, agentica; mappatura separata, run del 21-22
set). Regge se **|miss_sim − miss_lab| ≤ 0,02** per tutti e 18. Si riporta anche quanti sono
entro la soglia e il fattore 13%→30% per classe (senza soglia).

**T2 — `origin_rps`**, ai 5 punti della replica (`docs/RISULTATO-replica-20260924.md`, R4,
colonna «Ō nuovo»): S12 37,678 · S36 36,706 · C12 36,796 · C36 35,834 · P0 36,468.
Regge se **|Ō_sim − Ō_lab| / Ō_lab ≤ 3%** a tutti e 5.
*Limite dichiarato:* il 3% vale circa 1,1 req/s, piu' degli effetti da validare (circa 0,9 req/s
per A3, circa 1,0 req/s fra S12 e S36). T2 da sola quindi **non valida gli effetti**: li validano
T3, M1 e M2.

**T3 — ampiezza delle differenze** (stessi run della replica, formule di R1 e R2):
- m = (Ō(S36) − Ō(S12)) / 23,9990; lab −0,0405 ± 0,0061;
- d₁₂ = Ō(S12) − Ō(C12); lab +0,882 ± 0,183; d₃₆ = Ō(S36) − Ō(C36); lab +0,872 ± 0,064.
Regge ciascuna se **|x_sim − x_lab| ≤ 3·√(SE_sim² + SE_lab²)** (la regola di R1(b)).

## Criteri minimi

- **M1 — segno di A1.** m_sim < 0 **e** t_sim = m_sim / SE_sim ≤ −3.
- **M2 — segno di A3.** d₁₂,sim > 0 e d₃₆,sim > 0, **ciascuno** con t_sim ≥ 3.

Mappatura: T1 e M1 usano solo punti separati; M2 e T3 (d) confrontano separata e condivisa,
che e' l'oggetto del test. Nessun altro confronto le mescola.

## Esito e uso nella fase 2 (deciso ora)

- G0, G1, G2 non passano → confronto non eseguito, simulatore non valido.
- M1 o M2 non passa → simulatore **non valido** per la fase 2. Ci si ferma e si descrive lo
  scarto.
- M1 e M2 passano, T1–T3 tutti passano → valido per segni e ampiezze.
- M1 e M2 passano, almeno uno fra T1–T3 no → valido **solo per i segni**; ogni risultato
  della fase 2 lo dichiara.

Riportati senza soglia: marginali agli scope 0,06 e 0,20 (con i run di A1), netto S36 − P0
(A9), fattori di A2, oggetti in cache a tutti i punti.

## Regole

1. Nessun parametro si cambia dopo aver visto un confronto: H, capienza, ipotesi sui VU, semi,
   soglie sono quelli scritti qui. Unica eccezione: la ricalibrazione di H e dei 250 byte
   descritta nei controlli preliminari, una volta, solo su G1 e G2. Un errore di codice trovato dopo si corregge solo se e' una
   divergenza dal comportamento di `workload.js` / VCL gia' descritto qui, e si dichiara.
2. Ogni criterio si riporta PASSA / NON PASSA, anche se fallisce.
3. Lab in sola lettura: `ssh lab 'cat ...'` per `points.csv`, `env.txt` e JSON di k6;
   `tools/sim/object_sizes.py` per le dimensioni (legge i testi sul lab, stampa solo numeri).
   Nessun log dell'honeypot. Nessun testo Gutenberg esce dal lab.
4. Le uscite vanno in `data/sim/fase1/` con il commit del simulatore in testa a ogni file e
   la colonna `stato = SIMULATO`.

## Dimensioni degli oggetti — scelta: opzione (a)

La cache e' a capienza in byte e il corpus e' a coda pesante (testo: mediana 9,5 KB, media
15,0 KB, massimo 1,9 MB; footprint in cache 438 MB / 16 954 ≈ 25,9 KB): servono le dimensioni
per capitolo, che il repository non ha. Opzioni:

- **(a) Ricostruzione sul lab, sola lettura (proposta).** Uno script (`tools/sim/object_sizes.py`)
  eseguito con `ssh lab 'python3 -' < tools/sim/object_sizes.py` legge `~/undertow/cache`
  (`catalog.json` + testi) con la logica di `harness/app/load_corpus.py` (split, grafo dei link
  con seme 42) e ricostruisce la risposta JSON di `/book/<id>/ch/<n>` come la serializza Flask;
  stampa **solo** `book_id, n, byte`. Non avvia il database e non scrive nulla sul lab
  (nemmeno `__pycache__`). L'anteprima di `ts_headline` non e' riproducibile senza
  PostgreSQL: stimata con le prime 30 parole del capitolo di destinazione. Controllo: libri e
  numero di capitoli ricostruiti devono coincidere con `data/corpus/books.csv`. Ipotesi: il
  database del lab e' stato caricato dai testi attuali di `~/undertow/cache` con la versione
  attuale di `load_corpus.py` (12 link per capitolo, `54f5cf7`); non verificabile senza
  interrogare il database. **Scelta approvata**; risultato in `data/derived/chapter_sizes.csv`.
- **(b) Dimensione uniforme.** Nessun accesso ai testi; ogni oggetto 134 217 728 / 5 263 byte
  (C2). Equivale a un LRU a numero di oggetti; perde la coda pesante.
- (c) Interrogare PostgreSQL sul lab: richiede di avviare il container del database, quindi
  e' una modifica dello stato del lab. Esclusa.
