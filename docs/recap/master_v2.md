# Undertow — chiusura scientifica e piano operativo, versione 2
**22 settembre 2026.** Sostituisce integralmente la versione del 21 settembre.
Baseline: risultati dopo il controllo di separazione working-set, dopo la misura
diretta della capienza di cache, e dopo l'analisi honeypot di taratura.

**[M]** misurato · **[S]** meccanismo sostenuto · **[I]** interpretazione ·
**[D]** implicazione progettuale · **[F]** ipotesi / lavoro futuro

---

## 0. COSA CAMBIA RISPETTO ALLA VERSIONE 1

Sei correzioni, di cui due cambiano la sostanza.

1. **La capienza della cache era sbagliata di 7,75 volte.** Avevo diviso 128 MB per
   192,4 KB, che sono i byte di lavoro a PostgreSQL per richiesta misurati da
   `classcost.py`, non la dimensione dell'oggetto memorizzato da Varnish. Misura
   diretta: **5 274 oggetti, 24,8 KB l'uno**. L'insieme agentico sta a 0,19× la
   capienza, non a 1,49×. **Il "confine di residenza" e' ritirato.**
2. **Il meccanismo e' sostituito** dal tempo caratteristico della cache, che si adatta
   ai dati con zero parametri liberi — e che e' **teoria da manuale**, con conseguenze
   pesanti sulla novita' (§10).
3. «varia di un ordine di grandezza» → **«varia di circa quattro volte»**. 4,09 contro
   1,02 non e' un ordine di grandezza.
4. **«B domina C» era formalmente falso** e va riformulato: C ha p99 *nominalmente
   piu' basso*.
5. La soglia «sotto 1,1× basta il costo fisso» **e' tolta**: mai misurata.
6. Licenze e sede **non si congelano** oggi.

Piu' due risultati nuovi dall'honeypot, uno dei quali contraddice una nostra scelta di
progetto (§3.6).

---
# PARTE A — CHIUSURA SCIENTIFICA
---

## 1. PROBLEM

Un'infrastruttura web condivisa assegna capacita' finita — spazio in cache,
connessioni, CPU del backend — a richieste che oggi arrivano da popolazioni con forme
di accesso molto diverse: navigazione umana concentrata sulle risorse popolari,
crawler che attraversano il catalogo in modo esaustivo, agenti che raccolgono poche
pagine attorno a un compito. Per decidere cosa servire, rinviare o rifiutare serve una
stima di quanto costa una richiesta, e nella pratica quella stima e' associata a una
**classe**. Il problema affrontato qui e' se quell'associazione regga quando le classi
coesistono: **se il costo per richiesta di una classe resti abbastanza stabile, al
variare della composizione e dello stato condiviso, da poter essere trattato come una
proprieta' della classe.** Parte del problema e' osservata nei nostri esperimenti — la
stabilita' del costo per tre classi sintetiche su un singolo stack a tre livelli.
Parte appartiene alla domanda piu' ampia e non e' misurata qui. La formulazione non
presuppone che l'architettura attuale sia inadeguata: presuppone che la stabilita' del
costo per classe sia una proprieta' verificabile, e la verifica.

## 2. HYPOTHESIS

**A. Ipotesi ampia originaria.** *Man mano che il traffico automatizzato diventa una
componente strutturale del web, l'infrastruttura attuale resta adeguata? Dove cede,
cosa determina il cedimento, e quali proprieta' servirebbero per governare la
transizione?* **Non dimostrata**, e non dimostrabile con un testbed. E' la cornice.

**B. Ipotesi sperimentale testata.** *Su uno stack cache/applicazione/database con
capacita' finita e tre classi coesistenti, il costo per richiesta di una classe —
misurato come lavoro indotto all'origine — e' invariante rispetto alla composizione
del traffico?* Falsificabile, e falsificata per una classe su tre.

## 3. DISCOVERY

### 3.1 Il risultato centrale [M]

A capacita' di cache fissa, con tassi umano ed esaustivo fissi in valore assoluto
(55 e 28 req/s) e insiemi di lavoro decorrelati, portando la quota agentica dal 13% al
30% del carico:

| classe | miss al 13% | miss al 30% | escursione |
|---|---|---|---|
| umana | 0,227 | 0,232 | **1,02×** |
| esaustiva | 0,821 | 0,800 | **1,03×** |
| **agentica** | **0,180** | **0,044** | **4,09×** |

> **La sola composizione del traffico muove il costo per richiesta della classe
> agentica di circa quattro volte, e quello delle altre due del 2-3 per cento.**

**Precisazione necessaria, che un revisore fara' comunque.** Nell'esperimento varia il
volume della *sola* classe agentica; umano ed esaustivo restano fissi in valore
assoluto. Quindi il confronto misura, con rigore, **l'elasticita' del costo di una
classe al proprio volume** — e mostra che per umano ed esaustivo l'elasticita' al
volume *altrui* e' trascurabile. Non e' la stessa cosa di «le tre classi hanno
elasticita' diverse allo stesso stimolo», e va scritto cosi'. Il §4 spiega perche' la
distinzione, una volta capito il meccanismo, non indebolisce il risultato.

### 3.2 La serie marginale separata [M]

| tratto | Δ lavoro origine | costo marginale per richiesta agentica |
|---|---|---|
| 0 → 12 req/s | +1,238 ± 0,153 (t = +8,10) | **+0,1032 ± 0,0127** |
| 12 → 36 req/s | −0,846 ± 0,126 (t = −6,70) | **−0,0352 ± 0,0053** |
| 0 → 36 netto | **+0,392 ± 0,158 (t = +2,48)** | netto positivo |

Il marginale cambia segno al crescere della quota. Il netto e' **positivo**: aggiungere
traffico agentico aumenta il lavoro totale all'origine. Chiusura contabile:

| tratto | nuove agentiche | agentiche gia' presenti | umano | esaustivo | somma | misurato |
|---|---|---|---|---|---|---|
| 0 → 12 | +2,160 | 0 | +0,110 | −1,036 | +1,234 | **+1,238** (0%) |
| 12 → 36 | +1,056 | **−1,632** | +0,275 | −0,588 | −0,889 | **−0,846** (5%) |

Il termine dominante nel secondo tratto e' l'auto-localita' delle agentiche gia'
presenti, non un costo negativo del traffico aggiunto.

