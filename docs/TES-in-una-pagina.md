# Undertow — la tesi in una pagina

Bussola per ogni sessione di scrittura. **Non aggiunge claim**: ogni frase del paper resta
vincolata a `docs/claims.md` (v3.6). Questo file dice *cosa* raccontiamo e *in che ordine*.
28 settembre 2026.

## La frase

**L'identità dice chi è il traffico, non quanto costa.**
*(EN: "Identity tells you who the traffic is, not what it costs.")*

Oggi l'infrastruttura decide in base all'identità (classe dichiarata o stimata) e al carico.
Il costo della prossima richiesta di una classe dipende invece da come il suo insieme di
lavoro interagisce con lo stato condiviso della cache. È **D1** (SFIDATO), il claim centrale.

## Cosa abbiamo misurato — Results (solo MISURATO)

1. **A1.** Il marginale agentico cambia segno col working set: −0,035 / +0,160 / +0,438
   richieste all'origine per richiesta, a 0,19× / 0,58× / 1,93× la cache. Il punto a
   0,02 è replicato con pre-registrazione nello stesso giorno: −0,0405 ± 0,0061.
2. **A9.** Marginale negativo non vuol dire risparmio: il netto 0 → 36 req/s **non è
   negativo** (+0,392 ± 0,158; replica +0,238 ± 0,110, IC che contiene lo zero). Mai
   scrivere «positivo».
3. **A2 + A7.** Le classi reagiscono in modo opposto al proprio volume: l'agentica è
   sensibile 4,05×, l'esaustiva è piatta a ~0,98.
4. **A8.** Per richiesta, l'esaustiva degrada il miss umano più dell'agentica. È
   misurata la direzione; il fattore ~7× non è appaiato.
5. **A3 + C4.** Il costo misurato di una classe dipende dalle altre. La sovrapposizione
   con la testa umana vale ~0,9 req/s (replicato). In isolamento il miss è 0,002, in
   mistura 0,180.
6. **A6 + A4.** Blocco e rinvio stanno sulla stessa frontiera. Bloccare anche gli agenti
   costa 2 807 richieste servite, con una Δ p99 non misurabile.
7. **C3 + C5 + C6 (honeypot).**
   - L'ampiezza degli agenti reali è ≈ scope 0,02 (p90 670 contro 693).
   - La contiguità invece no: 4,3% contro 66,9%.
   - Firme Web Bot Auth sul 3,83% delle richieste, zero dagli agenti dichiarati.

## Il meccanismo — Mechanism (SOSTENUTO e INTERPRETATIVO, etichettati)

- **B1.** Pattern di accesso → geometria dell'insieme → interazione con lo stato
  condiviso → costo marginale.
- **B2.** Fra 12 e 36 req/s a scope 0,02 domina l'auto-località delle agentiche già
  presenti.
- **B4** (interpretativo). Il tempo caratteristico spiega l'ordinamento.
- **B3** è respinto come previsione quantitativa: dirlo se si citano Fagin e Che.
- **B5.** Il p99 umano sale per carico all'origine, non per spostamento di cache.

## Transitorio — Implications (solo sezione D, dichiarate come implicazioni)

- La classificazione resta **necessaria** (D2) ma **non sufficiente** (D3).
- All'etichetta vanno affiancate tre grandezze osservabili dall'edge:
  - l'ampiezza dell'insieme in una finestra ≈ tempo caratteristico (D4);
  - il costo marginale nello stato corrente (D5);
  - l'effetto sugli altri workload (D6).
- Blocco e rinvio vanno trattati come punti di una curva, scelti con queste grandezze (A6).
- Chi misura il costo di una classe lo misuri in mistura e dichiari la sovrapposizione
  (A3, C4).
- *Candidato, NON in claims.md:* un prezzo fisso per richiesta (pay-per-crawl) contro un
  costo che cambia segno. Entra solo con una riga D e una fonte primaria.

## To-be — proprietà, non architettura

**P1 = D4, P2 = D5, P3 = D6, P4 = D7 (debole).**

Tabella ponte: evidenza → cosa l'infrastruttura deve sapere → meccanismo attuale → dove non
basta.

**Non si afferma** (sezione E):
- che l'architettura attuale sia inadeguata;
- che serva un nuovo protocollo;
- che proponiamo una nuova cache o una nuova architettura.

«Dall'identità a stato e costo» è la **domanda che il paper apre** («to our knowledge»),
non la conclusione.

## Posizionamento — Related Work (fonti da verificare)

**Zhang et al., SoCC '25**, e il blog Cloudflare del 2 aprile 2026 (Wildani, Ahmad).
- **Cosa dicono:** il traffico AI, con molti URL unici, abbassa l'hit ratio umano in LRU.
- **Cosa propongono:** SIEVE e S3-FIFO, caching basato su ML, cache separate per tipo di
  traffico, admission control.
- **Dove concordiamo:** sulla classe esaustiva (A7, A8).
- **Cosa aggiungiamo:**
  - misuriamo il costo marginale all'origine, non l'hit ratio;
  - per gli agenti il segno dipende dall'insieme di lavoro **della classe**, non
    dall'unicità **per client** (A1, C3);
  - la sovrapposizione che loro fissano al 10–20% sposta il costo misurato (A3);
  - separare la cache per tipo di traffico può togliere un beneficio misurato (D8).
- **Conseguenza per il simulatore:** in fase 2 le prime politiche da provare sono SIEVE e
  S3-FIFO.

**Altri riferimenti:**
- **SemDN** (Hua e Xiao, HotNets '26) propone un'architettura alternativa; noi no.
- **Breakwater, DAGOR, Protego, TopFull:** il controllo in retroazione non è una novità.
- **Denning 1968** (working set); **Fagin 1977, Che 2002, Fricker 2012** (tempo
  caratteristico); **Mattson 1970, SHARDS, Counter Stacks** (curve di miss).

## Pubblicazione

- **Venue:** PAM 2027, short paper.
- **Formato:** ≤ 11 pagine LNCS di contenuto, più ≤ 5 per appendici e bibliografia.
- **Revisione:** doppio cieco.
- **Obbligatori:**
  - appendice «Ethics»;
  - dichiarazione dell'uso di GenAI nei ringraziamenti;
  - file `.bbl`.
- **Scadenze:** abstract 30 ottobre 2026, paper 6 novembre 2026.
- **arXiv:** dopo l'endorsement, e compatibilmente con le regole di anonimato di PAM.

## Ordine di scrittura

1. Passaggio a LNCS; Methodology; Results aggiornato con la replica.
2. Mechanism; Limitations.
3. Tabella ponte e Implications.
4. Related Work.
5. Introduction, Abstract, titolo.
6. Appendice Ethics, anonimizzazione, revisione ostile indipendente.