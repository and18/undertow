# Undertow — recap al 11 settembre 2026

Documento autosufficiente. Chi legge non sa nulla del progetto e deve
poter capire cosa è stato fatto, cosa è verificato, cosa è dubbio, cosa
è già di altri, e dove si sta andando.

---

# 1. La domanda

L'infrastruttura web è tarata su un modello di visitatore umano: poche
pagine popolari richieste molte volte, pause fra le richieste, copia
locale nel browser, sessione, ciclo giorno/notte. Il traffico automatico
viola tutte queste assunzioni — ma non le viola in modo uniforme, e le
differenze **fra** i client automatici sono più grandi della differenza
fra automatico e umano.

Tre classi, con impronte di costo e urgenze opposte:

- **crawler di training** — attraversa tutto il sito, una volta, ad alto
  volume, nessuno aspetta il risultato;
- **crawler di ricerca** — selettivo, vincolato dal valore atteso per
  pagina;
- **agente** — recupera due o tre pagine, volume bassissimo, **una
  persona aspetta in tempo reale**.

Costo e urgenza sono anticorrelati: la classe cara è quella che potrebbe
aspettare. Il web oggi decide guardando **l'identità** ("sei un bot?")
invece del costo.

**Domanda del progetto:** quanto costa davvero ogni classe a un'origine,
e che budget di risorse merita?

---

# 2. L'apparato

**Banco prova** (macchina OCI Ampere Neoverse-N1, 6 core fisici senza
SMT, 23 GB RAM, aarch64). Catena in Docker con ogni componente su core
dedicati:

```
k6 (core 0) → Varnish (1) → gunicorn/Flask, 8 thread (2) → PostgreSQL (3-5)
```

Corpus: 495 libri Project Gutenberg, 16 954 capitoli, ingombro degli
oggetti in cache **438 MB**. Le dimensioni dei capitoli sono a coda
pesante: mediana 9,5 KB, media 15,0 KB, deviazione standard 32,4 KB,
massimo 1,9 MB. Questo dettaglio ha invalidato misure per otto giorni
(vedi §7).

Generatore k6 in modalità **open-loop** (`constant-arrival-rate`), per
evitare la coordinated omission — un generatore che rallenta insieme al
server nasconde proprio le code che vorresti misurare.

**Tre profili di traffico sintetico:**

| profilo | modello di accesso | sta per |
|---|---|---|
| alta località | Zipf(1) sulla popolarità | navigazione umana |
| esaustivo | attraversamento uniforme, mai due volte la stessa pagina | crawler di training |
| agentico | sessioni di 3 capitoli contigui su un sottoinsieme del 2% del corpus, Zipf(0,6) | agente con persona che aspetta |

Il profilo agentico è **calibrato sui dati di campo**, non inventato:
copertura misurata 5,8-6,0% contro il 2,1-6,1% degli operatori agentici
reali sull'honeypot; 2,76 richieste per URL contro 2,1-3,7 misurate.

**Variabili indipendenti:** α = quota esaustiva, β = quota agentica. Il
**volume totale resta costante**: se il volume crescesse con α, un
eventuale collasso dimostrerebbe solo che più carico satura un sistema.

**Honeypot** (`theslowshelf.org`): 18 720 pagine di letteratura di
pubblico dominio, `robots.txt` che **permette esplicitamente tutti i
crawler AI** — l'opposto della pratica corrente, perché un sito che
blocca i crawler non può osservarli. Log nginx con due campi che i
formati standard non hanno: identificativo della connessione TCP e
contatore di richieste per connessione. Attivo dal 12 agosto, **378 747
richieste in 26 giorni**.

**Dati Cloudflare Radar** via API pubblica, per il contesto globale.

**Protocollo di misura, fisso dal 7 settembre e obbligatorio:**
`WARMUP=300`, `MEASURE=620` (derivato dalla copertura del corpus, non
scelto a mano), cancello di validità per run, riferimento ripetuto a
inizio e fine campagna come controllo di deriva. Deriva osservata nelle
ultime campagne: **fra 0,04% e 1%**.

---

# 3. Risultati che reggono

