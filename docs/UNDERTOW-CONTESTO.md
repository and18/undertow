# Undertow — documento di contesto
**22 settembre 2026, numeri aggiornati il 23 settembre** (vedi `claims.md` v3). Questo file e' tutto cio' che serve per riprendere il progetto in
una chat nuova. Non rileggere le conversazioni precedenti: contengono sei
interpretazioni poi ritirate, e questo documento le tiene fuori per costruzione.

---

## 0. REGOLE DI PRECEDENZA — leggere per prime

| fonte | ruolo |
|---|---|
| **`docs/claims.md`** | **verita' su cosa possiamo affermare** e con quale stato |
| **`docs/VERIFICHE-chiuse.md`** | **verita' sui numeri finali** e sulla letteratura |
| `docs/undertow-master-v2.md` | **struttura di lavoro**, non fonte numerica: contiene ancora lo sweep «in corso» e i vecchi numeri di A4 |
| `docs/RISULTATO-scopesweep.md` | esito dello sweep e sua interpretazione |
| `docs/retractions.md` | da scrivere — le sei ritrattazioni |

**Regola d'oro: se master_v2 e claims.md dicono numeri diversi, vince claims.md.**

---

## 1. LE TRE PIPELINE — non confonderle

### 1A. Pipeline di ricerca e rilascio — *come portiamo il lavoro alla pubblicazione*

```
RESEARCH  (chiusa)
   ↓
evidence freeze  ←── SIAMO QUI
   ↘ literature freeze  (fatta, § 7)         ← parallela
        ↓
   claims map  (fatta, docs/claims.md)
        ↓
     figures
        ↓
     writing
        ↘ reproducibility audit               ← parallela
             ↓
      internal review
             ↓
     repository cleanup
             ↓
           arXiv                               ← per primo, e' il timestamp
             ↓
     public repository                         ← contestuale: il paper lo linka
             ↓
     venue selection → submission              ← la sede si sceglie DOPO il paper freeze
             ↓
     dissemination (IETF, sito, LinkedIn)
```

### 1B. Spina dell'argomento scientifico — *come costruiamo la storia*

```
PROBLEM → HYPOTHESIS → DISCOVERY → MECHANISM → GENERAL PRINCIPLE
   → CURRENT INFRASTRUCTURE LIMIT → TRANSITIONAL INTERNET → TO-BE PROPERTIES
   → DECISION CRITERION → NOVELTY / PRIOR ART → CONTRIBUTIONS
```

Espressa come catena narrativa, che e' la forma da tenere in mente scrivendo:

> **Cosa osserviamo → perche' succede → quale principio generale ne ricaviamo → dove
> l'approccio corrente ha un limite → cosa dovrebbe conoscere l'infrastruttura → che
> decisione dovrebbe poter prendere.**

### 1C. Ordine di scrittura — *come materialmente si scrive*

```
registry.csv + claims.md → figures → Results → Methodology → Mechanism
  → Limitations → Related Work → Implications → Introduction → Abstract → Conclusion
```

L'introduzione **non** si scrive prima di aver capito cosa abbiamo trovato.

---

## 2. LE QUATTRO DOMANDE ORIGINARIE

Sono la cornice, e il risultato sperimentale e' **l'evidenza per Q4**, non la tesi intera.

- **Q1 IMPACT.** Cosa cambia quando cambia la composizione del traffico — non in
  richieste al secondo, ma in lavoro indotto su cache, origine, database.
- **Q2 BREAKING POINT.** Quando e perche' il sistema cede: volume, composizione,
  utilizzo, insieme di lavoro, risorse condivise.
- **Q3 TRANSITION.** Come possono convivere umano, search, training e agentico:
  classificazione, blocco, rinvio, budget, cache condivisa.
- **Q4 TO-BE.** Cosa deve sapere l'infrastruttura per decidere correttamente. La
  risposta che i dati sostengono: **ampiezza dell'insieme di lavoro + costo marginale +
  effetto sugli altri workload → decisione.**

---

## 3. IL BANCO

OCI Ampere Neoverse-N1, 6 core fisici senza SMT, 23 GB RAM, aarch64. Catena Docker:
k6 (core 0) → Varnish (1) → gunicorn/Flask 8 thread (2) → PostgreSQL (3-5).
Corpus: 495 libri Gutenberg, **16 954 capitoli**, oggetto medio **24,9 KB**.
Cache 128 MB = **5 263 ± 8 oggetti**, circa il 31% del corpus (misurato da
`varnish_main_n_object` a cache piena, non stimato; claims C2).