### 3.3 Il confonditore, misurato [M]

| | mappatura condivisa | mappatura separata | Δ |
|---|---|---|---|
| origine, 12 req/s | 36,950 ± 0,091 | 37,664 ± 0,085 | +0,714, **t = 5,74** |
| origine, 36 req/s | 35,806 ± 0,091 | 36,818 ± 0,094 | +1,012, **t = 7,74** |
| hit agentico, 12 | 0,881 | 0,820 | −0,061 |
| hit agentico, 36 | 0,973 | 0,956 | −0,017 |

Sotto la mappatura condivisa le 339 basi agentiche erano, per costruzione, gli oggetti
piu' popolari per la classe umana: il **62,1%** delle richieste umane vi cadeva sopra,
contro il **10,6%** dopo la separazione. La sovrapposizione fra insiemi di lavoro e' un
meccanismo causale dimostrato per manipolazione diretta.

### 3.4 Capienza della cache [M] — nuovo

Da `varnish_main_n_object` a cache piena (134,196,368 byte occupati, 21 360 liberi):

- **capienza = 5 274 oggetti**, 31,1% del corpus di 16 954
- **oggetto medio = 24,8 KB**

Sostituisce la stima di 681 oggetti della versione 1, che era sbagliata di 7,75×.

### 3.5 Contesa a monte [M]

Sotto mappatura separata il p99 umano passa da 70,3 a 76,1 ms (**t = 3,84**) mentre
l'hit umano si muove di 0,005. La pressione si propaga a una classe che non genera la
maggior parte del lavoro all'origine, senza spostamento di cache apprezzabile.

### 3.6 Taratura del generatore contro l'honeypot [M] — nuovo, e in parte scomodo

521 171 richieste, 12 agosto - 21 settembre 2026, 53 263 client, 314 520 connessioni,
sito di 18 720 pagine.

| parametro | generatore | mediana reale | media reale | p90 |
|---|---|---|---|---|
| pagine per sessione | 3 | **1** | 8,0 | 24 |
| scope (frazione del sito) | 0,0200 | **0,0008** | 0,0130 | 0,0358 |
| concentrazione | ~0,30 | **0,112** | 0,288 | — |

Il generatore sta vicino alla **media** di distribuzioni a coda pesante e lontano dalla
**mediana**. Con 31 client agentici con almeno 5 richieste, la mediana e' fragile.

**E un parametro e' contraddetto.** La contiguita' osservata per la classe `agent` e'
il **4,3%** di richieste consecutive adiacenti, contro il 50,1% di `other-bot` e il
29,1% dei browser. Il nostro generatore assume contiguita' totale dentro la sessione.
**Va in Limitations in prima pagina, non in nota.**

Composizione reale: `agent` **2,5%** del traffico, `other-bot` 43,5%, `training` 13,5%,
`search` 12,3%, browser 22,9%. I nostri esperimenti usano 13-30% di agentico: misuriamo
un regime futuro, non quello attuale, ed e' legittimo purche' dichiarato.

**Web Bot Auth [M].** 19 930 richieste su 520 038 (**3,83%**) portano una firma nei
campi `sig_agent`/`sig_input`. Tutte da `other-bot` (8,80% di quella classe); **zero**
dagli agenti dichiarati. Chi firma non si dichiara agente, chi si dichiara agente non
firma. Dato reale sull'adozione, utile in Related Work, nessun claim sul costo.

### 3.7 La frontiera decisionale [M]

λ = 185, α = 0,35, β = 0,10, cache 128 MB:

| politica | servite | p99 umano | ms per 1000 servite in piu' |
|---|---|---|---|
| C blocco esaustiva+agentica | 84 067 | 57,8 | — |
| B blocco esaustiva | 86 911 | 57,9 | 0,04 |
| rinvio budget 1 | 93 943 | 73,0 | 2,15 |
| rinvio budget 2 | 100 824 | 97,0 | 3,49 |
| rinvio budget 3 | 105 642 | 115,0 | 3,74 |
| rinvio budget 4 | 107 596 | 136,4 | 10,95 |
| rinvio budget 6 | 111 384 | 212,3 | 20,04 |
| A nessuna politica | 114 692 | 555,4 | 103,72 |

Pendenze monotone crescenti attraverso il cambio di meccanismo: blocco e rinvio
giacciono su un'unica curva convessa.

**Formulazione corretta del confronto B/C.** C ha p99 **57,8** contro 57,9 di B, quindi
e' nominalmente *piu' veloce*: parlare di dominanza di Pareto stretta e' sbagliato e la
versione 1 lo faceva. La formulazione ammessa:

> A questo punto operativo B serve **2 844 richieste in piu'** con una differenza di
> p99 umano di **0,1 ms**: non si osserva alcun beneficio misurabile dal blocco
> aggiuntivo della classe agentica.

Per dire «indistinguibile» con proprieta' servono le barre d'errore sul p99 delle
cinque ripetizioni di B e C. **Estrazione ancora da fare** (§15.A).

Spiegazione [S]: bloccare una richiesta esaustiva libera ~0,82 richieste all'origine,
bloccarne una agentica ~0,10. **C paga lo stesso prezzo in richieste servite per un
ottavo del sollievo.**

### 3.8 Validita' della metrica [M]

`CPU = 0,106 + 0,0345 × origin_rps`, R² = 0,998, residuo massimo 3,4%, su cinque
politiche e un intervallo di carico 4,5×. Proxy validato **su questo banco**, non
un'equivalenza generale.

## 4. MECHANISM

### A. Meccanismo misurato

1. Una classe altera lo stato di cache visto da un'altra (§3.3, per manipolazione).
2. La sovrapposizione fa apparire il traffico piu' economico: 6,1 punti di hit ratio.
3. Rimossa la sovrapposizione, la dipendenza dallo stato resta: 4,09×.
4. Il termine dominante e' l'auto-localita' (−1,632 su −0,889).
5. La contesa propaga pressione a monte con hit ratio fermo.

### B. Il modello: tempo caratteristico della cache

Con capienza C e tasso di miss M, un oggetto sopravvive se rivisitato entro
**T_C = C/M** (approssimazione di Che). Una classe con tasso λ su un insieme W ha
tasso per oggetto λ/W e **miss = exp(−λ·T_C/W)**.