## R1 — La soglia in percentuale non è trasferibile; l'utilizzazione sì

Su sei campagne, due architetture (x86 e ARM), quattro dimensioni del
pool di thread:

| host | ginocchio a α | occupazione |
|---|---|---|
| x86, 16 thread, SMT | 0,15 | 96% |
| x86 | 0,30 | 97% |
| x86 | mai raggiunto | max 75% |
| x86 | 0,20 | 93% |
| ARM, 6 core | 0,25 | 89% |

**La composizione al ginocchio varia da 0,15 a 0,30. L'occupazione al
ginocchio resta fra 0,89 e 0,97.**

Non esiste un limite universale di "percentuale di traffico AI". Esiste
un confine di utilizzazione, e un operatore lo ha già nel monitoraggio.

*Raffinamento (31 agosto):* ρ predice **quando la coda all'origine
esplode, non quanto una data classe ne soffre**, perché quello dipende
anche dalla frazione di miss della classe.

## R2 — La causa è la contesa di cache, dimostrata per intervento

α guida ogni anello della catena per costruzione, quindi tutte le
correlazioni sono vicine a 1 senza dimostrare nulla. Intervento diretto
sul mediatore ipotizzato, variando **solo** la dimensione della cache:

| cache | ginocchio | p99 a α=0,50 |
|---|---|---|
| 128 MB | α = 0,30 | 3096 ms |
| 256 MB | α = 1,00 | 252 ms |
| 512 MB | **assente** | **1 ms** |

*Caveat:* misurato su x86 prima che il protocollo fosse fissato. Da
rimisurare; l'effetto è troppo grande perché un artefatto lo spieghi.

## R3 — Il passaggio gratuito, e la sua legge di scala

La classe esaustiva campiona uniformemente un corpus più grande della
cache, quindi non ha località. Con una cache **privata** ottiene hit
ratio **0,000** a qualunque capacità da 32 a 384 MB (16 run). Con una
cache **condivisa** ottiene:

| cache | cache/corpus | h esaustiva | h umana | origine req/s |
|---|---|---|---|---|
| 32 MB | 0,073 | 0,048 | 0,590 | 60,0 |
| 64 MB | 0,146 | 0,089 | 0,686 | 51,0 |
| 128 MB | 0,292 | 0,195 | 0,791 | 39,4 |
| 256 MB | 0,584 | 0,537 | 0,909 | 20,2 |
| 384 MB | 0,877 | 0,804 | 0,964 | 8,3 |

Incontra ciò che la classe umana ha reso residente. **Il passaggio
gratuito è, in buona approssimazione, la frazione di corpus residente.**

Conseguenza pratica, e va riportata **prima** di R4: su un sito di
produzione, dove la cache tiene una frazione minuscola del contenuto, il
passaggio gratuito è **trascurabile**. Questo limita l'importanza pratica
di R4 ed è ciò che rende il lavoro onesto invece che allarmista.

## R4 — Il costo del partizionamento cambia segno con la scala

Riserva totale per la classe umana contro riferimento condiviso, **a
parità di capacità totale**:

| cache | condivisa | partizionata | costo |
|---|---|---|---|
| 32 MB | 60,0 | 57,5 | **−3,8%** |
| 128 MB | 39,5 | 41,8 | **+5,8%** |
| 384 MB | 8,4 | 35,4 | **+321%** |

Decomposizione che spiega l'inversione:

```
costo = λ·α·h_esaustiva      −  λ(1−α)·Δh_umana
        passaggio distrutto     guadagno della classe protetta
```

| cache | previsto | misurato |
|---|---|---|
| 32 MB | −2,56 | −2,3 |
| 128 MB | +2,31 | +2,3 |
| 384 MB | +22,1 | +27,0 |

Il secondo termine è normalmente positivo. **A 384 MB diventa negativo**:
l'hit ratio umano scende da 0,964 condiviso a 0,905 partizionato, *con
la stessa capacità*. In condivisione era la classe esaustiva a caricare
il corpus per quella umana. **Il passaggio gratuito corre in entrambe le
direzioni.**

## R5 — Una cache privata vale meno di una condivisa più piccola

