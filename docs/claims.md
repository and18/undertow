# claims.md — mappa claim / stato / evidenza
**Versione 3.2, 24 settembre 2026.** Sostituisce la v3.1, la v3 e la v2. Ogni frase del paper deve
appartenere a una riga di questa tabella; se non ci appartiene, non entra.

**Cambiato il 24 settembre (v3.2, B3/B4/B5 dalle medie).** I CSV di FIG-A1 e FIG-A2, ora
generati da `tools/figA_data.py`, ricalcolano i valori dalle medie delle ripetizioni (regola
v3: rapporti ed elasticita' dalle medie, mai da valori arrotondati). Cambiano tre righe:
**B3** elasticita' osservata a scope 0,06 **1,62** invece di 1,63 (1,6240; scarto dalla
previsione 3,1 **−48%** invece di −47%); **B4** monotonia **4,05 > 1,62 > 1,16**; **B5**
p99 umano **+37,0 ± 1,0 ms, t = 37,3** invece di +36,9 e t = 36, origine **da 36,8 a
52,6 req/s** invece di 52,7. Nessuno stato cambia. Le didascalie di FIG-A1 e FIG-A2 sono
calcolate dal CSV. **C3**: la finestra di 143 s resta; nota aggiunta nella riga (parametro
fissato con C2 = 5 274, con 5 263 sarebbe 142 s, scarto 0,2%, non ricalcolato).

**Cambiato il 24 settembre (v3.2: C2 aggiornata, A9 nuova, «previsione precedente»).**
(1) **C2 = 5 263 ± 8 oggetti**, oggetto medio 24,9 KB: media di `varnish_main_n_object`
sulle 10 finestre sature dei run a scope 0,20 (`tools/cache_capacity.py`). Il 5 274 usato
fino alla v3.1 era l'output non archiviato di `harness/load/capacity.sh` (`decisions.md`
§30). I rapporti di A1 restano 0,19× / 0,58× / 1,93×. I CSV di FIG-01, FIG-A1 e FIG-A2
sono generati da script (`tools/fig01_data.py`, `tools/figA_data.py`) con questo divisore.
(2) **A9 nuova**: il netto 0 → 36 req/s non e' un risparmio, ricalcolato dalle ripetizioni
con `tools/net_agentic.py`. (3) **La previsione di B3 e B4 diventa «previsione
precedente».** Fatti: il lab e' in UTC; il primo run a scope 0,06 (`tre-20260921-214946`)
e' stato lanciato alle 21:49:46 UTC (`env.txt`), il suo primo risultato (`m-…-1.json`) e'
delle 22:05:53 UTC; il file `docs/PREREGISTRAZIONE-scopesweep.md` porta l'intestazione
«21 settembre 2026, 23:50» senza fuso orario ed e' in git solo dal 23 settembre
(`c961151`); sul lab non ce n'e' una copia. La previsione e' quindi descritta come scritta
prima che fossero disponibili i primi risultati a scope 0,06 e 0,20, senza marca
temporale indipendente; nel paper, «prior prediction». Il punto a scope 0,02 era gia'
misurato e resta l'ancora.

**Cambiato il 24 settembre (v3.1: A1 tracciata, C2 verificata).** Nessun valore di A1
cambiato. (1) I parametri di disegno di A1 entrano nella riga, letti da `env.txt` e
`points.csv` dei sei run con `tools/scope_ttest.py`: rate offerti configurati umana
55,005 / 55,002, esaustiva 27,9965 / 28,0007, agentica 11,9985 → 35,9975 req/s;
`AGENT_MUL = 3266489917` in tutti e sei; a scope 0,02 `AGENT_SCOPE` non e' in `env.txt` e
vale il default 0,02 di `treclassi.sh`. Oggetti: **1 017 / 3 051 / 10 170**, quelli che il
generatore puo' toccare (`floor(16 954 × scope)` basi × 3 capitoli, `workload.js`), non il
nominale continuo 1 017 / 3 052 / 10 172 usato prima. (2) t di Welch fra scope
consecutivi, dalle 5 ripetizioni per run: **22,99** (0,02 → 0,06, df ≈ 10,6) e **32,13**
(0,06 → 0,20, df ≈ 10,2); lo script riottiene i marginali di A1 (−0,03525 / +0,16051 /
+0,43827). (3) C2 verificata da fonte rintracciabile: il valore 5 274 era annotato solo in
`docs/decisions.md` §30 (output di `harness/load/capacity.sh`, mai archiviato);
`tools/cache_capacity.py` rilegge `varnish_main_n_object` da VictoriaMetrics nelle 10
finestre di misura dei due run a scope 0,20 (cache satura: 26 000-33 000 evizioni LRU per
finestra, ~32 KB liberi su 134 MB) e da' **5 263,0 ± 8,4** oggetti (−0,21% da 5 274),
oggetto medio 24,90 KiB (`data/derived/cache_capacity.csv`). Scarto sotto il 2%: i
rapporti 0,19× / 0,58× / 1,93× restano. `data/derived/fig01_marginal_vs_workingset.csv`
ora e' generato da `tools/fig01_data.py`, non piu' a mano.

