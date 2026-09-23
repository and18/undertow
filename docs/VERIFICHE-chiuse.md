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
