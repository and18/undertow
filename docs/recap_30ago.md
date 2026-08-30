# Undertow — stato del progetto al 30 agosto 2026

Documento autosufficiente. Chi legge non sa nulla del progetto e deve
poter capire da zero cosa è stato fatto, cosa è stato trovato, cosa è
verificato, cosa è dubbio, e dove si sta andando.

Linguaggio da ingegnere. Ogni termine tecnico è spiegato alla prima
occorrenza.

**Le quattro etichette usate ovunque, mai mescolate:**

| | significato |
|---|---|
| **A** | risultato che abbiamo osservato noi, con i nostri dati |
| **B** | risultato già presente in letteratura o in fonti pubblicate |
| **C** | potenzialmente nuovo, ma non ancora abbastanza dimostrato |
| **D** | ipotesi o speculazione, nessun dato |

---

# 1. La storia

## Da dove siamo partiti

Un post che citava dati Cloudflare sul traffico dei bot. L'idea iniziale:
l'infrastruttura web è stata costruita su assunzioni sul comportamento
umano — le persone leggono poche pagine popolari molte volte, fanno
pause, il browser conserva una copia locale. Il traffico automatico
viola tutte queste assunzioni insieme.

**Ipotesi iniziale:** a parità di volume totale, cambiare la
*composizione* del traffico da umano ad automatico degrada il sistema in
modo non lineare, perché il traffico automatico non trae beneficio dalla
cache e il carico si riversa sul server di origine.

## Cosa abbiamo costruito

**Il banco prova.** Un sito web in miniatura in Docker: una cache
(Varnish) davanti, un'applicazione Python (gunicorn/Flask) in mezzo, un
database (PostgreSQL) dietro. Ogni componente confinato su core CPU
dedicati. Metriche raccolte ogni secondo. Il generatore di carico è k6 in
modalità *open-loop* — emette richieste a ritmo costante indipendentemente
da quanto il server risponde, per evitare l'errore noto come *coordinated
omission*, in cui un generatore che rallenta insieme al server nasconde
proprio le code che vorresti misurare.

Contenuto: 495 libri di Project Gutenberg, 16.954 capitoli, ingombro
misurato degli oggetti in cache 438 MB.

Due profili sintetici di traffico:
- **alta località** — distribuzione Zipf(1) sulla popolarità delle
  pagine. Poche pagine molto richieste. Sta per la navigazione umana.
- **bassa località** — attraversamento uniforme senza ripetizioni. Ogni
  pagina una volta sola. Sta per la scansione esaustiva.

La variabile indipendente è **α**, la frazione di traffico a bassa
località, variata **a volume totale costante**. Se il volume crescesse
con α, un eventuale collasso dimostrerebbe solo che più carico satura un
sistema, che è noto dal 1961.

**L'honeypot.** `theslowshelf.org`, 18.720 pagine di letteratura di
pubblico dominio, con `robots.txt` che **permette esplicitamente tutti i
crawler AI** — l'opposto della pratica corrente, perché un sito che
blocca i crawler non può osservarli. Il log di nginx registra due campi
che i formati standard non hanno: l'identificativo della connessione TCP
e il contatore di richieste per connessione. Sono gli unici due campi che
permettono di misurare il *riuso delle connessioni*.

Attivo dal 12 agosto. Circa 186.000 richieste in 17 giorni.

**I dati Cloudflare Radar**, interrogati via API pubblica.

## Cosa è successo, in ordine

Il progetto ha cambiato domanda tre volte, ogni volta perché un dato ha
smentito l'impostazione precedente.

**Fase 1 (12-19 ago) — "trova la soglia".** Cercavamo la percentuale di
traffico automatico oltre la quale il sistema collassa. Trovata: 15%.

**Fase 2 (18-19 ago) — la soglia non esiste.** Ripetendo lo stesso
esperimento tre giorni dopo, il collasso non si è verificato. Gli hit
ratio della cache erano identici all'1%, ma il database si era scaldato
(il suo working set era migrato in memoria) e la capacità dell'origine
era passata da 74 a 92 richieste al secondo. La soglia dipendeva dalla
macchina, non dal traffico.