Qui T_C = 5 274 / 37 = **143 s**. Con quel solo numero e nessun parametro libero:

| classe | λ | W | x = λT_C/W | miss previsto | miss osservato |
|---|---|---|---|---|---|
| esaustiva | 28 | 16 954 | 0,235 | **0,790** | 0,821 / 0,800 |
| umana Zipf(1) | 55 | 16 954 | distribuito | **0,249** | 0,227 / 0,232 |
| agentica | 12 | 1 017 | 1,682 | **0,186** | **0,180** |
| agentica | 36 | 1 017 | 5,046 | 0,006 | 0,044 |

Tre punti su quattro tornano. Il quarto no, e si sa perche': a x ≈ 5 il modello
uniforme sovrastima la residenza, perche' la concentrazione Zipf(0,6) *dentro* lo scope
lascia una coda fredda che continua a generare miss. **Il modello vale per x ≲ 2, e va
dichiarato cosi'.**

### C. Perche' una sola classe e' sensibile

miss = exp(−x) implica che l'elasticita' del miss al proprio volume e' esattamente −x.
Le tre classi stanno in tre regimi:

- **agentica**, insieme **limitato e piccolo** rispetto alla capienza (0,19×): x ≈ 1,7,
  regime **esponenziale**. Triplicare il volume divide il miss per e².
- **umana**, insieme **a coda pesante** (Zipf, privo di scala): sensibilita'
  **logaritmica**, perche' aumentare λ sposta solo la soglia di rango residente.
- **esaustiva**, insieme **molto piu' grande** di quanto il suo volume possa tenere
  caldo: x = 0,235, regime **lineare**, miss ≈ 1 e quasi immobile.

> **[S] La classe agentica non e' sensibile perche' e' "IA", ma perche' ha un insieme
> di lavoro limitato e piccolo rispetto alla capienza della cache. E' una proprieta'
> della forma dell'accesso — sessioni brevi su un sottoinsieme legato a un compito —
> non di chi lo genera.**

Questo chiarisce anche la precisazione del §3.1: l'asimmetria fra le classi non e'
un artefatto dell'aver variato un solo volume, perche' il modello dice che *anche
variando il volume umano* l'elasticita' umana resterebbe logaritmica. E' una
previsione, non una misura: **va nel lavoro futuro, non nei risultati.**

### D. Interpretazione residua

- [I] Il canale della contesa a monte — Varnish, pool di connessioni, thread
  dell'applicazione sugli hit — e' inferito per esclusione. Non abbiamo misurato la
  coda per stadio.
- [F] Tutto su oggetti quasi uniformi (spread 8,2%). Su oggetti eterogenei il modello
  andrebbe riscritto in byte.
- [F] La previsione del §4.C sull'elasticita' umana non e' testata.

## 5. GENERAL PRINCIPLE

Delle tre formulazioni candidate: «il costo dipende dallo stato» e' vera, nota dagli
anni '60, e i nostri dati la **restringono** (per due classi su tre la dipendenza e'
del 2-3%); «l'identita' di classe non basta» e' ambigua, perche' per umano ed
esaustivo basta benissimo; «il costo e' traffico piu' stato» e' generica.

La piu' forte difendibile, e la piu' utile perche' **discrimina**:

> **La sensibilita' del costo per richiesta di una classe al proprio volume e'
> determinata dal rapporto fra il tasso per oggetto della classe e il tempo
> caratteristico della cache. Classi con insieme di lavoro limitato e piccolo rispetto
> alla capienza stanno nel regime esponenziale e il loro costo non e' calibrabile una
> volta per tutte; classi con insieme a coda pesante o molto piu' grande della
> capienza stanno nei regimi logaritmico e lineare, e per loro un costo fisso e'
> adeguato. Il regime e' calcolabile in anticipo da tre quantita' misurabili.**

Qualificazione: *per infrastrutture web a stato condiviso con cache LRU-simile, sotto
variazione della composizione, su oggetti di dimensione omogenea.*

## 6. CURRENT INFRASTRUCTURE LIMIT

Non caricaturiamo la letteratura: UCP, Cliffhanger, Memshare, RobinHood, Breakwater,
DAGOR e Rajomon sono **tutti** sistemi adattativi che misurano lo stato in esercizio.

| dimensione | i sistemi esistenti | cosa mostrano i dati |
|---|---|---|
| identita' di classe | usata, e utilmente | **non e' il problema**: B e' sulla frontiera |
| costo fisso per classe | assunto da molte politiche operative | inadeguato **per una classe su tre**, di un fattore 4 |
| costo dipendente dallo stato | UCP, Cliffhanger, Memshare lo stimano online | come funzione dell'**allocazione**, non della **composizione** (§10, da verificare) |
| impatto marginale per richiesta | Breakwater, Rajomon reagiscono alla congestione | non attribuiscono lavoro marginale per classe |
| impatto per risorsa | RobinHood e' il piu' vicino | il nostro p99 con hit fermo e' un caso analogo |

**Delle opzioni A-F: e' B, ristretto.** Assegnare un costo fisso a una classe e'
insicuro quando quella classe sta nel regime esponenziale, e oggi in produzione non
esiste una misura che dica a un operatore quali classi ci stiano — benche', e questo e'
il punto operativo, **le tre quantita' che servono siano tutte gia' disponibili**.

## 7. TRANSITIONAL INTERNET

**A. Direttamente sostenuto.**
- La classificazione resta valida: al ginocchio il blocco per identita' della classe
  esaustiva e' sulla frontiera. [M]
- Bloccare la classe agentica costa 2 844 richieste servite senza beneficio misurabile
  di latenza. [M]
- Blocco e rinvio sono parametrizzazioni dello stesso scambio: una curva convessa. [M]
- Isolare la classe agentica rimuoverebbe un beneficio misurato: l'hit esaustivo sale
  comunque da 0,179 a 0,200 al crescere della quota agentica. [M]
- Il costo di una classe misurato in isolamento non predice il costo in mistura. [M]

**B. Implicazioni progettuali.**
- [D] Le cifre di costo per classe vanno pubblicate con la composizione e lo stato di
  cache in cui sono state misurate.
- [D] Per una classe nel regime esponenziale il rinvio con budget e' preferibile al
  blocco: controllo continuo sullo stesso scambio.