**Cambiato il 24 settembre (ricalcolo A7/A8).** Il marginale di A7 e la pendenza di A8
usavano come divisore il passo nominale arrotondato (14 e 42 req/s). Ricalcolati con il
rate offerto configurato della classe esaustiva, α·λ letto da `points.csv` dei run
`tre-20260916-013722/-025527/-041332/-053137` (α·λ = 0 / 13,9968 / 27,9965 / 41,9977, non
esattamente 0/14/28/42), con SE dalle 3 ripetizioni: A7 da 0,959 ± 0,009 · 0,998 ± 0,010 ·
0,985 ± 0,004 a **0,961 ± 0,009 · 0,997 ± 0,010 · 0,979 ± 0,004** (elasticita' invariata,
1,0889 arrotonda comunque a **1,09×**); A8 da 1,50 a **1,52** millesimi di miss umano per
richiesta esaustiva (SE 0,02 millesimi). Scostamenti piccoli perche' α·λ era gia' vicino
al nominale per disegno.

**Cambiato il 24 settembre (C1 tracciato).** I coefficienti precedenti di C1
(`CPU = 0,106 + 0,0345 × origin_rps`, R² = 0,998, residuo max 3,4%) non avevano una fonte
rintracciabile nel repository. Ricalcolati con `tools/cpu_validation.py`, che legge i
`points.csv` delle 5 politiche della frontiera del 19 settembre (A, B, C, D4, D6, gia' usate
in FIG-03/FIG-05) e interroga VictoriaMetrics su `node_cpu_seconds_total{cpu=~"3|4|5",
mode!="idle"}` (core 3-5 = PostgreSQL, `harness/.env`: `CPUSET_DB=3,4,5`, `CPUSET_APP=2`;
i default "3,4"/"5" di `harness/docker-compose.yml` non sono quelli in uso) sulla finestra
di misura di ciascuna ripetizione, mediando le 3 ripetizioni per politica. Nuovi valori: **CPU = 0,021 +
0,0368 × origin_rps**, R² = **0,997**, residuo max **3,1%** (dati in
`data/derived/fig06_cpu_validation.csv`).

**Stati.** `MISURATO` = differenza diretta con ripetizioni ed errore standard ·
`SOSTENUTO` = inferenza stretta da misure, con meccanismo · `INTERPRETATIVO` = coerente
con i dati, non verificato come previsione · `SFIDATO` = assunzione altrui che i nostri
dati mettono in discussione · `NON SOSTENUTO` = i dati non bastano ·
`RESPINTO` = testato e fallito · `RITIRATO` = affermato da noi e poi smentito.

**Cambiato dalla v2 (correzioni numeriche, nessun claim nuovo).** Il punto a scope 0,02 di A1 e B5 usava i valori di origine e p99 dei run a **mappatura condivisa** del 20 set invece di quelli separati del 21 set (`tre-20260921-150237`/`-162248`, `AGENT_MUL=3266489917`, verificato sui `points.csv` il 23 set). Ricalcolato dalle 5 ripetizioni: A1 da −0,0477 a **−0,0353 ± 0,0053** (t = −6,7, il segno regge); B5 da 75,9 a **76,1 ms** e origine da 35,8 a **36,8 req/s**; A2 **4,05×** invece di 4,09× (4,09 era il rapporto di valori gia' arrotondati, 0,180/0,044; 4,05 e' il rapporto delle medie); A8 mescolava un miss umano condiviso (0,223) con uno separato (0,232) ed e' ricalcolata. Coerenza verificata: il marginale di A1 a scope 0,02 coincide ora con la scomposizione contabile di B2 (−0,846 / 24 req/s).

