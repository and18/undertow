# Verifiche finali — esito
**22 settembre 2026.** Chiude la fase 2 del §28 (congelamento letteratura) e la riga A4.

---

## A4 — chiusa, con i numeri

Tre ripetizioni per punto, non una:

| | servite (media ± SE) | p99 umano (media ± SE) |
|---|---|---|
| C blocco esaustiva + agentica | 84 298 ± 116 | 57,83 ± 0,44 |
| B blocco esaustiva | 87 105 ± 144 | 57,87 ± 0,59 |

- **servite:** +2 807 ± 185, **t = 15,19**, IC 95% [+2 294, +3 320]
- **p99 umano:** +0,03 ± 0,73 ms, **t = 0,05**, IC 95% **[−1,99, +2,05] ms — contiene lo zero**

**Formulazione definitiva, da usare ovunque:**

> A questo punto operativo, B serve **2 807 ± 185 richieste in piu'** di C (t = 15,2),
> con una differenza di p99 umano di **+0,03 ms, indistinguibile da zero** (IC 95%
> ±2 ms). Il blocco aggiuntivo della classe agentica costa richieste servite e non
> produce un beneficio di latenza misurabile.

Sparisce anche il problema del «C nominalmente piu' veloce»: con tre ripetizioni la
differenza e' +0,03 ms, non −0,1. Resta comunque vietata la parola «domina».

**Frontiera con barre d'errore** (pendenze ricalcolate sulle medie, sempre monotone):
0,01 → 2,22 → 3,36 → 4,02 → 10,00 → 20,98 → 102,25 ms per 1000 richieste servite in piu'.
Nota per Results: il punto **A senza politica ha SE sul p99 di ±48,6 ms** contro ±0,2÷4,0
degli altri. Il regime non governato non e' solo lento, **e' instabile**. Vale una riga.

---

## Letteratura — sette verifiche su sette, con tre correzioni

### 1-2. Il modello non e' di Che soltanto: la catena e' a tre

- **Origine:** Fagin, R. (1977), *Asymptotic miss ratios over independent references*,
  JCSS 14(2):222-250. Dimostra sotto Independent Reference Model che il miss ratio LRU
  converge a quello di un working-set con finestra T al crescere del database.
  **Il termine «characteristic time» NON e' suo.**
- **Riscoperta e nome:** Che, H., Tung, Y., Wang, Z. (2002), *Hierarchical web caching
  systems*, IEEE JSAC 20(7):1305-1314. La letteratura successiva segnala che Che et al.
  la reintrodussero **senza giustificazione teorica**, dopo che il risultato di Fagin
  era passato inosservato.
- **Formalizzazione:** Fricker, C., Robert, P., Roberts, J. (2012), *A versatile and
  accurate approximation for LRU cache performance*, ITC 24, arXiv:1202.3974. Enunciato
  verificato: t_C unica radice di C = Σ(1 − e^(−q(i)·t)), e h(n) = 1 − e^(−q(n)·t_C).
  **Conferma che la nostra scrittura miss = exp(−λ·T_C) e' corretta.**

**Correzione da applicare:** ovunque scriviamo «approssimazione di Che» va scritto
**«Fagin 1977; Che et al. 2002; formalizzata da Fricker et al. 2012»**. Attribuire il
modello al solo Che e' l'errore che un revisore di caching nota subito.

### 3-4. UCP e Cliffhanger — la nostra distinzione REGGE