A 384 MB con r=0,75 la classe esaustiva ha **96 MB tutti suoi** e ottiene
h = 0,028. Con **32 MB condivisi** otteneva 0,048 — quasi il doppio, con
un terzo della memoria.

Falsifica direttamente l'additività delle curve di utilità misurate in
isolamento, che è l'assunzione alla base del partizionamento per utilità
(Qureshi & Patt, MICRO 2006).

**Forma operativa: alla classe esaustiva si dà zero, oppure capacità
aggiuntiva. Mai una fetta di quella che hai già.**

## R6 — Un budget per classe recupera la classe interattiva

L'applicazione ammette al massimo N richieste esaustive concorrenti;
l'eccesso riceve `503` con `Retry-After: 2` — **un rinvio, non un
rifiuto**.

| budget | p99 interattivo | throughput batch | occupazione |
|---|---|---|---|
| off | 1343,5 ms | 9870 | 90% |
| 5 | **270,7 ms** (5,0×) | 8623 (−12,6%) | 72% |
| 4 | **174,4 ms** (7,7×) | 8078 (−18,2%) | 61% |

Il throughput interattivo è **invariato** (29 615 → 29 693): quella
classe non era affamata di richieste servite, era affamata di latenza.
Costo sul lavoro totale del sistema: **−3,0%**. Isolamento quasi
perfetto: due rinvii sulla classe interattiva su 148 000 richieste.

*Caveat esistenziale:* k6 non rispetta `Retry-After`, quindi i rinvii
appaiono come lavoro perso. Se un crawler reale riprova, il 3% potrebbe
essere interamente temporale. **Nessuno ha mai misurato se i crawler
reali rispettano `Retry-After`.**

## R7 — Il costo unitario di una classe dipende dalla sua stessa quota

Campagna a tre classi, α=0,25 fisso, β variabile, λ=110, TTL 3600 s,
sei punti, tutti a 620 s di misura:

| β | h agentica | costo per richiesta | p99 agentica | origine totale |
|---|---|---|---|---|
| 0,02 | 0,732 | **0,268** | 91,2 ms | 39,78 |
| 0,05 | 0,800 | 0,200 | 82,3 ms | 39,18 |
| 0,10 | 0,867 | 0,133 | 63,9 ms | 38,91 |
| 0,15 | 0,911 | 0,089 | 55,5 ms | 37,98 |
| 0,20 | 0,939 | 0,061 | 49,2 ms | 36,67 |
| 0,30 | 0,971 | **0,029** | 39,8 ms | 34,49 |

Monotona su tutte le colonne. **Il costo per richiesta della classe
agentica varia di 9,2 volte al variare della sua sola quota.** E la
classe esaustiva fa l'opposto: il suo hit ratio **scende** man mano che
la sua quota sale (0,248 → 0,127 al crescere di α).

Nel frattempo l'hit ratio umano resta piatto (0,788 → 0,772): la classe
agentica non ruba residenza agli altri, se la costruisce.

**La domanda "quanto costa una richiesta agentica rispetto a una di
crawler?" non ha una risposta.** Il rapporto va da **3× a 28×** a
seconda della composizione del traffico. Ogni controllore di ammissione
pubblicato prende quel numero come costante.

## R8 — La classe agentica paga il conto della classe esaustiva

Quota agentica ferma al 5%, quota esaustiva crescente, λ=160, volume
totale costante:

| α | ρ | p99 umano | p99 agentico | p99 esaustivo |
|---|---|---|---|---|
| 0,00 | 0,32 | 64,5 | **61,6** | – |
| 0,20 | 0,60 | 114,2 | 117,7 | 165,1 |
| 0,30 | 0,75 | 162,6 | 165,9 | 231,4 |
| 0,40 | **0,92** | 528,1 | **529,4** | 629,6 |

Il p99 della classe agentica peggiora di **8,6 volte** senza che quella
classe cambi nulla. A ρ=0,92 le tre classi **convergono**: 528,1 e 529,4
sono lo stesso numero. La coda satura non sa chi sei.