**Fase 3 (21-23 ago) — l'audit di novità.** Confronto sistematico con la
letteratura. Scoperta che il paper SoCC 2025 usa lo stesso identico
modello (Zipf per gli umani, scansione per l'AI) e trova gli stessi
risultati qualitativi. Metà di quello che pensavamo nostro era già
pubblicato.

**Fase 4 (26-30 ago) — riorientamento.** La domanda diventa: *quanto
costa ogni classe di traffico, e quale budget di risorse merita?* Il
banco prova viene portato su una macchina ARM in cloud, perché il
portatile andava in kernel panic durante le campagne lunghe.

---

# 2. Cosa abbiamo trovato

## Nel banco prova

**O1 — la transizione esiste ed è netta.** [A, ma vedi §3: il fenomeno
è B] A volume costante di 220 richieste/secondo, il p99 della latenza
passa da 83 ms (α=0) a 1971 ms (α=0,25). L'hit ratio della cache scende
da 0,827 a 0,636.

**O2 — la soglia in percentuale non è trasferibile.** [C, il più forte]
Su sei campagne, due architetture (x86 e ARM) e quattro dimensioni di
pool di thread, il ginocchio si è presentato a α tra 0,10 e 0,30. Ma
calcolando il carico che arriva davvero all'origine — λ × (1 − hit
ratio) — il numero è sempre lo stesso:

| pool | λ | α al ginocchio | **carico all'origine** |
|---|---|---|---|
| 3 | 220 | 0,25 | **79,9 req/s** |
| 4 | 220 | 0,25 | **79,9** |
| 8 | 220 | 0,25 | **80,1** |
| 12 | 330 | 0,10 | **79,9** |

Con capacità dell'origine ≈ 90 req/s, il ginocchio è sempre a **ρ = 0,89**
(ρ = utilizzo della risorsa: quanto della sua capacità è impegnata).

**O3 — la causa è la cache, dimostrata per intervento.** [A, metodo
solido] Correlazione non basta: α guida ogni anello della catena per
costruzione, quindi tutte le correlazioni sono vicine a 1 senza
dimostrare nulla. Abbiamo quindi manipolato direttamente il presunto
mediatore. Variando **solo** la dimensione della cache: con 128 MB il
ginocchio è a α=0,30; con 256 MB a α=1,00; con 512 MB **non c'è**. A
α=0,50 il p99 passa da 3096 ms a 1 ms cambiando esclusivamente la cache.

**O4 — per la scansione, l'hit ratio è zero.** [B, teoria di base] Una
scansione sequenziale su un insieme più grande della cache fa sì che LRU
sfratti sempre l'oggetto che servirà per primo. Misurato: h = 0,000. È il
caso di scuola della non-scan-resistance.

**O5 — un budget per classe funziona.** [A l'esecuzione, B il
meccanismo] L'applicazione ammette al massimo N richieste a bassa
località contemporaneamente; l'eccesso riceve un 503 con `Retry-After`
— un rinvio, non un rifiuto.

| budget | p99 interattivo | throughput batch | occupazione |
|---|---|---|---|
| off | 1344 ms | 9870 | 90% |
| 5 | **271 ms** (5,0× meglio) | 8623 (−12,6%) | 72% |
| 4 | **174 ms** (7,7× meglio) | 8078 (−18,2%) | 61% |

Il throughput interattivo resta **identico** (29.615 → 29.693): quella
classe non era affamata di richieste servite, era affamata di latenza. Il
costo sul lavoro totale del sistema è **−3,0%**.

Isolamento quasi perfetto: due rinvii sulla classe interattiva su 148.000
richieste.

**La stessa grandezza che prevede il collasso ne prevede il recupero:**
la composizione spinge l'occupazione oltre il 90% e il sistema si rompe;
il budget la riporta al 72% e guarisce.

**O6 — il pool di thread non conta.** [A, risultato di ieri notte] A
volume fisso, variando solo la dimensione del pool (3, 4, 8, 12), il
ginocchio compare sempre e il throughput è identico a tre cifre. **Il
pool non è la risorsa che satura: è solo la coda davanti a quella che
satura**, il database. Questo falsifica un'ipotesi che avevamo (che un
pool più piccolo rendesse immuni) e corregge un'assunzione scritta nel
registro di progetto.

## Nell'honeypot