Generazione di carico a ciclo aperto (`constant-arrival-rate`). Protocollo fisso:
`WARMUP=300`, `MEASURE=620` derivato dalla copertura del corpus, gate di validita' per
run, riferimento di deriva ripetuto in testa e in coda.

Tre classi: **umana** Zipf(1) su tutto il corpus · **esaustiva** traversata uniforme ·
**agentica** 3 capitoli contigui da una base estratta Zipf(0,6) su uno scope del corpus.
Parametri agentici: `AGENT_SCOPE` (0,02 default), `AGENT_SESSION` 3, `AGENT_SKEW` 0,6,
`AGENT_MUL` (2654435761 default, **3266489917** = insieme separato da quello umano).

Proxy validato del carico di backend (PostgreSQL, core 3-5), **solo su questo banco**:
`CPU = 0,021 + 0,0368 × origin_rps`, R² = 0,997, residuo massimo 3,1% (`tools/cpu_validation.py`).

---

## 4. I NUMERI CONGELATI

### 4.1 Costo marginale agentico contro ampiezza dell'insieme di lavoro — *il risultato principale*

Mappatura separata, cache fissa, umano 55 req/s ed esaustivo 28 req/s fissi in valore
assoluto, quota agentica da 13% a 30%:

| scope | W nominale | W/capienza | origine @13% | origine @30% | **marginale per richiesta** |
|---|---|---|---|---|---|
| 0,02 | 1 017 | 0,19 | 37,66 ± 0,08 | 36,82 ± 0,09 | **−0,0353 ± 0,0053** |
| 0,06 | 3 052 | 0,58 | 40,10 ± 0,05 | 43,95 ± 0,15 | **+0,1605 ± 0,0067** |
| 0,20 | 10 172 | 1,93 | 42,13 ± 0,06 | 52,65 ± 0,12 | **+0,4383 ± 0,0055** |

Stessa classe, stessi volumi, stessa cache, stesso generatore: cambia solo l'ampiezza
dell'insieme di lavoro e il marginale passa **da risparmio netto a piu' della meta' del
costo di un crawler esaustivo (0,82)**. 5 ripetizioni per punto.

### 4.2 Elasticita' per classe alla composizione

A cache fissa e insiemi separati, quota agentica 13% → 30%:
miss **umano 0,227 → 0,232 (1,02×)** · **esaustivo 0,821 → 0,800 (1,03×)** ·
**agentico 0,180 → 0,044 (4,05×)**.

Precisazione obbligatoria: nell'esperimento varia il volume della sola classe agentica.
Misura quindi l'elasticita' **al proprio volume**, e mostra che quella al volume altrui
e' trascurabile. Non e' «tre classi sotto lo stesso stimolo».

### 4.3 Esternalita' sulla classe umana

Quota agentica 30%, al variare dello scope: p99 umano **76,1 → 88,0 → 113,0 ms**
(Δ = +37,0 ± 1,0, **t = 37,3**), mentre il miss umano si muove di 1,06× e il lavoro
all'origine va da 36,8 a 52,6 req/s. **E' carico, non spostamento di cache.**

### 4.4 Il confonditore da sovrapposizione

Decorrelando l'insieme agentico dalla testa popolare umana (la sovrapposizione passa dal
100% per costruzione al 2,1%; la massa di traffico umano sulle basi agentiche dal 62,1%
al 10,6%): origine **+0,714 (t = 5,74)** e **+1,012 (t = 7,74)** req/s; hit agentico
0,881 → 0,820 e 0,973 → 0,956.

### 4.5 Frontiera lavoro/latenza, λ = 185, α = 0,35, β = 0,10, 3 ripetizioni

| politica | servite | p99 umano | ms/1000 servite in piu' |
|---|---|---|---|
| C blocco esaustiva + agentica | 84 298 ± 116 | 57,83 ± 0,44 | — |
| B blocco esaustiva | 87 105 ± 144 | 57,87 ± 0,59 | 0,01 |
| rinvio budget 1 | 94 022 ± 46 | 73,2 ± 0,3 | 2,22 |
| rinvio budget 2 | 101 008 ± 94 | 96,7 ± 0,2 | 3,36 |
| rinvio budget 3 | 105 596 ± 25 | 115,2 ± 1,0 | 4,02 |
| rinvio budget 4 | 107 717 ± 97 | 136,4 ± 0,9 | 10,00 |
| rinvio budget 6 | 111 338 ± 47 | 212,3 ± 4,0 | 20,98 |
| A nessuna politica | 114 693 ± 1 | 555,4 ± 48,6 | 102,25 |