A α=0,40 la classe esaustiva è il 40% delle richieste e genera il **71%
del carico all'origine**; quella agentica è il 5% delle richieste e
genera il **2,4%**. E subiscono la stessa attesa.

Controllo di deriva su questa campagna: 27,17 contro 27,16 req/s a
cinque ore di distanza, **0,04%**.

## R9 — Il TTL: cosa sopravvive e cosa no

Campagna dell'11 settembre. α=0,25, λ=110, due valori di β, scadenza
degli oggetti accorciata da 3600 a 30 secondi.

| TTL | h agent β=0,02 | h agent β=0,20 | **divario** | origine β=0,02 | origine β=0,20 | **guadagno** |
|---|---|---|---|---|---|---|
| 3600 s | 0,730 | 0,938 | **0,208** | 39,75 | 36,87 | **−7,2%** |
| 300 s | 0,687 | 0,895 | **0,208** | 41,02 | 38,74 | −5,6% |
| 120 s | 0,655 | 0,831 | 0,176 | 43,95 | 42,59 | −3,1% |
| 60 s | 0,547 | 0,730 | 0,183 | 52,84 | 51,47 | −2,6% |
| 30 s | 0,439 | 0,608 | **0,169** | 60,52 | 60,18 | **−0,6%** |

Due letture, e vanno tenute separate.

**L'endogeneità sopravvive.** Il divario fra il costo della classe
agentica al 20% e al 2% della sua quota scende solo del 19% mentre la
scadenza si accorcia di **120 volte**. Il meccanismo di R7 non è un
artefatto del contenuto immutabile.

**Il beneficio di sistema no.** Il guadagno per il server — "più traffico
agentico, meno lavoro" — passa da −7,2% a −0,6% e sparisce sotto i
sessanta secondi. **Questo ridimensiona il risultato di R7 a livello di
sistema e va dichiarato come condizione di validità: vale per contenuto
che cambia lentamente.**

Nota: tutte le misure precedenti erano a TTL 3600 s, non "senza
scadenza" come credevamo. Un'ora contro 620 s di misura non morde, ma è
un parametro che credevamo di conoscere e non avevamo mai guardato.

## R10 — Il collo di bottiglia cambia il modo di rompersi, non solo il punto

λ=160, α crescente, pool di connessioni al database stretto da 12 a 4:

| pool | α | origine | p99 umano | errori |
|---|---|---|---|---|
| 12 | 0,30 | 65,3 | 151,8 ms | 0% |
| 12 | 0,40 | 78,5 | **292,6 ms** | 0% |
| 4 | 0,30 | 57,0 | 66,1 ms | **4,8%** |
| 4 | 0,40 | 63,9 | **67,3 ms** | **8,9%** |

Con il pool stretto **il sistema non collassa in latenza: scarta**. La
latenza resta a 67 ms invece di 293, ma l'8,9% delle richieste
fallisce, e il throughput all'origine si ferma a 64 invece di 78.

**Il confine in ρ vale per un collo di bottiglia che accoda. Con uno che
blocca, non c'è un ginocchio di latenza — c'è un ginocchio di errori.**
La generalità di R1 va riformulata: non "il ginocchio è a ρ 0,9", ma
"la composizione guida l'utilizzazione, e il modo di rompersi dipende da
come la risorsa satura".

**E c'è una conseguenza che non cercavamo.** Un pool di connessioni
sottodimensionato **è già controllo di ammissione**, involontario. Ma
scarta **senza guardare chi sei**: l'8,9% di richieste perse colpisce
allo stesso modo il crawler che nessuno aspetta e l'agente con una
persona davanti allo schermo. Il sistema sta già facendo triage, lo sta
solo facendo alla cieca. È l'argomento più diretto a favore di un budget
per classe: non serve aggiungere lo scarto, serve **dirigerlo**.

---

# 4. Dati di campo (honeypot, 26 giorni, 378 747 richieste)

**H1 — Il carico è un evento, non una media.** Rapporto picco/media per
operatore fino a **15,8×**. Ogni operatore arriva una volta, copre il
sito esaustivamente in un giorno, sparisce per una settimana. Chi
dimensiona sulla media incontra un picco di quindici volte quando tocca
a lui.