**H1 — ogni operatore arriva una volta, esaustivamente, e sparisce.**
[C, potenzialmente nuovo] GPTBot ha coperto il 102% del sito in **un
giorno** (19.220 richieste il 15 agosto) e non è tornato per nove giorni.
Meta la stessa cosa il 14. Ahrefs e Semrush il 18. **Il carico del
crawling non è una media giornaliera: è un evento.** Chi dimensiona sulla
media incontra un picco di venti volte quando tocca a lui.

**H2 — il sito ha un ciclo di vita.** [C] Dal 12 al 15 agosto crawling
esaustivo di training; dal 16 al 19 crawling SEO; dal 22 al 28 traffico
agentico. Le richieste agentiche passano da **34 nella prima settimana** a
**2.542 il solo 24 agosto**. Serviva un sito strumentato *prima* di
esistere, ed è il motivo per cui nessuno ha questo dato.

**H3 — i crawler SEO pesano più di quelli AI.** [A] Ahrefs, Semrush,
SERanking e DotBot superano insieme le 40.000 richieste, più di tutti gli
operatori AI messi insieme.

**H4 — l'identità verificabile non predice il costo.** [C] AhrefsBot è
l'**unico** operatore che firma crittograficamente con Web Bot Auth — lo
standard IETF che l'industria sta adottando per decidere chi far passare
— e apre **una connessione TCP per ogni singola richiesta**. GPTBot, che
non firma nulla, ne riusa **686**. Una politica che ammette i firmati e
rifiuta i non firmati ammette i costosi e rifiuta gli economici.

**H5 — il riuso delle connessioni varia di tre ordini di grandezza.** [C]
686,7 per GPTBot; esattamente 1,0 per Meta, Ahrefs, Semrush, Amazonbot;
2,8 per Googlebot. Meta usa HTTP/2 su 331 indirizzi e apre una
connessione nuova per ogni richiesta, vanificando l'unico motivo per cui
HTTP/2 esiste.

**H6 — selettivo contro esaustivo, quantificato.** [C] Googlebot copre il
17% del sito con indice di Gini 0,18 (alcune pagine gli interessano più
di altre). GPTBot, Ahrefs e Amazonbot coprono tutto con **Gini 0,00**:
perfettamente uniforme. Il Gini è calcolabile da qualunque log.

**H7 — nessuno rivalida.** [C] **Una risposta 304 su 186.000 richieste.**
Le richieste condizionali esistono perché un client possa chiedere "è
cambiato?" e ricevere poche centinaia di byte invece dell'intero
documento. Non le usa nessuno.

**H8 — un quarto del traffico non è classificato.** [lacuna aperta]
45.031 richieste con user agent da browser, che includono un crawler
mascherato da Chrome 42 del 2015 che scaricava ogni pagina due volte.

## Dai dati Cloudflare

**G1 — il web rifiuta il traffico sbagliato.** [B come dato, C come
inquadramento]

| | Training | Search | **User Action** |
|---|---|---|---|
| | *nessuno aspetta* | | ***una persona aspetta*** |
| 200 OK | 63,7% | 53,9% | **25,0%** |
| 403 | 17,6% | 19,0% | **34,5%** |
| rifiutato | 25,7% | 33,4% | **59,8%** |

La classe con un essere umano in attesa in tempo reale viene bloccata il
doppio delle volte e riceve una risposta valida una volta su quattro.

**G2 — la composizione si sta riproporzionando.** [B] In un anno: User
Action +130%, Search +91%, Training +8%.

**G3 — nessuno rivalida, globalmente.** [B] 304 allo 0,53% di tutte le
richieste dei bot AI. Conferma H7 su scala planetaria.

---

# 3. L'audit di novità

Fatto due volte, la seconda deliberatamente ostile ("prova a distruggere
l'ipotesi").

## Il concorrente diretto

**Zhang, Cai, Wildani, Klimovic, "Rethinking Web Cache Design for the AI
Era", SoCC 2025** (Cloudflare + ETH Zürich, peer-reviewed, DOI
10.1145/3772052.3772255).

Usa **lo stesso identico modello**: Zipf(1) per gli umani, scansione
depth-first per l'AI, prototipo Varnish su architettura Wikimedia. Trova
che il miss ratio passa dal 17,3% al 51,8%, e propone politiche di
sfratto resistenti alla scansione più tier separati.

## Riga per riga