- [D] Un operatore puo' calcolare **x = λ·T_C/W** per ciascuna classe: λ dai propri
  contatori, T_C da capienza e tasso di miss (entrambi in `varnishstat`), W dai log.
  E' un conto, non un sistema.

**C. Aperto.**
- [F] Se i valori si trasferiscano a infrastrutture reali, corpora eterogenei, agenti
  reali. L'honeypot dice che il nostro agente sintetico e' vicino alla media e lontano
  dalla mediana, e che la contiguita' e' sbagliata (§3.6).
- [F] Quale valore di x giustifichi economicamente un controllo adattativo. **Non
  misurato**: la versione 1 proponeva una soglia 1,1× che era inventata.
- [F] Se un segnale di identita' verificabile sia necessario. Il 3,83% di richieste
  firmate e' un punto di partenza, non una risposta.

**Resta valido durante la transizione:** robots.txt, rate limiting, classificazione per
identita', ammissione con feedback, cache condivisa. Nessun risultato li mette in
discussione.

## 8. TO-BE INTERNET

| proprieta' | dimostrata? | implicazione? | gia' nota? | aperta? |
|---|---|---|---|---|
| classificazione / scopo | utile [M] | — | **si'** | — |
| osservabilita' dello stato | serve [S] | si' [D] | **si'** | — |
| stima del lavoro marginale | serve per alcune classi [M] | si' [D] | parzialmente | stima online: si' |
| consapevolezza multi-risorsa | motivata [M] | si' [D] | **si'** (RobinHood) | — |
| ammissione adattativa | sulla frontiera [M] | — | **si'** | — |
| rinvio / ritardo | sulla frontiera, continuo [M] | si' [D] | si' | — |
| prioritizzazione | non testata | — | si' | si' |
| feedback | — | — | **si'** | — |
| condivisione consapevole del riuso | riuso incrociato reale [M] | si' [D] | parzialmente | si' |
| **evitare l'isolamento automatico** | **si' [M]** | si' [D] | **no** | — |
| **triage per regime (x = λT_C/W)** | il regime spiega i dati [S] | **si' [D]** | il modello si', l'uso no | si' |

**L'astrazione difendibile e' un criterio, non un componente.** La letteratura sa
costruire anelli di retroazione; non ha una risposta a dove valga la pena pagarli.

## 9. SOLUTION

**Non c'e' un controllore, un protocollo o un meccanismo nuovo validato
sperimentalmente.** Il contributo e' una caratterizzazione empirica con un meccanismo
sostenuto, piu' un criterio decisionale che ne discende.

> Un'infrastruttura dovrebbe usare l'impatto marginale nello stato corrente **per le
> classi che il calcolo di x colloca nel regime esponenziale**, e puo' continuare a
> usare un costo fisso per le altre. Il regime si calcola da tasso della classe,
> ampiezza del suo insieme di lavoro e tempo caratteristico della cache — tre
> quantita' gia' misurabili in produzione.

**Non validato:** che un controllore che implementi il criterio batta uno basato sulla
classe. Non lo abbiamo costruito.

## 10. NOVELTY — la revisione ostile, dopo il cambio di meccanismo

**L'obiezione piu' pericolosa e' nuova, e nasce dal §4.B.**

> *«Il vostro 4,09× e' exp(−λT/W). L'approssimazione del tempo caratteristico e' di
> Fagin (1977) e Che et al. (2002), e il regime esponenziale per insiemi limitati e'
> una conseguenza immediata. Avete misurato una formula da manuale.»*

**E' in gran parte vero, e va concesso in apertura invece che difeso.** Il modello non
e' nostro, si adatta ai nostri dati con zero parametri liberi, ed e' esattamente questo
che lo rende credibile. Il contributo **non e' il modello**.

Cosa resta, dopo aver concesso:

1. **Che nel traffico web reale una classe stia nel regime esponenziale e le altre no,
   e che sia la classe emergente.** Il modello dice che *puo'* accadere; la misura dice
   che *accade*, per questa forma di accesso, con queste ampiezze — e l'honeypot dice
   che quella forma e' quella osservata sugli agenti veri.
2. **La quantificazione del confonditore da sovrapposizione** (§3.3): 6,1 punti di hit
   ratio e 0,71 req/s. Chiunque caratterizzi il costo di una classe su un corpus
   condiviso deve controllarlo o dichiararlo. Non ho trovato questo uso in letteratura.
3. **La conseguenza decisionale misurata** (§3.7): il rapporto 8× fra i costi marginali
   delle due classi bloccabili, e le 2 844 richieste che il blocco della classe
   sbagliata costa senza comprare latenza.
4. **L'uso del modello come criterio di triage per classi**, con le tre quantita' gia'
   disponibili in produzione. Il modello e' vecchio, questo impiego non l'ho trovato.

| lavoro | cosa NON stabilisce rispetto a noi |
|---|---|
| **Fagin '77, Che '02, Fricker '12** | sono il nostro modello: **non rivendichiamo nulla di teorico** |
| **UCP, Cliffhanger, Memshare** | misurano utilita' contro **allocazione**, non costo contro **composizione** — *da verificare sui primari prima di congelare* |
| **RobinHood** | latenza di coda multi-backend; non classi di traffico ne' composizione |
| **FairRide** | il free-riding e' il suo tema; noi lo misuriamo come **confonditore di misura** |
| **Bonfire** | riscaldamento cache; non costo per classe |
| **Breakwater, DAGOR, Rajomon** | ammissione con feedback; nessuno stato di cache, nessuna attribuzione marginale per classe |
| **Zhang et al. SoCC '25** | misura sotto composizione data; non varia la composizione ne' controlla la sovrapposizione — *da verificare* |
| **Cloudflare 2026** | modello di costo implicito per classe; nessuna misura pubblicata della sua stabilita' |
| **IETF aipref, webbotauth** | identita' e preferenze, ortogonali al costo |

**Delta difendibile, onestamente enunciato:** una caratterizzazione empirica che
identifica quale classe sta in quale regime in un carico web a tre classi; la
quantificazione di un confonditore di misura; una conseguenza decisionale; e l'uso di
un modello noto come criterio di triage. **Non c'e' un principio piu' fondamentale
nascosto qui, e non c'e' teoria nuova.**