**H2 — Il sito ha un ciclo di vita.** Crawling di training (12-15 ago)
→ crawling SEO (16-19 ago) → traffico agentico (dal 22 ago). Da 34
richieste agentiche nella prima settimana a 947 in un solo giorno.
*Serviva un sito strumentato prima di esistere, ed è il motivo per cui
nessuno ha questo dato.*

**H3 — I crawler SEO pesano più di quelli AI.** SEO 30,9% del traffico
contro AI-training 20,4%. SemrushBot da solo fa 56 787 richieste, più di
qualunque operatore AI.

**H4 — L'identità verificabile predice la conformità al protocollo, non
il costo di trasporto.** AhrefsBot è l'**unico** operatore che firma con
Web Bot Auth (19 217 richieste su 19 217) **ed è anche l'unico che
rivalida**: 22 delle 23 risposte 304 dell'intero dataset sono sue. Ma
apre **una connessione TCP per ogni richiesta**.

> Non esiste "il costo". Una politica di ammissione deve dichiarare
> quale costo sta ottimizzando. Ammettere i firmati e rifiutare i non
> firmati ammette chi spreca connessioni e risparmia banda, e rifiuta
> l'opposto.

Rilevante perché i gruppi IETF stanno costruendo l'ammissione basata
sull'identità **adesso**, senza questo dato.

**H5 — Riuso delle connessioni per operatore.** GPTBot 24,0 su 26
giorni; Google-CloudVertex 10,3; Googlebot 5,2; SemrushBot, AhrefsBot,
DotBot, Meta, Amazonbot, Applebot tutti **1,0**. *Caveat:* il
`keepalive_requests` di nginx a 1000 tronca la distribuzione, quindi
sono tutti limiti inferiori.

**H6 — Selettivo contro esaustivo, quantificato dal Gini.** Googlebot
copre il 27,3% con Gini 0,38; SERanking 0,001, AhrefsBot 0,003, GPTBot
0,072 coprono tutto quasi uniformemente. Il Gini è calcolabile da
qualunque log di accesso.

**H7 — Nessuno rivalida.** 23 risposte condizionali su 378 747 (0,0061%).
*Caveat:* il log non registra `If-None-Match`, quindi è un'inferenza dal
codice di risposta.

**H8 — Un terzo del traffico presenta user agent da browser ed è
ostile.** 130 100 richieste, **0,0% con referer**, percorsi più chiesti
`/.env`, `/.git/config`, `/wp-admin/install.php`, `/signup`. Non è
navigazione non classificata: è scansione di vulnerabilità travestita da
browser, e va separata dalle classi sotto studio.

**H9 — La classe agentica riceve 404 due volte su tre.** Claude-User
66,0%, Perplexity-User 67,0%, ChatGPT-User 49,2%, ClaudeBot 69,5% — sei
operatori indipendenti convergono su 66-69,5%, **su un sito che non
blocca nessuno**. *Aperto:* per Claude-User 200+404 somma al 66,7%,
quindi un terzo delle risposte è altro e non lo stiamo stampando. Va
verificato prima di interpretarlo.

**Dai dati Cloudflare Radar:** nella settimana del 24 agosto il traffico
agentico riceve `403` nel **52,4%** dei casi e una risposta valida nel
21,3%, contro il 62,8% di successi del training. La serie ha una rottura
nella settimana del 20 luglio, subito dopo l'annuncio Cloudflare del 1°
luglio. *Caveat obbligatorio:* anche la composizione ha un gradino nelle
stesse settimane della riclassificazione Cloudflare, quindi cambiamento
di comportamento e rietichettatura **non sono separabili**.

---

# 5. Cosa è già di altri

Questa sezione esiste perché la tentazione di rivendicare troppo è il
rischio principale del progetto.