| contributo | stato |
|---|---|
| Degrado dell'hit ratio con traffico AI | **già fatto** (SoCC 2025) |
| Zipf contro scansione come modello | **già fatto** — stesso identico |
| Hit ratio zero per la scansione | **già fatto** — teoria di base (ARC, LIRS, 2Q, SIEVE) |
| Scan-resistance | **già fatto** — letteratura dagli anni '90 |
| Cache contention fra classi | **già fatto** |
| Il carico si sposta sul backend | **già fatto qualitativamente** — SoCC lo dice, non lo misura |
| Cache partitioning | **parzialmente** — proposto da SoCC come visione, mai implementato |
| Admission control per classe | **già fatto come meccanismo** — Netflix concurrency-limits 2018 divide il budget fra "live" e "batch" con split 90/10 |
| Il ginocchio a ρ ≈ 0,9 | **già noto come teoria** — è la formula di Kingman |
| **Che la soglia in % non sia trasferibile** | **non trovato** |
| **Il paradosso della scan-resistance** | **non trovato**, da verificare |
| **Riuso connessioni per operatore** | **non trovato** |
| **Zero rivalidazione misurata** | **non trovato** come misura |
| **Carico del crawling come evento** | **non trovato** |
| **Ciclo di vita di un sito nuovo** | **non trovato** |

Nota su tutte le righe "non trovato": significa *non ho trovato evidenza
pubblicata nelle fonti controllate*, non "nessuno l'ha mai fatto".

## Cosa abbiamo dovuto ritirare

Dieci ritrattazioni registrate. Quattro sono lo stesso errore: una
spiegazione elegante costruita su una finestra parziale, formulata pochi
minuti dopo una misura interessante.

Le più significative: la "banda di instabilità" (era in gran parte
variabilità della piattaforma, non del fenomeno — su ARM la dispersione
è del 4% contro il 300% su x86); l'inversione scan/LRU presentata come
controintuitiva quando è teoria di base; e tutte le misure di hit ratio
della classe scan prima del 26 agosto, invalidate da un offset casuale
nel generatore che rendeva il risultato una lotteria.

---

# 4. Cloudflare: aiuto o minaccia?

Cloudflare classifica il traffico AI in Search / Agent / Training, e dal
**15 settembre 2026** cambia i default: Training e Agent bloccati sulle
pagine con pubblicità per i domini nuovi.

**Cosa pubblica:** composizione del traffico per classe, crawl-to-refer,
codici di risposta per classe, tipi di contenuto, hit rate CDN
aggregato.

**Cosa NON pubblica** (verificato su Radar, AI Insights, AI Crawl
Control, blog, API, paper): hit/miss per classe legato al carico
all'origine; latenza in funzione della composizione; saturazione delle
risorse a valle; carico all'origine per classe; una soglia di
saturazione; l'effetto quantificato di un budget per classe.

**Conclusione: Cloudflare non rende il lavoro inutile. Fornisce la
classificazione che ci mancava.** Loro rispondono a *che traffico è*, noi
a *quanto costa e che budget merita*. Sono strati diversi.

**Attenzione però:** Cloudflare si sta avvicinando. Il loro blog di
aprile 2026 parla già di ripensare la cache per l'era AI e di tier
separati. La finestra si sta restringendo.

---

# 5. La direzione attuale

## Il riorientamento

L'impostazione iniziale — "l'AI rompe la cache" — è morta per due
ragioni: è già pubblicata, e la soglia che produceva non era
trasferibile.

L'impostazione attuale:

> Le classi di traffico hanno impronte di risorse e urgenze opposte. Il
> training è ad alto volume con nessuno in attesa; l'agentico è a basso
> volume con una persona che aspetta. Oggi si decide per identità, e il
> risultato misurabile è che il web rifiuta il 60% del traffico urgente e
> serve il 64% di quello che potrebbe aspettare. Serve una politica
> basata sul **costo**, e questo richiede di misurare quanto ogni classe
> costa davvero.

## Le due fasi (la distinzione che rende il lavoro durevole)

**Fase transitoria** — mondo misto umani + agenti. Il problema è
l'interferenza fra classi e la protezione del traffico interattivo. Qui
servono partizionamento della cache, admission control, isolamento delle
risorse. **È dove siamo, ed è dove i risultati attuali si applicano.**

**Fase futura** — traffico prevalentemente agentico. Se α → 1, α smette
di essere una variabile utile: non puoi progettare dicendo "quando gli
agenti sono il 70% faccio X" se sono il 100%. Ma restano le differenze
*fra* agenti: chi cerca in modo selettivo, chi attraversa tutto, chi fa
polling, chi genera raffiche. **La distinzione fondamentale smette di
essere umano/agente e diventa comportamento/comportamento.**