**Cambiato dalla v1:** A4 chiusa con le barre d'errore · A2 ristretta da Zhang et al. ·
**A7 nuova**, che chiude il caveat «avete variato il volume di una sola classe» ·
**A8 nuova** sull'esternalita' differenziale · B3 e B4 con la catena Fagin → Che →
Fricker · C6 con il riferimento IETF · tre nuove righe in E.

---

## A. Claim primari — possono stare nell'abstract

| # | claim | stato | evidenza | cosa lo falsificherebbe |
|---|---|---|---|---|
| **A1** | Il costo marginale della classe agentica **cambia segno** al variare dell'ampiezza del suo insieme di lavoro, a parita' di classe, volumi, cache e corpus: **−0,0353 ± 0,0053 → +0,1605 ± 0,0067 → +0,4383 ± 0,0055** richieste all'origine per richiesta | **MISURATO** | sweep AGENT_SCOPE 0,02 / 0,06 / 0,20 (1 017 / 3 051 / 10 170 oggetti, 0,19× / 0,58× / 1,93× la capienza C2), mappatura separata, 5 rip. per punto; agentica 12 → 36 req/s, umana 55 ed esaustiva 28 fisse; **t di Welch fra scope consecutivi 22,99 e 32,13**; `tre-20260921-150237`/`-162248`, `tre-20260921-214946`/`-230947`, `tre-20260922-002958`/`-015010`; `tools/scope_ttest.py` | un difetto di disegno che faccia variare altro oltre lo scope; ripetizione con esito diverso |
| A9 | A scope 0,02 il netto dell'aggiunta della classe agentica da 0 a 36 req/s **non e' un risparmio**: **+0,392 ± 0,158** req/s all'origine, IC 95% **[+0,02, +0,76]** (t di Welch = 2,48, df = 7,35) | **MISURATO** | `tre-20260920-102015` (β = 0) e `tre-20260921-162248` (β·λ = 36), 5 rip. ciascuno, **run di giorni diversi (20 e 21 set)**; λ ricostruito dai conteggi per classe nei JSON di k6 del run a β = 0 (umana 54,92, esaustiva 28,08, λ = 83,00 req/s), perche' il run e' anteriore a `env.txt`; `tools/net_agentic.py` | netto significativamente negativo in ripetizione |
| A2 | Nel banco, la sensibilita' del costo per richiesta al **proprio** volume differisce fortemente fra classi coesistenti: agentica **4,05×** (miss 0,180 → 0,044), esaustiva 1,03×, umana 1,02× | **MISURATO** | separazione working-set, 21 set, 5 rip. | rapporti simili fra le tre classi in ripetizione |
| | *nota di posizionamento* | | Zhang et al. SoCC '25 variano gia' la composizione (0-100% AI) misurando l'**hit ratio**; il nostro apporto e' il **costo marginale all'origine** e il confronto fra tre classi | |
| **A7** | Variando il **proprio** volume da 0 a 42 req/s a umano e agente fissi, il costo marginale della classe **esaustiva** e' **piatto a ~0,98** (0,961 ± 0,009 · 0,997 ± 0,010 · 0,979 ± 0,004) e la sua elasticita' e' **1,09×** | **MISURATO** | serie crawler, 16 set, 4 punti, 3 rip., finestra 1211 s | marginale esaustivo non piatto in ripetizione |
| | *perche' conta* | | **Chiude il caveat di A2.** L'asimmetria non e' un artefatto dell'aver variato il volume di una sola classe: entrambe sono state variate sul proprio volume, con metodologia identica, e si comportano in modo opposto | |
| **A8** | A parita' di richiesta aggiunta, la classe **esaustiva** degrada il miss umano **molto piu'** della classe agentica: **1,52** millesimi di miss umano per richiesta esaustiva contro **0,20** per richiesta agentica (mappatura separata; ~0 sotto mappatura condivisa) | **MISURATO la direzione**; il fattore (~7×) non e' appaiato: serie diverse per mappatura e finestra | serie crawler 16 set (miss umano 0,173 → 0,236 su +42 rps, condivisa, 1211 s) contro separazione 21 set (0,227 → 0,232 su +24 rps) | un fattore invertito su serie appaiate |
| A3 | La sovrapposizione fra l'insieme di lavoro di una classe e la testa popolare di un'altra fa apparire quella classe piu' economica: **+0,714 e +1,012 req/s** all'origine, **t = 5,74 e 7,74**, rimuovendola | **MISURATO** | condivisa contro separata, stessi α e β | ripetizione senza differenza |
| | *nota di posizionamento* | | Zhang et al. fissano l'overlap al 10-20% **senza variarlo**; FairRide tratta il free-riding come **equita'**, non come bias di misura | |
| **A4** | Al ginocchio, bloccare la classe agentica oltre a quella esaustiva serve **2 807 ± 185 richieste in meno** (t = 15,19) con una differenza di p99 umano di **+0,03 ± 0,73 ms**, IC 95% **[−1,99, +2,05] che contiene lo zero** | **MISURATO** | politiche B e C a λ = 185, 3 rip. | barre d'errore che rendano significativa la differenza di latenza |
| A5 | Bloccare una richiesta esaustiva libera ~**0,82** richieste all'origine, una agentica ~**0,10** al punto operativo della frontiera | **SOSTENUTO** | miss ratio misurati, marginale agentico, e A7 che conferma ~0,98 per l'esaustiva a volume proprio | — |
| A6 | Blocco e rinvio giacciono su un'unica curva convessa a pendenza monotona: parametrizzazioni dello stesso scambio, non politiche alternative | **MISURATO** | 8 punti, λ = 185, pendenze 0,01 → 102,25 ms/1000 | un punto fuori curva |