---
# PARTE B — CLAIM, REVISIONE, DECISIONE
---

## 11. CLAIM LADDER

**LIVELLO 1 — misurato direttamente**
- Escursione del miss ratio al proprio volume: 4,09× agentica, 1,03× esaustiva,
  1,02× umana, a cache fissa e insiemi separati.
- Capienza 5 274 oggetti, oggetto medio 24,8 KB.
- Separare gli insiemi aumenta il lavoro di 0,71 e 1,01 req/s (t = 5,74 e 7,74).
- Marginale agentico +0,1032 ± 0,0127 al 13%, −0,0352 ± 0,0053 al 30%.
- Netto 0 → 36 **positivo**: +0,392 ± 0,158.
- B serve 2 844 richieste in piu' di C con 0,1 ms di differenza sul p99.
- Otto politiche su una curva convessa a pendenza monotona.
- CPU = 0,106 + 0,0345 × origin_rps, R² = 0,998.
- p99 umano +5,8 ms con hit umano fermo.
- Honeypot: contiguita' agentica 4,3%; scope mediano 0,0008; 3,83% firmate.

**LIVELLO 2 — fortemente sostenuto**
- La sovrapposizione e' causale, non correlazione.
- Il termine dominante nel secondo tratto e' l'auto-localita'.
- Il tempo caratteristico spiega tre classi su quattro punti con zero parametri liberi.
- All'operating point della frontiera l'esaustiva costa ~8× l'agentica per richiesta.

**LIVELLO 3 — interpretazione ragionevole**
- Il regime (esponenziale / logaritmico / lineare) spiega quale classe e' sensibile.
  **Sotto test adesso** (§12).
- La degradazione del p99 umano e' contesa a monte.

**LIVELLO 4 — ipotesi**
- Che x sia stimabile online a basso costo.
- Che un controllore che lo usa batta uno class-based.
- Che l'elasticita' umana resti logaritmica variando il volume umano.
- Che i valori si trasferiscano al traffico reale.

**LIVELLO 5 — da NON dire**

| affermazione | verdetto |
|---|---|
| "il traffico IA e' intrinsecamente costoso" | respinta |
| "il traffico agentico e' sempre cache-friendly" | respinta |
| "il traffico agentico fa risparmiare lavoro" | respinta, netto +0,392 |
| "B domina C" / "C e' Pareto-dominata" | **respinta**: C ha p99 nominalmente minore |
| "le politiche basate sulla classe falliscono" | respinta: B e' sulla frontiera |
| "le politiche statiche sono obsolete" | respinta: adeguate per 2 classi su 3 |
| "serve una nuova architettura" | respinta |
| "il controllo in retroazione e' una novita'" | respinta |
| "abbiamo un nuovo modello di cache" | **respinta**: il modello e' di Che, 2002 |
| "soglia universale ρ ≈ 0,9" | respinta |
| "sotto 1,1× basta il costo fisso" | **respinta**: mai misurata |
| "origin RPS = carico backend" | da qualificare sempre |
| "il partizionamento e' dannoso in generale" | da qualificare |
| "il nostro agente sintetico rappresenta gli agenti reali" | **da qualificare**: contiguita' 4,3% contro 100% |

## 12. ESPERIMENTI — stato

**Lo sweep di AGENT_SCOPE e' in corso**, lanciato il 21 settembre alle 21:49 UTC,
`AGENT_MUL=3266489917` e `AGENT_SCOPE=0.06` verificati in `env.txt`. Quattro punti,
conclusione attesa ~03:10 UTC.

Previsione registrata prima del lancio, in `PREREGISTRAZIONE-scopesweep.md`:

| scope | W/capienza | rapporto miss(12)/miss(36) previsto |
|---|---|---|
| 0,02 | 0,19 | **4,09** (misurato) |
| 0,06 | 0,58 | **≈ 3,1** |
| 0,20 | 1,93 | **≈ 1,4** |

Falsificazione: monotonia decrescente con scarti ≥ 2 SE combinati; **r(0,20) < 2,0**
(soglia derivata dal modello, non dai dati); entrambi entro ±30%.

**Dopo questo, chiusura definitiva**, qualunque sia l'esito. Se fallisce, resta la
caratterizzazione empirica senza meccanismo: livello 2, piu' debole, pubblicabile.

## 13. FINAL SCIENTIFIC CONTRIBUTION

**1. Caratterizzazione empirica.** Su uno stack web a tre livelli con capacita' finita,
la sensibilita' del costo per richiesta al proprio volume differisce fortemente fra
classi coesistenti: portando la quota agentica dal 13% al 30% a capienza fissa, il miss
ratio agentico cambia di 4,09× mentre umano ed esaustivo cambiano di 1,02× e 1,03×. La
conseguenza decisionale e' misurata al ginocchio: bloccare la classe agentica costa
2 844 richieste servite senza beneficio misurabile di latenza, perche' il suo costo
marginale e' un ottavo di quello della classe esaustiva.

**2. Un confonditore di misura, quantificato.** La sovrapposizione fra l'insieme di
lavoro di una classe e la testa popolare di un'altra fa apparire quella classe
sostanzialmente piu' economica: decorrelandola, l'hit agentico scende di 0,061 e il
lavoro all'origine sale di 0,71 req/s (t = 5,74). Chiunque caratterizzi il costo di una
classe su un corpus condiviso deve controllarlo o dichiararlo.

**3. Un criterio di triage, da un modello noto.** L'approssimazione del tempo
caratteristico prevede tre dei nostri quattro punti con zero parametri liberi e
identifica il regime di ciascuna classe da x = λ·T_C/W. Poiche' le tre quantita' sono
gia' misurabili in produzione, il criterio dice **dove** serve una decisione
consapevole dello stato e dove un costo fisso basta. Il modello non e' nostro; il suo
uso come triage per classi di traffico non l'abbiamo trovato in letteratura.

## 14. PAPER / THESIS STRUCTURE

### Paper