**Perché questo rende il lavoro più forte:** i risultati che sopravvivono
al passaggio sono quelli espressi in termini di risorse, non di
composizione. ρ resta, il ginocchio resta, l'admission control resta.
"Umano contro AI" no.

**Il rischio, ed è reale:** promettere "come progettare il web
dell'era agentica" quando si ha un banco prova, un honeypot e diciassette
giorni di dati. Un revisore lo vede subito. La formulazione che i dati
sostengono è più stretta: *misuriamo cosa si rompe, dove, e quale
variabile lo predice*.

---

# 6. Valutazione ostile

**La direzione è interessante?** Sì, ma non per il motivo che pensavamo.
Il caching è terreno occupato. Quello che resta libero è la misura *lato
origine* e il comportamento reale degli operatori.

**È abbastanza diversa da SoCC 2025?** Solo su tre punti: l'intervento
causale (loro osservano, noi manipoliamo), la riformulazione della
soglia, e i dati di campo. Su tutto il resto siamo pari o dietro.

**La domanda scientifica più forte:** *quando due classi di traffico
condividono un'infrastruttura, una politica che ottimizza per una classe
può trasferire il costo sull'altra invece di eliminarlo — e in che
condizioni?*

**Il risultato che renderebbe il lavoro importante:** dimostrare che la
soluzione proposta da SoCC 2025 e adottata da Cloudflare ha un costo
nascosto misurabile.

**Cosa sarebbe solo incrementale:** riconfermare che l'AI degrada la
cache. Aggiungere una politica di sfratto migliore. Misurare più bot.

**Stiamo costruendo una storia troppo grande?** Sì, se il titolo parla
del futuro del web. No, se parla di quello che abbiamo misurato.

**Cosa eliminare:** l'inquadramento profetico sull'era agentica come
tesi centrale (va in discussione); la banda di instabilità come
risultato; l'ambizione di classificare il traffico meglio di Cloudflare.

**L'esperimento con il miglior rapporto tempo/valore:** il
partizionamento della cache per classe. Due ore, e o conferma o smentisce
l'unica cosa che contraddice un lavoro pubblicato.

**Cosa interesserebbe fra 5-10 anni, indipendentemente dall'AI:** il
principio del trasferimento di costo fra classi che condividono una
risorsa. Non dipende dall'AI, dipende dal fatto che classi diverse
condividano una cache.

---

# 7. La domanda di ricerca

In ordine, dalla più forte alla più debole.

**RQ1.** *Quando due classi di traffico con obiettivi diversi condividono
una cache, una politica che protegge una classe può aumentare il costo
totale sul sistema invece di ridurlo?*
Verificabile in due ore, contraddice un lavoro pubblicato, generalizza
oltre l'AI.

**RQ2.** *Qual è la grandezza che predice il punto di rottura di
un'infrastruttura sotto traffico misto, e perché quella che il campo usa
oggi (la percentuale di traffico AI) non è trasferibile?*
Dimostrata su sei campagne e due architetture. Il rischio è che sia
troppo vicina a teoria delle code nota.

**RQ3.** *Come si comportano davvero gli operatori automatici, e
l'identità che dichiarano predice quanto costano?*
Dati unici. Rischio: un solo sito, diciassette giorni.

**RQ4.** *Si può servire il traffico batch senza sacrificare quello
interattivo, senza bloccare nessuno?*
Dimostrato. Ma il meccanismo è Netflix 2018.

**RQ5.** *Come cambierà l'infrastruttura quando il traffico sarà
prevalentemente agentico?*
Interessante ma non dimostrabile con i dati che abbiamo. Discussione, non
risultato.

---

# 8. I possibili "big result"

**BIG-1 — Il costo nascosto della protezione.** [in corso di verifica]