| affermazione | chi l'ha già fatta |
|---|---|
| Il traffico a bassa località degrada la cache | Zhang, Cai, Wildani, Klimovic, *Rethinking Web Cache Design for the AI Era*, SoCC '25, doi:10.1145/3772052.3772255. **Stesso identico modello sperimentale.** |
| La degradazione della cache aumenta il carico sul backend | Stesso paper, dichiarato qualitativamente |
| Tier separati e rinvio per il traffico AI | Cloudflare blog, 2 aprile 2026: propone esplicitamente code di ammissione e rinvio dello scraping massivo. **L'idea del rinvio è loro, pubblicata prima della nostra misura** |
| La latenza esplode vicino alla saturazione | Kingman 1961, Pollaczek-Khinchine |
| Una classe in coda satura ne degrada un'altra | Head-of-line blocking, fair queueing, anni '90 |
| Il free riding nelle cache condivise | Pu et al., *FairRide*, NSDI '16. **Il termine è loro** |
| Condivisa batte partizionata in aggregato, e costa carico di database | Cidon et al., *Memshare*, ATC '17. **Il precedente più vicino a R4** |
| Il partizionamento statico scambia isolamento contro utilizzazione | Frase di apertura standard di 25 anni di letteratura sull'isolamento: Pisces, Cake, IOFlow, SQLVM, Intel CAT, NVIDIA MIG |
| Controllo di sovraccarico con priorità e scadenze | DAGOR (WeChat 2018), Breakwater (OSDI '20), Rajomon (NSDI '25), TopFull, SEDA. **Tutti presuppongono client cooperativi** |
| Scan-resistance come problema di produzione | Brooker et al., AWS Lambda, arXiv:2305.13162 |
| Conformità parziale dei crawler a robots.txt | Kim et al., IMC '25, arXiv:2505.21733. **Non misurano 503/429/Retry-After** |

**Nota importante sul paper SoCC:** due dei quattro autori sono
dipendenti Cloudflare e il lavoro è ospitato su `research.cloudflare.com`.
Il post aziendale di aprile è Cloudflare che comunica il proprio paper,
non una terza parte che lo adotta. A gennaio 2026 aveva **zero
citazioni** e 912 download.

**Una direzione esplicitamente scartata (7 settembre):** generalizzare
da "traffico AI" a "competizione fra classi per risorse condivise"
sembra rendere il lavoro più duraturo, ma **sposta il contributo nel
campo più affollato dell'informatica dei sistemi invece che in uno più
libero**. La novità vive nella specificità, non nell'astrazione: il
principio generale è quasi sempre già stato scritto da qualcuno; il caso
specifico misurato bene, quasi mai.

---

# 6. Cosa resta potenzialmente nostro

In ordine di solidità.

**N1 — Il costo unitario di una classe è endogeno alla composizione del
traffico.** Il costo per richiesta della classe agentica varia di 9,2
volte al variare della sola sua quota (R7), il rapporto fra costo
esaustivo e costo agentico va da 3× a 28×, e l'effetto sopravvive a
scadenze realistiche (R9). La classe con insieme di lavoro piccolo si
**auto-migliora**; quella esaustiva si **auto-peggiora**.

Perché potrebbe essere un buco vero: ogni controllore di ammissione
pubblicato prende il costo per classe come **input fisso** — DAGOR usa
priorità dichiarate, Rajomon un prezzo per API, UCP curve di utilità
misurate in isolamento, il weighted fair queueing pesi assegnati. Se il
costo è funzione della composizione, **il controllore cambia il proprio
input quando agisce**. Non è un fenomeno nuovo: è una specificazione
sbagliata del problema.

Conseguenza operativa misurata: strozzare la classe agentica è
controproducente in modo **sublineare** — passando dal 20% al 2% di
quota, il suo volume scende del 90% ma il suo carico all'origine scende
solo del 60%, perché le richieste che restano diventano ciascuna più
care.

**N2 — La classe più rifiutata dal web è la più economica da servire.**
Il traffico agentico ha hit ratio 0,73-0,97, costa il 2,4% del carico
all'origine pur essendo il 5% delle richieste, e riceve `403` nel 52,4%
dei casi. Il crawler di training ha hit ratio 0,13-0,25, genera il 71%
del carico, e passa nel 62,8% dei casi.