## B. Claim di meccanismo

| # | claim | stato | evidenza | cosa lo falsificherebbe |
|---|---|---|---|---|
| B1 | Il comportamento dipende dall'interazione fra volume della classe, ampiezza del suo insieme di lavoro e capienza della cache — non dall'etichetta. Catena: **pattern di accesso → geometria dell'insieme → interazione con lo stato condiviso → costo marginale** | **SOSTENUTO** | A1, A2 e A7 congiunti | una classe con stesso volume e stesso insieme che si comporta diversamente |
| B2 | Nel tratto 12 → 36 req/s a scope 0,02 il termine dominante e' l'**auto-localita' delle agentiche gia' presenti** (−1,632 su −0,889 totali) | **MISURATO** | scomposizione contabile, chiude a 0% e 5% | scomposizione che non chiude |
| B3 | L'approssimazione del tempo caratteristico — **Fagin 1977** (origine), **Che et al. 2002** (riscoperta e nome), **Fricker, Robert, Roberts 2012** (formalizzazione) — **predice quantitativamente** l'elasticita' | **RESPINTO** | previsione scritta prima che fossero disponibili i primi risultati a scope 0,06 e 0,20, senza marca temporale indipendente (21 set): previsti 3,1 e 1,4, osservati 1,62 e 1,16 (scarto −48% a scope 0,06, fuori dalla tolleranza ±30%); criterio 3 fallito | — |
| B4 | La stessa approssimazione **spiega qualitativamente** il regime e l'ordinamento: piu' grande l'insieme, minore l'elasticita' | **INTERPRETATIVO** | monotonia 4,05 > 1,62 > 1,16; r(0,20) < 2,0 | rapporti non monotoni in un'altra configurazione |
| B5 | La degradazione del p99 umano al crescere dello scope (**76,1 → 113,0 ms, +37,0 ± 1,0 ms, t = 37,3**) e' carico all'origine, non spostamento di cache: miss umano 1,06×, origine da 36,8 a 52,6 req/s | **SOSTENUTO** | sweep scope, quota 30% | hit umano in calo proporzionale al p99 |
| B6 | Il canale preciso della contesa a monte (Varnish, connessioni, pool di thread) | **NON SOSTENUTO** | inferito per esclusione; coda per stadio mai misurata | — |

## C. Claim di validita' e taratura