*Cosa misurare:* carico all'origine per classe, latenza per classe, al
variare della frazione di cache riservata.
*Esperimento:* due istanze Varnish, instradamento per classe, r da 0,5 a
1,0 più un riferimento a cache condivisa.
*Cosa dimostrare:* che oltre una certa r il carico totale all'origine
peggiora anche se la latenza umana migliora.
*Perché nuovo:* nessun paper sulla scan-resistance riporta il carico
backend come metrica separata dall'hit ratio.
*Perché interessa un revisore:* contraddice una proposta pubblicata.
*Perché interessa un operatore:* dice se la politica che sta per adottare
gli costa capacità.
*Cosa potrebbe bocciarci:* se l'effetto è piccolo (i dati preliminari
dicono +14%), è un caveat e non una confutazione.

**BIG-2 — Il carico è un evento, non una media.** [dati già in mano]

*Cosa misurare:* rapporto picco/media per operatore, su otto settimane.
*Esperimento:* nessuno, solo continuare la raccolta.
*Cosa dimostrare:* che il fattore di picco è ~20× e che il
dimensionamento sulla media è sbagliato per costruzione.
*Perché nuovo:* nessuno ha dati di campo con questa granularità.
*Perché interessa un operatore:* è capacity planning diretto.
*Cosa potrebbe bocciarci:* un solo sito. Serve un secondo dominio per
generalizzare.

**BIG-3 — Identità e costo sono indipendenti.** [dati in mano,
n piccolo]

*Cosa dimostrare:* che il costo infrastrutturale di un operatore non è
predetto dalla sua identità verificabile, con implicazione diretta sugli
standard in corso di definizione.
*Perché interessa:* i gruppi di lavoro IETF stanno costruendo
l'ammissione basata sull'identità proprio ora.
*Cosa potrebbe bocciarci:* un solo firmatario osservato. È un
controesempio, non una caratterizzazione.

---

# 9. Le fonti e il loro ruolo nel paper

| fonte | ruolo |
|---|---|
| Banco prova (Varnish/Flask/PostgreSQL/k6) | **prova principale** |
| Intervento sulla cache (O3) | **prova causale** |
| Invarianza su pool e architetture (O2, O6) | **prova principale** |
| Budget per classe (O5) | **mitigazione** |
| Esperimento di partizionamento | **il risultato che manca** |
| Honeypot — riuso connessioni, Gini, 304 | **caso di studio + motivazione** |
| Honeypot — carico a evento, ciclo di vita | **caso di studio, potenzialmente principale** |
| Cloudflare Radar | **contesto e motivazione a scala globale** |
| Classificazione Search/Agent/Training | **vocabolario preso in prestito** |
| Dati telco/uplink | **fuori tema** — progetto diverso |

---

# 10. Mappa finale

