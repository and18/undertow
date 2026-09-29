# Undertow — la tesi in una pagina

Bussola per ogni sessione di scrittura. **Non aggiunge claim**: ogni frase del paper resta
vincolata a `docs/claims.md` (v3.8). Questo file dice *cosa* raccontiamo e *in che ordine*.
29 settembre 2026 (aggiornato con la traversata corretta, voce R7 di `docs/retractions.md`).

## La frase

**L'identità dice chi è il traffico, non quanto costa.**
*(EN: "Identity tells you who the traffic is, not what it costs.")*

Oggi l'infrastruttura decide in base all'identità (classe dichiarata o stimata) e al carico.
Il costo della prossima richiesta di una classe dipende invece da come il suo insieme di
lavoro interagisce con lo stato condiviso della cache. È **D1** (SFIDATO), il claim centrale.

## Cosa abbiamo misurato — Results (solo MISURATO)

1. **A1.** Il marginale agentico cambia segno col reachable set: −0,035 / +0,143 / +0,421
   richieste all'origine per richiesta, a 0,19× / 0,58× / 1,90× la cache, tutti con la
   traversata esaustiva in scenario proprio (`TRAV_MODE=scen`, 28-29 set). Lo sweep del
   21-22 set (−0,035 / +0,161 / +0,438) resta come misura precedente.
2. **A9.** Marginale negativo non vuol dire risparmio: **l'aggiunta della classe agentica
   costa**, +1,102 ± 0,080 req/s da 0 a 36 req/s, IC 95% [+0,909, +1,295]. Le misure
   precedenti (+0,392 e +0,238) erano abbassate dall'artefatto R7.
3. **A2 + A7.** Le classi reagiscono in modo opposto al proprio volume: l'agentica è
   sensibile 4,08×, l'esaustiva è piatta a ~0,98.
4. **A8.** Per richiesta, l'esaustiva degrada il miss umano più dell'agentica. È
   misurata la direzione; il fattore ~7× non è appaiato.
5. **A3 + C4.** Il costo misurato di una classe dipende dalle altre. La sovrapposizione
   con la testa umana vale +0,93 e +0,80 req/s. In isolamento il miss è 0,002, in
   mistura 0,183.
6. **A6 + A4.** Blocco e rinvio stanno sulla stessa frontiera. Bloccare anche gli agenti
   costa 2 807 richieste servite, con una Δ p99 non misurabile.
7. **C3 + C5 + C6 (honeypot).**
   - L'ampiezza degli agenti reali è ≈ scope 0,02 (p90 670 contro 693).
   - La contiguità invece no: 4,3% contro 66,9%.
   - Firme Web Bot Auth sul 3,83% delle richieste, zero dagli agenti dichiarati.

## Il meccanismo — Mechanism (SOSTENUTO e INTERPRETATIVO, etichettati)

- **B1.** Pattern di accesso → geometria dell'insieme → interazione con lo stato
  condiviso → costo marginale.
- **B2** (misurato, contabile). Fra 12 e 36 req/s a scope 0,02 il termine più grande è
  la variazione sulle 12 req/s agentiche già presenti (−1,622 su −0,889). Dice quale
  termine, non perché: niente «domina» né «auto-località» (tolti in claims v3.4).
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
- **SemDN** (Hua e Xiao, preprint arXiv:2609.22486) propone un'architettura alternativa; noi no.
- **Breakwater, DAGOR, Protego, TopFull:** il controllo in retroazione non è una novità.
- **Denning 1968** (working set); **Fagin 1977, Che 2002, Fricker 2012** (tempo
  caratteristico); **Mattson 1970, SHARDS, Counter Stacks** (curve di miss).

## Pubblicazione

- **Venue:** **arXiv** (deciso il 29 settembre; PAM non e' piu' la sede). Sede di conferenza
  da scegliere dopo, come previsto in `CLAUDE.md`.
- **Formato:** si tiene LNCS (`llncs` v2.26 in `~/texmf`, bibliografia `splncs04`),
  circa 16 pagine di contenuto piu' appendici.
- **Anonimato:** non piu' necessario per arXiv; il sorgente oggi e' ancora anonimo (autore,
  ringraziamenti, `\anonrepo`) e va reso nominativo prima dell'invio.
- **Da tenere:** appendice «Ethics», dichiarazione dell'uso di GenAI, riferimenti verificati.
- **arXiv:** dopo l'endorsement.

## Ordine di scrittura

1. Passaggio a LNCS; Methodology; Results aggiornato con la replica.
2. Mechanism; Limitations.
3. Tabella ponte e Implications.
4. Related Work.
5. Introduction, Abstract, titolo.
6. Appendice Ethics, anonimizzazione, revisione ostile indipendente.