**N3 — Identità verificabile e costo sono scorrelati, in entrambe le
direzioni.** L'unico firmatario Web Bot Auth è il migliore sulla
semantica HTTP e il peggiore sul trasporto (H4). Una politica di
ammissione deve dichiarare quale costo ottimizza. Rilevante *adesso*,
perché lo standard si sta scrivendo.

**N4 — Il comportamento di campo per operatore**: riuso connessioni,
Gini di copertura, assenza di rivalidazione, carattere impulsivo del
carico, ciclo di vita di un sito nuovo. Dati che richiedevano un sito
strumentato prima di esistere.

**N5 — Una cache privata vale meno di una condivisa più piccola** (R5),
che falsifica empiricamente l'additività assunta da UCP.

---

# 7. Registro delle ritrattazioni — 15 voci

Il progetto tiene un registro di tutto ciò che è stato ritirato. Nulla
viene cancellato. **Quattro delle prime dieci sono lo stesso errore: una
spiegazione elegante costruita su una finestra parziale, formulata pochi
minuti dopo una misura interessante.**

Le più significative:

- **26 ago** — tutte le misure di hit ratio della classe esaustiva
  ritirate: offset casuale per run che rendeva il risultato una lotteria.
- **30 ago** — la campagna sul partizionamento è **nulla**: il router
  instradava le classi a cache separate anche in modalità "condivisa",
  quindi la configurazione di riferimento non esisteva. Il sintomo era
  visibile (hit ratio identico alla quarta cifra su cinque
  configurazioni) ed era stato letto al contrario, come prova che la
  contesa non esistesse.
- **30 ago** — la "banda metastabile" era il tetto dei virtual user del
  generatore: nove run avevano `vus` esattamente al limite, 6000+
  iterazioni scartate e il 18% di errori.