**B contro C:** +2 807 ± 185 servite (t = 15,19); Δ p99 **+0,03 ± 0,73 ms**, IC 95%
**[−1,99, +2,05] contiene lo zero**. Formulazione ammessa: *il blocco aggiuntivo della
classe agentica costa richieste servite e non produce un beneficio di latenza
misurabile*. **Mai la parola «domina».**

Nota per Results: il punto A ha SE sul p99 di ±48,6 ms contro ±0,2÷4,0 degli altri.
Il regime non governato non e' solo lento, e' **instabile**.

Costi marginali al punto della frontiera: esaustiva ~**0,82**, agentica ~**0,10** —
rapporto 8×, ed e' la spiegazione del confronto B/C.

### 4.6 Honeypot — taratura, `theslowshelf.org`

521 171 richieste, 12 agosto - 21 settembre 2026, 53 263 client, 314 520 connessioni,
18 720 pagine. Composizione: `other-bot` 43,5%, browser 22,9%, `training` 13,5%,
`search` 12,3%, `unknown` 5,3%, **`agent` 2,5%**.

Insieme di lavoro in **finestra di 143 s** (= T_C del banco), classe `agent`, 31 client:
mediana **4** URL, media 240, **p90 670**, massimo 678.

**Confronto omogeneo:** il nostro punto a scope 0,02 con λ=12 tocca **~693 oggetti
distinti nella stessa finestra**. Il p90 osservato e' **670**. Il punto sperimentale piu'
basso e' appaiato, per ampiezza dell'insieme in finestra, al 90° percentile degli agenti
osservati **in questo honeypot**.

Divergenza da dichiarare: **contiguita' agentica osservata 4,3%**, contro il 100%
assunto dal generatore. Va in Limitations, in prima pagina.

Web Bot Auth: **3,83%** delle richieste firmate (19 930 su 520 038), tutte da
`other-bot` (8,80% di quella classe), **zero** dagli agenti dichiarati.

---

## 5. LA SPINA, RIEMPITA

**PROBLEM.** Un'infrastruttura web condivisa assegna capacita' finita a richieste da
popolazioni con forme di accesso diverse, e per decidere associa un costo a una
**classe**. Il problema e' se quell'associazione regga quando le classi coesistono.

**HYPOTHESIS.** Ampia (cornice, non dimostrabile qui): l'infrastruttura attuale resta
adeguata mentre il traffico automatizzato diventa strutturale? Sperimentale
(falsificabile, e falsificata per una classe su tre): il costo per richiesta di una
classe e' invariante rispetto alla composizione?

**DISCOVERY.** Guidare con **4.1**, non con 4.2: il cambio di segno del costo marginale
e' inatteso e non anticipato da nessuno; l'elasticita' per classe e' in parte anticipata
da Zhang et al. (§7).

**MECHANISM.** Il comportamento dipende dall'interazione fra volume della classe,
ampiezza del suo insieme di lavoro e capienza della cache — non dall'etichetta.
Catena da usare: **pattern di accesso → geometria dell'insieme di lavoro → interazione
con lo stato condiviso → costo marginale.** Questa formulazione ci svincola
dall'etichetta «agentico».
L'approssimazione del tempo caratteristico (§7) **spiega la direzione ma non predice i
valori**: interpretativa, non validata.

**GENERAL PRINCIPLE.** Non una legge nuova — il modello e' da manuale. Il principio e'
**discriminante**: un costo fisso per classe e' adeguato per alcune classi e inadeguato
per altre, e quali siano le une e le altre e' determinabile per misura.

**CURRENT INFRASTRUCTURE LIMIT.** Non «la classificazione fallisce». La classificazione
resta utile: la politica B, che blocca per identita', **sta sulla frontiera**.
L'assunzione insicura e' piu' stretta: **che il costo per classe sia stabile abbastanza
da essere calibrato una volta.**

**TRANSITIONAL INTERNET.** La classificazione puo' essere necessaria ma **non
necessariamente sufficiente**. Il rinvio con budget da' controllo continuo dove il blocco
da' un interruttore. Isolare la classe agentica rimuoverebbe un beneficio misurato.

**TO-BE PROPERTIES.** L'infrastruttura dovrebbe poter osservare o derivare: **ampiezza
dell'insieme di lavoro** (sostenuta), **costo marginale nello stato corrente**
(sostenuta), **effetto sugli altri workload** (sostenuta). Stato condiviso e pressione
sulle risorse sono sostenute **debolmente** e vanno enunciate con meno enfasi.

**DECISION CRITERION.** Un **criterio, non un componente**. Non proponiamo un
controllore: la letteratura sa costruire anelli di retroazione, non ha una risposta a
dove valga la pena pagarli.

**NOVELTY.** §7.

**CONTRIBUTIONS.** §6.