- **UCP** (Qureshi & Patt, MICRO '06): utilita' definita testualmente come
  `U_a^b = miss_a − miss_b` con a, b **numero di way allocate**. La derivata e'
  ∂(miss)/∂(allocazione). Workload fissi, nessuna stima rispetto alla composizione.
- **Cliffhanger** (Cidon et al., NSDI '16): *«determines the gradient of the hit rate
  curve at the current working point»*, stimato con shadow queue che simulano **piu'
  memoria**. Anche qui ∂(hit)/∂(memoria).

> La frase «loro misurano l'utilita' contro l'allocazione, noi il costo contro la
> composizione» e' **verificata sui primari** e puo' uscire dalla quarantena. Puo'
> entrare nell'abstract.

### 5. FairRide — sopravviviamo, ma con una cautela

- **(a) CONFERMATO:** FairRide tratta esplicitamente il free-riding fra utenti che
  condividono file in cache.
- **(b) SMENTITO nella parte che ci riguarda:** lo inquadra come problema di **equita' e
  incentivi** nell'allocazione (isolation-guarantee, strategy-proofness,
  Pareto-efficiency), con una regola normativa di cost-sharing (1/k per file condiviso
  fra k utenti). **Nessuna discussione di errore o bias di misura.**

**Cautela da non ignorare.** FairRide *quantifica* il free-riding, ma in unita' di
prestazione: un utente strategico batte uno non strategico di 2,9×, e un utente puo'
perdere fino al 50% di hit ratio quando i suoi file sono «free ridden». Un revisore puo'
dire che il fenomeno e' gia' quantificato. La nostra formulazione deve quindi essere
stretta: **non** «abbiamo scoperto il free-riding», ma «quantifichiamo la sovrapposizione
degli insiemi di lavoro come **bias nella caratterizzazione sperimentale del costo di una
classe**, uso che non compare in quella letteratura».

### 6. Zhang et al. SoCC '25 — **restringe il nostro contributo, e va detto**

Riferimento esatto: Yazhuo Zhang, Jinqing Cai, Avani Wildani, Ana Klimovic,
*Rethinking Web Cache Design for the AI Era*, SoCC '25, DOI 10.1145/3772052.3772255.

- **Variano la composizione: SI.** Figura 2, proporzione di traffico AI **da 0% a 100%**,
  su Varnish, ATS e Memcached. Misurano hit ratio complessivo **e hit ratio del traffico
  umano**.
- **Misurano il costo per richiesta: NO.** Solo miss/hit ratio e unique URL ratio. Il
  costo compare in forma motivazionale, non misurata.
- **Sovrapposizione degli insiemi di lavoro: fissata, mai variata.** Setup Wikimedia con
  ~20% di contenuto condiviso; traccia sintetica con umano Zipf(1), AI a scansione
  sequenziale e **10% di overlap**. Nessuna figura fa uno sweep dell'overlap.

**Conseguenza sui nostri claim, da applicare subito:**
- **A2 si restringe.** «Misuriamo come cambia il costo di una classe al variare della
  composizione» era gia' in parte fatto da Zhang, per l'hit ratio. Quello che aggiungiamo
  e' il **costo marginale all'origine** e il **confronto di elasticita' fra tre classi**.
  Va riformulato cosi', non taciuto.
- **A1 e' intatta e diventa il contributo principale.** Zhang fissa l'overlap e non varia
  mai l'ampiezza dell'insieme di lavoro: il cambio di segno del costo marginale al
  variare dello scope non e' anticipato da nessuno.
- **A3 si rafforza.** Zhang fissa l'overlap al 10-20% senza testarne la sensibilita'.
  Il nostro risultato — spostare l'overlap cambia il lavoro all'origine di 0,71 req/s con
  t = 5,74 — indica che quella scelta e' un parametro influente. **Osservazione tecnica,
  da scrivere senza tono polemico.**

### 7. Cloudflare — la data del 15 settembre e' piu' stretta di come l'abbiamo usata

- **Tassonomia Search / Agent / Training: CONFERMATA**, annuncio del **1 luglio 2026**
  (blog `content-independence-day-ai-options`, changelog pari data). Tassonomia estesa
  dei verified bot con undici categorie.
- **Azioni: CONFERMATE.** Per categoria: blocco su tutte le pagine, blocco solo sulle
  pagine con annunci, nessun blocco. Per singolo crawler: Allow / Block / Charge
  (pay-per-crawl, **ancora private beta**), piu' enforce robots.txt e managed robots.txt.
  Risposta 403 o 402.
- **Il cambiamento del 15 settembre 2026: ANNUNCIO, e piu' ristretto.** Testo ufficiale:
  i nuovi default valgono per i **domini nuovi in onboarding** e bloccano Training e
  Agent **solo sulle pagine che mostrano annunci**; Search resta permesso. **Non e' un
  blocco di default esteso a tutta la rete**, come riportano diversi blog terzi. E **non
  esiste alcun post o changelog Cloudflare datato attorno al 15 settembre che ne
  confermi l'entrata in vigore.**
- **Cifre di costo per classe: NON ESISTONO.** Cloudflare pubblica volumi, quote e
  crawl-to-refer ratio. Nessun costo in dollari, banda o CPU per classe, nessuna misura
  di stabilita' di quel costo.

**Azione:** rileggere il Capitolo 5 gia' scritto e correggere ogni punto in cui il
cambiamento del 15 settembre e' descritto come generale o come fatto compiuto.

### 8. IETF — confermato, e combacia con l'honeypot

- **aipref** (WG): `draft-ietf-aipref-attach-05` (18 ago 2026),
  `draft-ietf-aipref-vocab-08` (13 set 2026). Nessuno ancora RFC.
- **webbotauth** (WG): `draft-ietf-webbotauth-httpsig-protocol-00` (**1 settembre
  2026**), HTTP Message Signatures su **RFC 9421**, header **`Signature-Agent`** e
  **`Signature-Input`** con `tag="web-bot-auth"`.

I campi `sig_agent` e `sig_input` del nostro log honeypot corrispondono esattamente. Il
dato C6 — 3,83% di richieste firmate, tutte da `other-bot`, zero dagli agenti dichiarati
— e' quindi una misura di adozione di un draft **adottato dal WG tre settimane fa**.
Vale una riga in Related Work.

---

## Una lacuna che resta aperta, e che non posso chiudere

**arXiv 2609.22486, *Semantics Delivery Network: Rethinking Web Retrieval Infrastructure
for LLM Agents* (settembre 2026).** Non sono riuscito a leggerlo: arXiv ha risposto
**HTTP 429** a quattro tentativi, e il paper non risulta indicizzato altrove. Per titolo
e area e' il candidato piu' vicino al nostro contributo dopo Zhang et al.

**Va letto prima di rivendicare novita'.** E' l'unica verifica della lista che resta
scoperta. Puoi aprirlo tu da browser: https://arxiv.org/abs/2609.22486

Per il resto, la ricerca sistematica non ha trovato **nessun lavoro 2025-2026 che misuri
il costo infrastrutturale per richiesta di una classe al variare della composizione o
dell'ampiezza del suo insieme di lavoro**. Il termine «marginal cost of traffic class»
in letteratura restituisce solo economia dei trasporti: nel nostro dominio non e'
occupato.

---

## Righe di claims.md da aggiornare

| riga | modifica |
|---|---|
| **A4** | da «barre d'errore da estrarre» a **MISURATO**: +2 807 ± 185 servite, p99 +0,03 ± 0,73 ms, IC 95% ±2 ms |
| **A2** | aggiungere: «Zhang et al. SoCC '25 variano gia' la composizione misurando l'hit ratio; il nostro contributo e' il costo marginale all'origine e il confronto di elasticita' fra tre classi» |
| **A3** | aggiungere: «Zhang et al. fissano l'overlap al 10-20% senza variarlo; FairRide tratta il free-riding come equita', non come bias di misura» |
| **B3, B4** | sostituire «Che 2002» con la catena **Fagin 1977 → Che et al. 2002 → Fricker et al. 2012** |
| **C6** | aggiungere il riferimento `draft-ietf-webbotauth-httpsig-protocol-00`, 1 settembre 2026, RFC 9421 |
| **nuova E** | «Il cambiamento Cloudflare del 15 settembre 2026 e' un blocco di default generalizzato» → **RESPINTO**: vale per i nuovi domini e solo sulle pagine con annunci, ed e' un annuncio senza conferma di entrata in vigore |
| **nuova apertura** | «Nessun lavoro precedente misura il costo per classe al variare dell'insieme di lavoro» → **SOSTENUTO con riserva**: resta da leggere arXiv 2609.22486 |

---

## Bibliografia per il .bbl di PAM — verifiche del 28 settembre 2026

PAM valida i riferimenti dal `.bbl`: ogni voce citata nel paper e' stata controllata sulla
fonte primaria (autori, titolo, sede, anno, pagine, DOI). Fonti: Crossref (API `works`),
pagine delle presentazioni USENIX, pagine dei post Cloudflare (metadati HTML), testo degli
Internet-Draft su ietf.org, pagina arXiv, PDF dell'autore per Zhang et al. Nessuna voce e'
stata aggiunta da memoria.

| voce | esito | dettagli |
|---|---|---|
| `cho2020breakwater` | **VERIFICATA** (USENIX) | Cho, Saeed, Fried, Park, Alizadeh, Belay, «Overload Control for µs-scale RPCs with Breakwater», OSDI '20, pp. 299-314 |
| `zhou2018dagor` | **VERIFICATA** (Crossref) | Zhou, Chen, Lin, Wang, She, Liu, Gu, Ooi, Yang, «Overload Control for Scaling WeChat Microservices», SoCC '18, pp. 149-161, doi 10.1145/3267809.3267823 |
| `cho2023protego` | **VERIFICATA** (USENIX) | Cho, Saeed, Park, Alizadeh, Belay, «Protego: Overload Control for Applications with Unpredictable Lock Contention», NSDI '23, pp. 725-738 |
| `park2024topfull` | **VERIFICATA** (Crossref) | Park, Park, Jung, Lim, Yeo, Han, «TopFull: An Adaptive Top-Down Overload Control for SLO-Oriented Microservices», SIGCOMM '24, pp. 876-890, doi 10.1145/3651890.3672253 |
| `denning1968` | **VERIFICATA** (Crossref) | CACM 11(5):323-333, 1968, doi 10.1145/363095.363141 (esiste anche la versione SOSP '67; si cita la rivista) |
| `mattson1970` | **VERIFICATA** (Crossref) | Mattson, Gecsei, Slutz, Traiger, IBM Systems Journal 9(2):78-117, 1970, doi 10.1147/sj.92.0078 |
| `waldspurger2015shards` | **VERIFICATA** (USENIX) | Waldspurger, Park, Garthwaite, Ahmad, «Efficient MRC Construction with SHARDS», FAST '15, pp. 95-110 |
| `wires2014counterstacks` | **VERIFICATA** (USENIX) | Wires, Ingram, Drudi, Harvey, Warfield, «Characterizing Storage Workloads with Counter Stacks», OSDI '14, pp. 335-349; l'abstract dice che produce MRC approssimate |
| `cloudflare2026cache` | **VERIFICATA** (pagina) | titolo «Why we're rethinking cache for the AI era», 2 aprile 2026, autori **Avani Wildani e Suleman Ahmad** (metadati `blogAuthor`). Livello separato: «routes human and AI traffic to distinct tiers»; per l'AI «cache handling could vary by task type»: RAG e riassunti in tempo reale su cache con capienza maggiore e latenza moderata, crawl di training su tier profondi (SSD lato origine) o differiti. Anche: esperimenti su algoritmi basati su ML |
| `cloudflare2026options` | **VERIFICATA** (pagina) | «Your site, your rules: new AI traffic options for all customers», 1 luglio 2026, autori Jin-Hee Lee e Bryan Becker. Il post stesso annuncia al futuro («we'll be setting») i default del 15 settembre: nuovi domini, Training e Agent bloccati sulle pagine con annunci, Search permesso. Conferma di entrata in vigore: non cercata di nuovo (resta quanto al §7) |
| `ietf-webbotauth` | **VERIFICATA**, **titolo corretto** | «HTTP Message Signatures for automated traffic» (non «for Bots»), T. Meunier (Cloudflare), S. Major (Google), 1 settembre 2026; usa `Signature-Agent` e RFC 9421 |
| `ietf-aipref-vocab` | **VERIFICATA**, **data corretta** | «A Vocabulary For Expressing AI Usage Preferences», P. Keller, M. Thomson (Ed.), **14 settembre 2026** (non 13, come scritto al §8); categorie AI Training, AI Use, Search |
| `hua2026semdn` | **VERIFICATA come preprint**; **sede NON confermata** | Peichun Hua, Yunming Xiao, arXiv:2609.22486, 18 settembre 2026. La pagina arXiv **non indica HotNets** e la lista degli accettati di HotNets 2026 non e' pubblica: citato come preprint arXiv. La lacuna della sezione precedente e' chiusa per l'abstract (letto), non per il testo completo. **Da allineare:** la riga E di `claims.md` scrive «HotNets 2026» |
| `zhang2025` | **VERIFICATA**, pagine aggiunte | SoCC '25, pp. 535-542. Rimedi letti nel PDF dell'autore (§3.1, §3.2): politiche resistenti alle scansioni (SIEVE, S3-FIFO, ARC) come filtri impliciti; gerarchia «composable» di tier differenziati con un tier condiviso per i contenuti richiesti da entrambi, «instead of strict separation»; controllori adattivi di admission, eviction e refresh. Il «learned caching» e' del blog Cloudflare, non di Zhang et al.: tolto da loro |
| `fagin1977`, `che2002` | **VERIFICATE** (Crossref), DOI aggiunti | 10.1016/S0022-0000(77)80014-7; 10.1109/JSAC.2002.801752 |
| `qureshi2006ucp` | **VERIFICATA**, **titolo completato** | «Utility-Based Cache Partitioning: A Low-Overhead, High-Performance, Runtime Mechanism to Partition Shared Caches», MICRO '06, pp. 423-432, doi 10.1109/MICRO.2006.49 |
| `cidon2016cliffhanger`, `pu2016fairride` | **VERIFICATE** (USENIX), pagine aggiunte | NSDI '16, pp. 379-392 e 393-406 |
| `fricker2012` | **PARZIALE** | autori, titolo e anno su arXiv 1202.3974; la sede ITC 24 resta quella della verifica precedente (§1-2) e **non e' stata riconfermata**: IEEE Xplore e dblp rifiutano l'accesso automatico, il PDF arXiv non la indica. Mancano pagine e DOI: **da completare da browser** |

Voci del bib non citate nel paper, quindi assenti dal `.bbl`: `megiddo2003arc`, `jiang2002lirs`,
`johnson1994twoq`, `liu2025somesite`, `tene-latency` (le ultime due ancora «check»).