| # | claim | stato | evidenza |
|---|---|---|---|
| C1 | Il lavoro all'origine e' proxy validato del carico di backend **su questo banco**: `CPU = 0,021 + 0,0368 × origin_rps`, R² = 0,997, residuo max 3,1% | **MISURATO** | 5 politiche, intervallo di carico 4,5× |
| C2 | Capienza della cache **5 263 ± 8 oggetti**, oggetto medio **24,9 KB** | **MISURATO** | `varnish_main_n_object` da VictoriaMetrics, media delle 10 finestre di misura sature dei run a scope 0,20 (`tools/cache_capacity.py`, `data/derived/cache_capacity.csv`); il 5 274 precedente era l'output non archiviato di `harness/load/capacity.sh` |
| C3 | Il punto sperimentale piu' basso (scope 0,02, λ = 12) tocca **~693 oggetti distinti in 143 s**; il **p90** dei client agentici dell'honeypot nella stessa finestra e' **670** | **MISURATO** | calcolo sul generatore + `honeypot_window.py`. *Nota:* la finestra di 143 s e' un parametro fissato con C2 = 5 274 (T_C = 5 274 / 37 req/s); con C2 = 5 263 sarebbe 142 s, scarto 0,2%, non ricalcolato |
| C4 | Il costo di una classe misurato **in isolamento** non predice quello in mistura: la classe agentica sola a cache calda ha miss **0,002**, in mistura al 13% di quota ha miss **0,180** | **MISURATO** | `tre-20260911-154109` contro separazione |
| C5 | Il generatore assume 3 capitoli **contigui**; la contiguita' osservata per la classe `agent` e' **4,3%** | **MISURATO — divergenza dichiarata** | honeypot, 1 929 sessioni |
| C6 | Il **3,83%** delle richieste honeypot porta una firma Web Bot Auth, tutte da `other-bot` (8,80% di quella classe), **zero** dagli agenti dichiarati | **MISURATO** | `sig_agent`/`sig_input`, 520 038 richieste; `draft-ietf-webbotauth-httpsig-protocol-00`, 1 set 2026, su RFC 9421 |
| C7 | Il risultato e' invariante alla durata della finestra: origine 39,84 / 40,03 / 40,28 su finestre di 620 / 1860 / 3720 s | **MISURATO** | 14 set, controlli di durata |

## D. Claim sull'infrastruttura — implicazioni, non tecnologie

| # | claim | stato | evidenza | nota |
|---|---|---|---|---|
| D1 | Una politica che sa solo «questo e' traffico agentico» non possiede necessariamente informazione sufficiente a stimarne l'impatto marginale | **SFIDATO** | A1: stessa etichetta, marginale da −0,035 a +0,438 | **claim centrale del paper** |
| D2 | La classificazione resta necessaria e utile: al ginocchio il blocco per identita' della classe esaustiva e' sulla frontiera | **MISURATO** | politica B | impedisce la lettura «la classificazione fallisce» |
| D3 | Durante la transizione la classificazione puo' essere necessaria ma **non e' necessariamente sufficiente** | **SOSTENUTO** | D1 + D2 | formulazione da usare, non piu' forte |
| D4 | L'infrastruttura dovrebbe poter osservare o derivare l'**ampiezza dell'insieme di lavoro** di una classe | **IMPLICAZIONE** | A1 | la piu' sostenuta |
| D5 | ...e il suo **costo marginale** nello stato corrente | **IMPLICAZIONE** | A1, A5, A7 | sostenuta |
| D6 | ...e l'**effetto sugli altri workload** | **IMPLICAZIONE** | B5, A8 | sostenuta |
| D7 | ...e lo **stato condiviso** e la **pressione sulle risorse** | **IMPLICAZIONE DEBOLE** | indiretta | meno enfasi delle altre tre |
| D8 | Isolare la classe agentica in una cache separata rimuoverebbe un beneficio misurato | **SOSTENUTO** | hit esaustivo 0,179 → 0,200 al crescere della quota agentica, sotto separazione | chiude la domanda sulla cache separata |

## E. Claim che NON facciamo