- **31 ago** — previsione registrata prima della misura ("il sistema
  protetto collassa per primo") **fallita**: il modello conteneva solo il
  termine di coda e ignorava quello di esposizione.
- **6 set** — tutte le misure di hit ratio per classe superate. Due cause
  sovrapposte: warm-up e misura erano invocazioni k6 separate, quindi la
  classe esaustiva rivisitava esattamente gli oggetti appena inseriti; e
  la durata di misura copriva solo il 29% di un corpus a coda pesante. Da
  qui la regola: **la durata della misura non si sceglie, si deriva dalla
  copertura del corpus**.
- **7 set** — una diagnosi intermedia (la correlazione fra ordine di
  traversata e rango di popolarità) è stata falsificata cambiando il
  moltiplicatore della permutazione: l'effetto è rimasto identico.

**Il principio, enunciato quattro volte nel log delle decisioni:** un
parametro del generatore non derivato dal carico è una variabile
incontrollata. E: la riproducibilità non è accuratezza — un bias
deterministico resta un bias, renderlo riproducibile lo rende invisibile.

---

# 8. Valutazione critica onesta

**Non abbiamo scoperto un meccanismo che nessuno sapeva potesse
esistere.** Se quello è il metro, la risposta è no.

Quello che abbiamo è: misure di meccanismi noti in un punto dove nessuno
le ha prese, una conseguenza controintuitiva che l'industria sta
sbagliando proprio adesso, dati di campo che richiedevano un sito
strumentato prima di esistere, e una condizione di validità che nessuno
ha scritto. **È un buon paper di misurazione. Non è una svolta.**

**La strada verso qualcosa di più forte non è misurare ancora: è
costruire.** N1 diventa un contributo scientifico solo se si dimostra
che rompe qualcosa, e la dimostrazione è un artefatto:

> Costruire due controllori di ammissione sullo stesso banco. Uno assume
> il costo per classe **fisso e calibrato in isolamento**, come fanno
> tutti i sistemi pubblicati. L'altro **misura il costo online** mentre
> la composizione cambia. Dimostrare che il primo converge sul punto
> operativo sbagliato, e di quanto.

Se il primo sbaglia in modo misurabile, la tesi è sistemistica: *il
controllo di ammissione con costo esogeno è mis-specificato quando le
classi condividono una cache, ed ecco l'errore che commette.* Se non
sbaglia, si scrive il paper di misurazione senza gonfiarlo.

**Criterio di arresto, deciso in anticipo:** se l'errore del costo
esogeno sul punto operativo è sotto il 10%, non vale un paper
sistemistico e si smette di cercare la svolta.

**Sui canali di impatto.** Il paper SoCC ha avuto impatto perché due
autori lavoravano nell'azienda che ha poi spedito il prodotto. Quel
canale non è replicabile. Quello disponibile è diverso e in questo
momento vale forse di più: **i gruppi IETF stanno decidendo adesso come
funzionerà l'ammissione dei bot, e stanno decidendo senza dati.** Web Bot
Auth è passato a Standards Track ad agosto 2026, non esiste ancora un
draft di working group, e l'assunzione implicita è che l'identità
verificabile serva a decidere chi far passare. H4 dice che identità e
costo sono scorrelati, e nessuno ha portato quella misura lì.

**Due artefatti previsti**, non uno: un paper di misurazione stretto e
difendibile (arXiv, poi PAM o IMC), e un rapporto ampio su come cambia
un'infrastruttura pensata per gli umani e come andrebbe riprogettata
(arXiv, blog, gruppi IETF). Il secondo diventa scrivibile quando
l'honeypot arriva a otto settimane, intorno al 7 ottobre.

---

# 9. Domande aperte

**Q1 — I crawler reali rispettano `Retry-After`?** Rischio esistenziale
per R6, e **nessuno l'ha misurato**. Testabile sull'honeypot servendo
`503` a un operatore per volta e contando chi torna. Entrambi gli esiti
sono contributi: se tornano, il conflitto fra classi è apparente e non
reale; se non tornano, il rinvio è inapplicabile finché i client non
cambiano, che è una specifica di protocollo.

**Q2 — Di quanto sbaglia un controllore a costo esogeno?** Calcolabile
sui dati esistenti prima di costruire qualsiasi cosa. È il numero che
decide se vale un paper sistemistico.

**Q3 — Confronto fra politiche sullo stesso banco:** nessuna regola /
blocco per identità / budget statico / scheduling per urgenza. È qui che
il lavoro smette di misurare e comincia a proporre.

**Q4 — La classe agentica del banco non è un agente.** Differisce dalle
altre solo per modello di accesso. Un agente vero differisce anche per
assenza di cache locale, sessione, riuso di connessione, impulsività
degli arrivi, tipo di contenuto. Variamo una dimensione su nove.

**Q5 — Il terzo di traffico honeypot con 404**: verificare l'istogramma
dei codici prima di interpretare H9.

**Q6 — Rimisurare R2 sotto il protocollo attuale.**

**Q7 — Alzare `keepalive_requests` e registrare gli header di
rivalidazione** sull'honeypot, perché H5 e H7 smettano di essere limiti
inferiori.

---

# 10. In una pagina

L'infrastruttura web assume visitatori che ripetono. I client automatici
non ripetono, ma non sono una cosa sola: il crawler di training costa
cinque volte un umano e nessuno lo aspetta; l'agente costa **meno** di
un umano e una persona lo aspetta. Il web decide per identità e il
risultato misurabile è che rifiuta il 52% della classe che costa meno e
serve il 63% di quella che costa di più.

Sul banco prova: la soglia in percentuale di traffico automatico non è
trasferibile fra macchine, quella in utilizzazione sì. La causa è la
cache, dimostrata per intervento. Le classi si sostengono a vicenda
attraverso la residenza condivisa, quindi separarle distrugge valore in
misura che dipende dal rapporto cache/contenuto. Un budget per classe
con rinvio riduce di cinque volte la latenza interattiva al costo del 3%
del lavoro totale.

E il costo per richiesta di una classe **non è una costante**: varia di
nove volte con la sua stessa quota, in direzioni opposte per classi
diverse, e sopravvive a scadenze realistiche. Tutti i controllori di
ammissione pubblicati lo assumono fisso.

Non è rivoluzionario. È un solido lavoro di misurazione con un possibile
risultato sistemistico, dati di campo che nessun altro ha, e un registro
di quindici ritrattazioni che lo rende verificabile.