---

## 6. I TRE CONTRIBUTI

1. **Caratterizzazione empirica.** Il costo marginale di una classe cambia segno al
   variare dell'ampiezza del suo insieme di lavoro, a parita' di classe, volumi e cache
   (−0,035 → +0,438). La conseguenza decisionale e' misurata al ginocchio: bloccare la
   classe agentica costa 2 807 richieste servite senza beneficio di latenza misurabile,
   perche' il suo costo marginale e' un ottavo di quello della classe esaustiva.
2. **Un confonditore di misura, quantificato.** La sovrapposizione fra insiemi di lavoro
   fa apparire una classe piu' economica: 0,061 di hit ratio e 0,71 req/s. Chiunque
   caratterizzi il costo di una classe su un corpus condiviso deve controllarlo o
   dichiararlo. **Formulazione stretta obbligatoria**: non «abbiamo scoperto il
   free-riding» (FairRide lo tratta gia', come equita'), ma «lo quantifichiamo come bias
   nella caratterizzazione sperimentale del costo».
3. **Un criterio di triage.** Il regime di una classe si stima da tre quantita' gia'
   disponibili in produzione. Il criterio dice **dove** spendere complessita' adattativa.
   Il modello non e' nostro; questo impiego non risulta in letteratura.

---

## 7. PRIOR ART — verificata su fonti primarie

**Il modello e' di altri, e la catena e' a tre.** Fagin 1977 (origine, JCSS 14(2):222-250)
→ Che, Tung, Wang 2002 (riscoperta e nome, IEEE JSAC 20(7):1305-1314) → Fricker, Robert,
Roberts 2012 (formalizzazione, ITC 24, arXiv:1202.3974). **Scrivere sempre tutti e tre.**

**UCP** (Qureshi & Patt, MICRO '06) e **Cliffhanger** (Cidon et al., NSDI '16): verificato
sui primari che misurano ∂(miss)/∂(**allocazione**), non ∂(costo)/∂(**composizione**).
La distinzione regge e puo' entrare nell'abstract.