| claim | stato | perche' |
|---|---|---|
| Il traffico agentico del Web e' generalmente benigno | **NON SOSTENUTO** | un honeypot, 31 client `agent`, una popolazione, una finestra |
| Il traffico agentico e' intrinsecamente costoso | **RESPINTO** | A1: il segno dipende dall'insieme di lavoro |
| Il traffico agentico e' sempre cache-friendly | **RESPINTO** | miss 0,546 a scope 0,20 |
| Il traffico agentico fa risparmiare lavoro all'origine | **RITIRATO** | netto 0 → 36 positivo: +0,392 ± 0,158 |
| Le politiche basate sulla classe falliscono | **RESPINTO** | D2 |
| Le politiche statiche sono obsolete | **RESPINTO** | adeguate per 2 classi su 3 nel banco |
| L'architettura Web attuale e' inadeguata | **NON DIMOSTRATO** | nessuna prova end-to-end |
| Serve un nuovo protocollo o una nuova architettura | **NON DIMOSTRATO** | lavoro futuro |
| Il controllo in retroazione e' una novita' | **RESPINTO** | Breakwater, UCP, Cliffhanger |
| Abbiamo un nuovo modello di cache | **RESPINTO** | il modello e' di Fagin e Che |
| Il rinvio domina il blocco | **RITIRATO** | A6: stessa frontiera |
| B domina C in senso di Pareto | **RITIRATO** | Δ p99 = +0,03 ± 0,73 ms |
| Esiste un confine di residenza a 681 oggetti | **RITIRATO** | capienza sbagliata di 7,75× |
| Sotto 1,1× di escursione basta un costo fisso | **RITIRATO** | soglia mai misurata |
| Soglia universale di utilizzazione ρ ≈ 0,9 | **RESPINTO** | il ginocchio varia con la configurazione |
| **Il cambiamento Cloudflare del 15 settembre 2026 e' un blocco di default generalizzato** | **RESPINTO** | vale per i nuovi domini in onboarding e solo sulle pagine con annunci; **nessuna fonte primaria conferma l'entrata in vigore** |
| **Cloudflare pubblica cifre di costo per classe** | **RESPINTO** | pubblica volumi e crawl-to-refer ratio |
| **Proponiamo un'architettura di consegna alternativa** | **NON LO FACCIAMO** | e' cio' che fa SemDN (Hua & Xiao, HotNets 2026); noi studiamo la dipendenza del costo dallo stato condiviso. **Non affermare che il nostro criterio sia validato su SemDN: non l'abbiamo testato** |
| origin RPS = carico di backend in generale | **DA QUALIFICARE** | C1 vale su questo banco |
| Il nostro agente sintetico rappresenta gli agenti reali | **DA QUALIFICARE** | C3 regge sull'ampiezza, C5 no sulla contiguita' |

---

## Regole d'uso

1. L'**abstract** contiene solo `MISURATO` e `SOSTENUTO`.
2. **Results** contiene solo `MISURATO`. Nessuna riga `INTERPRETATIVO` o `IMPLICAZIONE`.
3. **Mechanism** puo' usare `SOSTENUTO` e `INTERPRETATIVO`, ciascuno etichettato.
4. **Implications** contiene solo la sezione D, e ogni frase dichiara di essere
   un'implicazione progettuale, non una tecnologia validata.
5. Le righe `RITIRATO` stanno in `docs/retractions.md` e i loro dati in
   `archive/retired/`. **Non compaiono nel corpo del paper**; in tesi sono un'appendice.
6. Nessuna nuova riga senza una misura. Gli esperimenti non generano piu' la storia:
   verificano che quella congelata regga.

## Note metodologiche che accompagnano righe specifiche

- **A7 e A8** provengono dalla serie del 16 settembre, a **mappatura condivisa** e con
  finestra di misura **1211 s** invece di 620. Non sono appaiate al disegno primario e
  vanno riportate come **secondarie**, con il caveat esplicito. Reggono comunque il loro
  scopo, perche' il volume della classe agentica e' fisso a 12 req/s in tutti e quattro
  i punti e la variabile manipolata e' il volume esaustivo.
- **Le configurazioni dei run precedenti al 21 settembre non sono registrate**:
  `env.txt` esiste solo da allora. Per lo sweep di capienza del 10-11 settembre la
  dimensione nominale della cache **non e' recuperabile** e i punti sono ordinabili solo
  per hit ratio umano osservato. E' il motivo per cui FIG-A1 resta in appendice.