| idea | già pubblicata? | nostro risultato | novità | evidenza | manca |
|---|---|---|---|---|---|
| Umano vs agente | sì (SoCC, Cloudflare) | conferma | nessuna | forte | — |
| Scan-resistance | sì (anni '90) | non è il focus | nessuna | — | — |
| Carico origine per classe | qualitativo | quantificato | media | forte | — |
| Cache partitioning | proposto, non valutato | in corso | **alta** | in corso | l'esperimento |
| Admission control | sì (Netflix 2018) | quantificato all'origine | bassa | forte | — |
| Pool ρ | teoria (Kingman) | invariante su 4 pool, 2 arch. | media | forte | altro bottleneck |
| Req/connessione | non trovato | 686 contro 1,0 | **alta** | 1 sito | secondo sito |
| Zero 304 | non trovato come misura | 1 su 186.000 | **alta** | 1 sito + Radar | — |
| Carico a evento | non trovato | picco 20× | **alta** | 17 giorni | 8 settimane |
| Infrastruttura agentica futura | — | — | — | nessuna | tutto (è D) |

| direzione | novità | impatto | fattibilità | rischio |
|---|---|---|---|---|
| **A — costo nascosto della protezione** | alta | alto | **2 ore** | effetto piccolo (+14%) |
| **B — comportamento reale degli operatori** | alta | medio | già in corso | un solo sito |
| **C — futuro dell'infrastruttura agentica** | media | alto | mesi | non dimostrabile ora |

---

# 11. Cosa farei nei prossimi due-tre mesi

**Settimana 1 — l'esperimento del partizionamento.** Due ore di
macchina. Se il paradosso esiste, è il risultato che regge il paper. Se
non esiste, è comunque pubblicabile ("la proposta di Zhang non ha il
costo nascosto che si potrebbe temere") e si risparmiano settimane.

**Settimane 2-4 — consolidare.** Ripetizioni sulla configurazione
finale; l'esperimento del retry (se il crawler rispetta `Retry-After`, il
costo del budget passa dal 3% a zero); l'honeypot che continua fino a
otto settimane; scomposizione del quarto di traffico non classificato.

**Settimane 5-8 — scrivere.** arXiv per primo, poi una conferenza di
misurazione (PAM è la più accessibile senza affiliazione, IMC la più
prestigiosa). Rilasciare il generatore e il dataset.

**Settimane 9-12 — diffondere.** Blog, LinkedIn, e portare le misure sul
riuso delle connessioni ai gruppi di lavoro IETF, dove si sta decidendo
proprio ora come funzionerà l'ammissione basata sull'identità.

**Cosa NON fare:** inseguire Cloudflare sulla classificazione; costruire
una seconda mitigazione; promettere il futuro del web; aggiungere
esperimenti prima di aver scritto quelli fatti.

**Perché questa strada:** massimizza novità × impatto × probabilità di
riuscita. L'unico risultato che contraddice qualcosa di pubblicato costa
due ore. Il resto è già misurato e va scritto, non esteso.

---

# In una pagina: cosa abbiamo davvero in mano oggi

**Il problema.** L'infrastruttura web assume che i visitatori leggano
poche pagine popolari molte volte. Il traffico automatico legge tutto una
volta sola, quindi la cache non lo assorbe e il carico arriva al server.
A parità di volume totale, cambiare la composizione del traffico rompe il
sistema.

**Cosa abbiamo misurato, e regge.** La transizione è netta e riproducibile
su due architetture. La causa è la cache: dandogliene abbastanza, il
fenomeno sparisce (dimostrato manipolando direttamente la cache, non per
correlazione). La soglia in percentuale di traffico AI **non è
trasferibile** — varia da 0,10 a 0,30 fra configurazioni — mentre il
carico all'origine al punto di rottura è sempre lo stesso, circa il 90%
della capacità. Un budget di risorse per classe riduce la latenza del
traffico interattivo di cinque volte al costo del 3% del lavoro totale, e
il pool di thread applicativo non c'entra nulla: è solo la coda davanti
al database.

**Cosa abbiamo osservato sul campo.** Un sito-esca acceso il 12 agosto
con `robots.txt` permissivo. Ogni operatore arriva una volta, scansiona
tutto in un giorno, e sparisce — GPTBot ha coperto il 102% del sito in
ventiquattr'ore. Il carico non è una media, è un evento. Il sito ha
attraversato tre fasi: crawling di training, poi indicizzazione, poi
traffico agentico (da 34 richieste in una settimana a 2.542 in un
giorno). L'unico operatore che si firma crittograficamente è anche quello
che si comporta peggio: una connessione TCP per richiesta, contro le 686
richieste per connessione di GPTBot che non firma nulla. E su 186.000
richieste, **una sola** ha usato una richiesta condizionale.

**Cosa è già di altri.** Che l'AI degradi la cache è pubblicato (SoCC
2025, stesso modello sperimentale). Che una scansione azzeri l'hit ratio
è teoria di base. Che un budget di concorrenza protegga il traffico
interattivo è Netflix 2018. Che la latenza esploda vicino alla
saturazione è teoria delle code. Dieci ritrattazioni registrate, quattro
delle quali sono lo stesso errore: una spiegazione elegante costruita su
una finestra parziale.

**Cosa resta potenzialmente nostro.** Che la soglia in percentuale non
sia trasferibile e che quella che lo è vada misurata sul collo di
bottiglia vero. Il comportamento di campo per operatore (riuso
connessioni, Gini di copertura, assenza di rivalidazione, carattere
impulsivo del carico). E — da verificare in due ore — che proteggere la
cache del traffico umano **aumenti** il carico all'origine invece di
ridurlo, il che contraddirrebbe la soluzione che l'industria sta
adottando proprio ora.

**Il prossimo passo.** L'esperimento del partizionamento. Se il costo
nascosto esiste, il paper ha una tesi che contraddice un lavoro
pubblicato. Se non esiste, si scrive quello che c'è — che è comunque un
buon paper di misurazione con un dataset che nessun altro ha.

**Valutazione onesta:** non è rivoluzionario. È un solido lavoro di
misurazione con un possibile risultato controintuitivo e dati di campo
originali. La differenza fra un buon paper e uno importante si gioca
tutta su quelle due ore di esperimento.