| § | scopo | claim ammessi | claim vietati | figure |
|---|---|---|---|---|
| 1 Introduction | il problema | i tre contributi | "nuova architettura" | FIG-01 |
| 2 Background | posizionamento, **con Che/Fagin in apertura** | "il modello non e' nostro" | "i sistemi esistenti sono statici" | — |
| 3 Methodology | riproducibilita' | proxy validato su questo banco | "origin rps = backend" | TABLE-01 |
| 4 Results | i fatti | solo livello 1 | ogni interpretazione | FIG-02..05, TABLE-02 |
| 5 Mechanism | il modello e lo sweep | livelli 1-2, 3 se lo sweep regge | attribuire il canale di contesa | FIG-06, TABLE-03 |
| 6 Implications | il criterio | solo [D], etichettate | "proponiamo un controllore" | — |
| 7 Limitations | dichiarare | — | difendersi | — |
| 8 Conclusion | chiudere | — | futuro come fatto | — |

**Limitations deve aprire con la contiguita' 4,3%**, perche' e' il punto in cui il
nostro generatore diverge dalla realta' che diciamo di modellare.

### Tesi

Il paper piu': un capitolo sulla transizione (§7 con la separazione A/B/C); il
capitolo 5 gia' scritto, riallineato ai numeri corretti; e un'**appendice sulle
ritrattazioni**. Quattro affermazioni ritirate con i controlli che le hanno uccise. In
un paper sarebbe fuori posto; in una tesi e' il capitolo che dimostra metodo.

---
# PARTE C — PIPELINE OPERATIVA
---

## 15. RESEARCH / LITERATURE FREEZE

**A. Da verificare, obbligatorio.**
- **Che et al. 2002 e Fagin 1977**: enunciare correttamente l'approssimazione e
  attribuirla. Aggiunti in v2, sono ora la base del §4.
- **UCP, Cliffhanger**: verificare sui primari la frase «utilita' contro allocazione».
  Finche' non e' verificata **non entra nell'abstract**.
- **FairRide**: verificare se quantificano il free-riding come errore di misura. Se si',
  il contributo 2 si indebolisce.
- **Zhang et al. SoCC '25**: verificare se variano la composizione. Se si', il
  contributo 1 si restringe.
- **Cloudflare 2026**: solo post ufficiali datati, mai commentari secondari.
- **IETF aipref, webbotauth**: stato dei draft.
- **Estrazione delle barre d'errore sul p99 di B e C** (§3.7).

**B. Opzionale.** MemExchange; lavori 2025-2026 su infrastrutture per agenti.

**C. Sufficiente.** Memshare, RobinHood, Bonfire, Breakwater, DAGOR, Rajomon, Kingman.

## 16. EVIDENCE FREEZE

| evidenza | ruolo |
|---|---|
| **Separazione working-set (21 set)** | **PRIMARIA** |
| **Sweep di AGENT_SCOPE (in corso)** | **PRIMARIA se regge** |
| **Frontiera, 8 punti** | **PRIMARIA** |
| **Capienza da varnishstat** | **PRIMARIA** — fonda il §4 |
| **Honeypot, taratura** | **PRIMARIA** — validita' esterna e Limitations |
| **Validazione CPU R² = 0,998** | **PRIMARIA** — valida la metrica |
| R2 intervento causale; R6 budget | secondarie |
| R8 riletta come contesa; R9 TTL e durata | secondarie, robustezza |
| R10 pool DB | validazione infrastrutturale |
| R1 soglia; R4 partizionamento; R5 cache privata | background |
| R3 free-riding | **RILETTA** come confonditore |
| Serie a mappatura condivisa | **RITIRATA** come evidenza centrale |
| Elasticita' 9× e 280× | **RITIRATE** |
| "il traffico agentico riduce il lavoro" | **RITIRATA** |
| "il rinvio domina il blocco" | **RITIRATA** |
| "B domina C" | **RITIRATA** nella forma di dominanza |
| "confine di residenza a 681 oggetti" | **RITIRATA** — capienza sbagliata di 7,75× |
| Campagna del 20 set senza AGENT_MUL | **INVALIDA** — no-op |

## 17. DATA / ARTIFACT ARCHIVE

**A. Evidenza da pubblicare.** `points.csv` e `env.txt` di ogni run primario; JSON k6
dei primari; configurazioni di generatore, compose, pinning; manifesto del corpus
(495 libri, 16 954 capitoli, ID Gutenberg, oggetto medio 24,8 KB, spread 8,2%); semi;
**l'output honeypot aggregato**, senza IP.

**B. Riproducibilita'.** Script di campagna; digest delle immagini; versioni dei
pacchetti; finestre e gate; script di analisi e figura.

**C. Archivio interno.** Serie a mappatura condivisa; run invalidi; Grafana; Prometheus.

**D. Rimovibili.** Temporanei, log di debug, esperimenti senza CSV.

**E. Deprecati ma conservati.** `archive/retired/` con README.

**Vincolo assoluto:** i log honeypot contengono IP in chiaro. Restano in `.gitignore`.
Si pubblica solo l'output aggregato di `honeypot_scope.py`, che per costruzione non
stampa IP.

## 18. WRITING PIPELINE

```
undertow/
  README.md
  paper/     paper.md · references.bib · claims.md
  docs/      methodology.md · results.md · mechanism.md · limitations.md
             retractions.md · registry.csv
  experiments/   analysis/   figures/
  data/      evidence/ · validation/ · robustness/
  archive/retired/
```

Fonte di verita': `paper/paper.md` per il testo, `docs/registry.csv` per i fatti,
`references.bib` per le citazioni. **Nessun numero scritto a mano in paper.md**;
`claims.md` lega ogni affermazione alla riga di dati, alla figura e al falsificatore.

## 19. WRITING ORDER

`registry.csv + claims.md` → figure → Results → Methodology → Mechanism → Limitations →
Related Work → Implications → Introduction → Abstract → Conclusion.

Il risparmio viene da tre scelte: la mappa claim-evidenza prima della prosa, i
risultati separati dall'interpretazione, l'introduzione scritta quando non c'e' piu'
nulla da scoprire.

## 20. FIGURE E TABELLE