**FairRide** (Pu et al., NSDI '16): tratta il free-riding come **equita' e incentivi**,
non come errore di misura. Ma lo quantifica in unita' di prestazione (2,9×), quindi la
nostra formulazione va tenuta stretta.

**Zhang et al., SoCC '25** (Zhang, Cai, Wildani, Klimovic, DOI 10.1145/3772052.3772255).
**Variano la composizione da 0% a 100% di traffico AI** misurando hit ratio complessivo
e umano. **Restringe A2.** Ma: misurano hit ratio, **non costo per richiesta**; e
**fissano l'overlap al 10-20% senza mai variarlo**. Quindi **4.1 resta intatta** e 4.4 si
rafforza — il parametro che loro fissano cambia il lavoro all'origine con t = 5,74.

**SemDN** (Hua & Xiao, HotNets 2026, arXiv:2609.22486). Propone un'architettura di
consegna a granularita' semantica: chunk retrieval, caching semantico, gerarchia edge.
Misurano il «page tax» (107× fino a 2 532× byte processati contro consumati), la
localita' agentica (30,5% di ripetizioni byte-identiche entro il task, 32-55% di chunk
gia' recuperati), e il risparmio di byte all'origine di una cache a chunk contro una a
URL (13-41× a parita' di capienza).

> **Posizionamento, da scrivere esplicitamente.** Loro chiedono *come dovrebbe essere
> l'architettura di consegna per gli agenti*; noi chiediamo *se, dentro
> un'infrastruttura condivisa, il costo di una classe possa essere trattato come una
> sua proprieta' stabile*. Non proponiamo un'architettura di consegna e **non
> affermiamo che il nostro criterio sia validato su SemDN**: non lo abbiamo testato.
> La domanda resta rilevante anche se l'architettura di consegna cambia — chi decide
> ammissione, collocazione e priorita', e con quale stima del costo?

Due punti di contatto utili, da citare senza polemica: SemDN documenta che gli agenti
spingono lavoro ridondante sulle origini, il che sostiene la nostra premessa; e la loro
O3 riprende da Zhang che «il traffico AI degrada le cache URL perche' riusa poco gli
URL» — affermazione **generale** che i nostri dati qualificano, perche' a scope 0,02 la
classe agentica ha l'82% di hit ratio. E' un raffinamento, non una contraddizione.

**Ricerca sistematica:** nessun lavoro 2025-2026 misura il costo infrastrutturale per
richiesta di una classe al variare della composizione o dell'ampiezza del suo insieme di
lavoro. Il termine «marginal cost of traffic class» nel nostro dominio non e' occupato.

**IETF:** `draft-ietf-aipref-attach-05` (18 ago 2026), `draft-ietf-aipref-vocab-08`
(13 set 2026); `draft-ietf-webbotauth-httpsig-protocol-00` (**1 set 2026**), su RFC 9421,
header `Signature-Agent` e `Signature-Input`. Corrispondono ai campi del nostro log.

**Cloudflare:** tassonomia Search/Agent/Training annunciata **1 luglio 2026**. Il
cambiamento del **15 settembre 2026 e' un annuncio**, vale per i **nuovi domini in
onboarding** e **solo sulle pagine con annunci**; nessuna conferma pubblicata di entrata
in vigore. Cloudflare pubblica volumi e crawl-to-refer ratio, **non costi per classe**.
Il Capitolo 5 gia' scritto va corretto ovunque lo descriva come generale o compiuto.

---

## 8. LE SEI RITRATTAZIONI

Non si nascondono. `docs/retractions.md` e' un documento di prima classe linkato dal
README; i dati che le sostenevano stanno in `archive/retired/`, **non** in
`data/evidence/`. In tesi diventano un'appendice metodologica.

1. «Il rinvio domina il blocco» — falsificata dalla frontiera: unica curva convessa.
2. «Il traffico agentico riduce il lavoro all'origine» — netto 0 → 36 positivo,
   +0,392 ± 0,158.
3. «La separazione ha falsificato la critica del workload cache-friendly» — confronto
   non appaiato; poi il run si e' rivelato un no-op (`AGENT_MUL` mai inoltrato a k6).
4. «Confine di residenza a 681 oggetti» — capienza sbagliata di circa 7,7×: sono 5 263 (C2).
5. «B domina C in senso di Pareto» — la differenza di p99 e' +0,03 ± 0,73 ms.
6. «Il tempo caratteristico predice quantitativamente l'elasticita'» — previsione precedente
   fallita: previsti 3,1 e 1,4, osservati 1,62 e 1,16.

**Tutte e sei erano interpretazioni, nessuna era una misura.** Le misure non sono mai
cambiate. Tutte e sei sono state trovate da noi, prima di pubblicare.

---

## 9. REGOLE DI LAVORO — imparate a caro prezzo

- **Nessun ragionamento sull'esito di un controllo prima di averlo eseguito.** Origine di
  tre ritrattazioni su sei.
- **Nessun numero derivato per divisione senza verificare cosa misura il divisore.**
  Origine della ritrattazione 4, che costo' un meccanismo intero.
- **Nessun lancio di campagna senza verificare `env.txt` trenta secondi dopo.** Origine
  della ritrattazione 3, che costo' quattro ore di macchina.
- **Si committa da una sola copia** (WSL `~/undertow`); lab e honeypot sono sola lettura,
  `git pull` soltanto. I patch applicati sul lab tornano indietro via `scp`.
- **Mai le righe `Co-Authored-By` o `Claude-Session` nei messaggi di commit.**
- Nessuna figura da Grafana nel paper: resta osservabilita' operativa.
- Nessun controllore inventato per rafforzare la novita'.
- Nessuna rivendicazione teorica sul modello del tempo caratteristico.
- Gli esperimenti sono **chiusi**. Da qui non generano la storia: verificano che quella
  congelata regga.

---

## 10. PROSSIMO PASSO

**Fase 1 — evidence freeze.** Due file:

- **`docs/registry.csv`** — un record per run: directory, data, configurazione
  (λ, α, β, scope, mul, cache), ripetizioni, ruolo (PRIMARIA / secondaria / validazione
  infrastrutturale / robustezza / **ritirata** / **invalida**), e in quale claim o figura
  entra. Criterio di uscita: **zero run «da decidere»**.
- **`docs/retractions.md`** — le sei voci del §8, ciascuna con: cosa affermavamo, su
  quale evidenza, cosa l'ha falsificata, cosa la sostituisce.

Il comando per l'inventario dei run:

```
ssh lab 'cd ~/undertow/harness/results && for d in tre-*/; do [ -f "$d/points.csv" ] || continue; printf "%-26s %3d punti  %s\n" "$d" "$(( $(wc -l < $d/points.csv) - 1 ))" "$(head -2 $d/points.csv | tail -1 | cut -d, -f1,2,4)"; done'
```

Poi: **fase 3, figure.** Sei principali piu' tre d'appendice, tutte da Python, con
`make figures` che le rigenera identiche. La figura centrale non e' piu' l'elasticita' ma
**il costo marginale contro l'ampiezza dell'insieme di lavoro**, con il cambio di segno e
la banda del p90 honeypot sovrapposta.