| id | contenuto | sorgente | risultato | dove |
|---|---|---|---|---|
| **FIG-01** | escursione del miss ratio per classe | 21 set | 1,02× / 1,03× / 4,09× | paper §1, §4 |
| **FIG-02** | lavoro all'origine contro quota agentica, condivisa e separata | 20-21 set | massimo interno, traslazione | paper §4 |
| **FIG-03** | frontiera a 8 punti, C evidenziata | 19-20 set | curva convessa | paper §4 |
| **FIG-04** | scomposizione contabile, barre impilate | 21 set | chiude a 0% e 5% | paper §5 |
| **FIG-05** | CPU contro origin rps | politiche | R² = 0,998 | paper §3 |
| **FIG-06** | **elasticita' contro W/capienza, con la curva del modello** | sweep | previsto 4,09 / 3,1 / 1,4 | **paper §5** |
| FIG-A1 | gradiente al ridursi della cache | 10-11 set | −2,88 → −0,34 | appendice, etichettata condivisa |
| FIG-A2 | p99 umano contro quota, con hit sovrapposto | 21 set | +5,8 ms, hit fermo | appendice |
| **FIG-A3** | **honeypot: distribuzioni di sessione, scope, contiguita'** | honeypot | taratura e divergenze | **appendice** |
| TABLE-01 | banco e protocollo | — | — | paper |
| TABLE-02 | i punti separati, 5 ripetizioni | 21 set | — | paper |
| TABLE-03 | **modello contro osservato, 4 punti** | §4.B | 3 su 4 con zero parametri | **paper** |
| TABLE-04 | registro esperimenti, ritirati inclusi | registry | — | appendice |

FIG-06 e TABLE-03 sono le due che reggono il §5. Nessuna figura da Grafana: resta
osservabilita' operativa, una dashboard lab e una honeypot.

## 21. FIGURE PIPELINE

```
data/evidence/<run>/points.csv  →  analysis/prepare.py  →  data/derived/<nome>.csv
  →  analysis/fig_NN_<nome>.py  →  figures/FIG-NN.pdf + .caption.txt + .provenance.txt
```

`make figures` rigenera tutto. Nessun grafico ritoccato a mano. Verifica: cancellare
`figures/` e rieseguire deve produrre file identici.

## 22. WEBSITE

**Utile** solo dopo il deposito: una pagina con abstract, FIG-01, link al PDF e al
repo. **Overhead** qualunque cosa interattiva adesso; il vecchio breakpoint calculator
basato sul ginocchio e' incoerente col contributo e va abbandonato. **Minimo:** pagina
statica con titolo, abstract, FIG-01 e FIG-03, due link, una riga sui limiti.

Se piu' avanti servira' qualcosa di interattivo, l'unica cosa coerente e' un
**calcolatore di x = λ·T_C/W**: si inseriscono tasso della classe, ampiezza
dell'insieme, capienza e tasso di miss, e si legge il regime. E' il §13.3 reso usabile.

## 23. INTERNAL REVIEW — lista eseguibile

1. Ogni numero nel paper risale a `registry.csv` o a un CSV in `data/`.
2. Ogni claim in `claims.md` ha livello, evidenza, figura, falsificatore.
3. Nessun numero ritirato nel testo. Grep esplicito su: `9×`, `280×`, `681`,
   `192,4 KB` come dimensione d'oggetto, `0,881`, `0,973`, "domina", "riduce il lavoro",
   "ordine di grandezza", "1,1×".
4. Ogni figura ha `provenance.txt` e si rigenera con `make figures`.
5. Ogni affermazione in Related Work ha una fonte primaria datata.
6. Ogni [D] e' etichettata e non compare in Results.
7. L'abstract contiene solo livello 1 e 2.
8. La metodologia scritta corrisponde agli script.
9. Per ogni risultato: «quale variabile e' cambiata insieme a quella che credo di aver
   manipolato?». E' la domanda che ha scoperto la sovrapposizione.
10. Nessuna frase del livello 5.
11. Grep su IP nei file pubblicati.
12. **La revisione la esegue chi non ha seguito il lavoro**, o a distanza di almeno
    tre giorni dalla scrittura.

## 24. REPRODUCIBILITY AUDIT

**Riproducibile:** immagini con digest; versioni; pinning; configurazione del generatore
**compresi tutti i parametri agentici**; corpus (ID e schema, non i testi); semi;
warmup, finestra, gate; script; test statistici; CSV di riferimento.

**Non riproducibile esattamente, e va scritto:** i valori assoluti di latenza dipendono
dalla macchina (Ampere Neoverse-N1, 6 core fisici senza SMT) e dal vicinato cloud; il
ginocchio si sposta con la configurazione. **Devono riprodursi i rapporti e i segni** —
4,09× contro 1,02×, il cambio di segno del marginale, l'ordine sulla frontiera — non i
millisecondi.

## 25. REPOSITORY CLEANUP

| categoria | contenuto |
|---|---|
| **PUBLIC** | paper, figure, script, CSV di evidenza, `env.txt`, manifesto corpus, compose, README, LICENSE, CITATION.cff, registry.csv, retractions.md, output honeypot aggregato |
| **PRIVATE** | log honeypot grezzi, credenziali, dettagli di rete, snapshot Prometheus |
| **ARCHIVED** | serie a mappatura condivisa, run invalidi, Grafana |
| **REMOVE** | temporanei, debug, script abortiti |
| **DEPRECATED** | `archive/retired/` con README |

**Le ritrattazioni non si nascondono e non si mescolano.** `docs/retractions.md` e' un
documento di prima classe, linkato dal README: per ciascuna dice cosa affermavamo, su
quale evidenza, cosa l'ha falsificata, cosa la sostituisce. I dati che le sostenevano
stanno in `archive/retired/`, **non** in `data/evidence/`.

**Licenze: da decidere alla fase 8, non ora.** Il vincolo fermo e' che i testi
Gutenberg **non si ridistribuiscono**: si pubblicano ID e schema.

## 26. PUBLIC REPOSITORY

Struttura del §18, piu' `LICENSE`, `CITATION.cff`, `CHANGELOG.md`, `Makefile`
(`make figures`, `make check`).

README in una pagina, in quest'ordine: **problema** (il costo per classe e' calibrabile
una volta?); **contributo** (i tre punti del §13); **esperimenti** (il registro coi
ruoli e i ritirati visibili); **riproduzione** (`make figures`, piu' la nota del §24 su
cosa si riproduce e cosa no); **il paper**; **limiti** (sintetico, un corpus, una
macchina, oggetti omogenei, contiguita' del generatore contraddetta dall'honeypot).

## 27. RELEASE PIPELINE

```
esito dello sweep
  → evidence freeze
  → literature freeze            (parallelo, indipendente)
  → figure                        (dipende da evidence)
  → scrittura                     (dipende dalle figure)
  → reproducibility audit         (parallelo alla scrittura)
  → internal review
  → repository cleanup
  → arXiv                         <- per primo, e' il timestamp
  → repository pubblico           (contestuale: il paper deve linkarlo)
  → venue selection → submission
  → IETF / sito / LinkedIn
```

**La sede si sceglie dopo il paper freeze**, verificando page limit e policy sui
preprint, non come conseguenza dell'esito dello sweep. L'unico vincolo d'ordine reale
e' che arXiv venga per primo.

---
# PARTE D — PIANO MASTER
---

## 28. ROADMAP

| fase | azioni | criterio di uscita | dipende da |
|---|---|---|---|
| **0 — sweep** | in corso dal 21/09 21:49 UTC | i 4 punti hanno gate superato | — |
| **1 — evidence freeze** | `registry.csv`; ritirati in `archive/`; `retractions.md` (4 voci) | ogni run ha un ruolo; zero "da decidere" | 0 |
| **2 — literature freeze** | le 7 verifiche di §15.A | tutte chiuse | nessuna |
| **3 — claims map** | `claims.md` con 5 colonne | ogni claim completo | 1, 2 |
| **4 — figure** | FIG-01..06 + A1..A3 | `rm -rf figures && make figures` identico | 1, 3 |
| **5 — scrittura** | ordine del §19 | ogni numero risale a un CSV | 4 |
| **6 — review** | i 12 punti del §23 | 12 su 12 | 5 |
| **7 — repro audit** | §24 | un terzo rigenera le figure | 1, 4 |
| **8 — cleanup + licenze** | §25 | grep IP pulito; nessun numero ritirato | 6, 7 |
| **9 — rilascio** | arXiv, poi repo | DOI ottenuto | 8 |
| **10 — sede e sito** | selezione, submission, sito minimo | — | 9 |

## 29. STOP-LIST

- Nessun esperimento oltre lo sweep in corso, salvo lacuna bloccante in fase 6.
- Nessun riuso dei numeri ritirati: 9×, 280×, **681 oggetti**, **192,4 KB come
  dimensione d'oggetto**, hit 0,881 e 0,973 come risultato, "riduce il lavoro",
  "il rinvio domina", "B domina C", "ordine di grandezza", "soglia 1,1×".
- Nessuna riapertura di metodologia risolta: warmup 300, finestra 620, pinning, gate.
- Nessun controllore inventato per rafforzare la novita'.
- **Nessuna rivendicazione teorica sul modello del tempo caratteristico: e' di Che e
  Fagin, e va attribuito in apertura del Background.**
- Nessuna affermazione che una nuova architettura sia stata validata.
- Nessuna espansione della letteratura oltre §15.A.
- Nessun lavoro sul sito prima di arXiv.
- Nessuna figura da Grafana.
- **Nessun ragionamento sull'esito di un controllo prima di averlo eseguito.** E'
  l'errore che ho commesso tre volte in questo progetto.
- Nessun lancio senza verificare `env.txt` trenta secondi dopo.
- **Nessun numero derivato per divisione senza aver verificato cosa misura il
  divisore.** E' l'errore dei 681 oggetti, e mi e' costato un meccanismo intero.

## 30. FINAL DECISION

**A. Chiuso.** La fase sperimentale tranne lo sweep in corso. Il contributo, nei tre
punti del §13. Il principio, nella formulazione del §5. Quattro ritrattazioni. La cache
separata: eliminata definitivamente.

**B. Resta.** L'esito dello sweep, che decide se il §4.B entra come verificato o come
interpretazione. Poi le dieci fasi del §28.

**C. Non necessario.** Cache separata; serie marginale al ginocchio; sweep della cache
sotto separazione; stimatore online; controllore; ricalibrazione del generatore sulla
mediana honeypot. Tutto in Future Work.

**D. Prossimo artefatto.** `registry.csv`, appena lo sweep chiude.

**E. Progetto finito quando** il preprint e' su arXiv, il repository si rigenera da
solo con `make figures`, e un lettore che non ha seguito il lavoro capisce problema,
contributo e limiti dal README in una pagina.

> **Prossima azione, in una frase:** leggere `/tmp/scopesweep.log` dopo le 03:10 UTC e
> confrontare i due rapporti con 3,1 e 1,4 della pre-registrazione.

---

## MASTER PLAN SUMMARY

**Problema.** Il costo per richiesta di una classe e' abbastanza stabile, al variare
della composizione e dello stato condiviso, da essere trattato come proprieta' della
classe?

**Ipotesi.** Ampia: come deve adattarsi l'infrastruttura mentre il traffico
automatizzato diventa strutturale (cornice, non dimostrata). Sperimentale: il costo per
richiesta e' invariante rispetto alla composizione (falsificata per una classe su tre).

**Scoperta.** A cache fissa e insiemi separati, portando la quota agentica dal 13% al
30%, il miss ratio agentico cambia di **4,09×**, l'umano di **1,02×**, l'esaustivo di
**1,03×**.

**Principio.** La sensibilita' e' determinata da x = λ·T_C/W: insieme limitato e piccolo
rispetto alla capienza → regime esponenziale e costo non calibrabile; coda pesante o
insieme molto piu' grande della capienza → logaritmico o lineare, costo fisso adeguato.
Il regime si calcola in anticipo da tre quantita' misurabili.

**Limite.** Un costo fisso e' insicuro per le classi nel regime esponenziale, e oggi in
produzione non esiste una misura che dica quali lo siano — benche' le tre quantita'
necessarie siano gia' disponibili.

**Transizione.** La classificazione resta valida e sulla frontiera; bloccare la classe
agentica costa 2 844 richieste senza beneficio misurabile; le cifre di costo per classe
vanno pubblicate con la composizione in cui sono state misurate.

**To-be.** Un criterio di triage, non un componente.

**Contributo.** Caratterizzazione empirica + confonditore di misura quantificato +
criterio di triage da un modello noto. Nessun sistema nuovo, **nessuna teoria nuova**.

**Esperimenti.** Uno in corso, pre-registrato, chiusura definitiva al suo esito.

**Prossimo artefatto.** `registry.csv`.

**Completamento.** arXiv, repository che si rigenera, README di una pagina.