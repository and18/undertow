# Verifica finale del PDF arXiv — 2 ottobre 2026

Verifica di sola lettura del paper contro `docs/claims.md` v3.10. Nessun file del paper, dei dati o
di `claims.md` e' stato modificato.

**Cosa e' stato verificato.** Il PDF compilato da `paper/main.tex` al commit `3cc10aa` (versione
arXiv con nome, gia' con `\showclaimsfalse`; 31 pagine), in una copia temporanea fuori dal
repository. Tutte le pagine citate sotto si riferiscono a quel PDF. `paper/main-clean.tex` (non
tracciato, 29 settembre) e' una copia obsoleta: vedi il punto 3.

**Fonti dei ricalcoli.**
- Numeri del paper: `docs/claims.md` v3.10 e i CSV di `data/derived/` e `data/posthoc/che_posthoc.csv`.
- IC di A9: `points.csv` di `tre-20260928-174217` e `tre-20260928-162206`
  (`~/undertow-backup/lab-20260928-own/results/`), quantile t di `tools/net_agentic.py`.
- T alla frontiera: `points.csv` degli otto run della frontiera (`tre-20260919-072040` A,
  `-080920` B, `-085754` C, `tre-20260920-075220` D1, `-070346` D2, `-061512` D3,
  `tre-20260919-094627` D4, `-103501` D6) dalle copie locali `~/undertow-backup/lab-20260928-own/`
  e `lab-20260929-own/`; capienza C2 = 5 263 oggetti; definizione di `origin_rps` in
  `harness/load/treclassi.sh` e `harness/load/workload.js`; risposte 403/503 in
  `harness/app/app.py` e `harness/varnish/default.vcl`.
- Netto simulato con SIEVE: `data/sim/fase2-scen/criteri.csv`.
- Dimensioni dei reachable set (8%): `data/derived/chapter_sizes.csv` con `reachable()` di
  `tools/scope_ttest.py`.

## Esito dei cinque controlli

| Controllo | Esito |
|---|---|
| (1) Numeri uguali a `claims.md` v3.10, Results tutti MISURATO | **Quasi tutto regge.** Ogni numero del testo, delle tabelle e delle didascalie coincide con `claims.md` o con il CSV da cui viene. Ho ricalcolato l'IC di A9 dalle ripetizioni: [0,9087; 1,2953], quindi «+0.91 to +1.30» e' giusto. Restano i punti 1, 2 e 4–12 dell'elenco. |
| (2) ID interni, TODO, «working set», PAM | **Nel PDF e' tutto a posto.** Nessun ID, solo il TODO del repository, «working set» sempre usato bene, nessun PAM. Nei sorgenti invece PAM c'e' (punto 18). |
| (3) «??» e bibliografia | **Nessun «??»** in `main.pdf`, nessun avviso di BibTeX. In `main-clean.pdf` ce ne sono 7 (punto 3). |
| (4) Abstract sotto 1 920 caratteri | **Si': 1 172 caratteri** (1 179 con il markup TeX), 200 parole. |
| (5) Ripetizioni fra testo e appendice | **Ce ne sono**, elencate al punto 17. |

## Il punto su T alla frontiera

- **Cosa conta `origin_rps`.** Conta solo i miss serviti con 200 (`workload.js`). I 403 del blocco
  hanno `no-store` e i 503 del rinvio non sono cacheabili per Varnish. Quindi `origin_rps` e'
  proprio il tasso con cui entrano oggetti in cache.
- **Il ritorno esaustivo.** Con il contatore condiviso, un capitolo ripassa nella traversata ogni
  16 954 / 185 = **91,6 s**. A ogni passaggio pero' e' una richiesta esaustiva solo con
  probabilita' α = 0,35. Il 35% dei ritorni avviene dopo 91,6 s; la media e' 261,8 s.

| Politica | Origine (req/s) | T ≈ 5 263 / origine | T confrontato con 91,6 s |
|---|---|---|---|
| A, nessuna politica | 81,45 | 64,6 s | piu' corto |
| B, blocca esaustiva | 18,80 | 279,9 s | piu' lungo, ma i miss esaustivi (403) non entrano in cache |
| C, blocca esaustiva + agentica | 17,96 | 293,0 s | come B |
| D1, rinvio budget 1 | 40,30 | 130,6 s | **piu' lungo** |
| D2, rinvio budget 2 | 55,01 | 95,7 s | **piu' lungo, al limite (+4%)** |
| D3, rinvio budget 3 | 64,10 | 82,1 s | piu' corto |
| D4, rinvio budget 4 | 68,32 | 77,0 s | piu' corto |
| D6, rinvio budget 6 | 74,96 | 70,2 s | piu' corto |

Il «T ≈ 143 s» della v3.10 e' il T del design primario (5 274 / 37 req/s, vedi B.1), non quello
della frontiera. Secondo l'approssimazione, gli hit esaustivi possono essere gonfiati solo con i
budget 1 e 2, non «in tutte le politiche». Con B e C l'esaustiva non puo' mai riusare le proprie
richieste.

## Elenco: errore, pagina, correzione proposta

**1. La riserva sulla frontiera usa il T sbagliato e generalizza troppo.**
- **Pagine:** 15 (§4.5), 23 (§7); `claims.md` A4, A5, A6, D2, D5.
- **Correzione per Results (§4.5).** Sostituire da «These runs use…» fino a «…by how much.» con:
  > These runs use the default agentic scope, 0.02, and the shared mapping, and they predate the correction of the exhaustive traversal (Section 3.2); Section 7 states for which policies this can matter.

  Il ragionamento su T e' un'approssimazione, non una misura, quindi in Results non ci sta.
- **Correzione per Limitations (§7).** Sostituire la frase «For the frontier, … we did not measure it.» con:
  > For the frontier, a chapter came up in the shared traversal every 91.6 s (16,954 chapters at 185 req/s), and the exhaustive class requested it at each pass with probability α = 0.35. Taking the characteristic time of each policy as the cache capacity over its origin rate, T ≈ 5,263 objects / origin rate, gives 65 s with no policy; 131, 96, 82, 77 and 70 s for deferral budgets 1, 2, 3, 4 and 6; and 280 and 293 s for the two blocking policies. A return after 91.6 s therefore falls within T only under budgets 1 and 2, where exhaustive hits may be inflated; with no policy and budgets 3 to 6, T is shorter than the return. Under the blocking policies an exhaustive miss receives an uncacheable error, so the exhaustive class never hits its own earlier requests. We did not measure how much budgets 1 and 2, and hence the shape of the frontier, are affected.
- **Correzione per `claims.md` (v3.11).**
  - **A4:** «Il meccanismo della v3.10 non si applica a B e C: i miss esaustivi ricevono 403 `no-store` e non entrano in cache, quindi l'esaustiva non riusa le proprie richieste. Resta solo il limite: run non rilanciati con la traversata corretta.»
  - **A6:** «Un capitolo passava nella traversata ogni 91,6 s ed era richiesto dall'esaustiva con probabilita' 0,35. T ≈ 5 263 / tasso d'origine per politica: A 64,6; D1 130,6; D2 95,7; D3 82,1; D4 77,0; D6 70,2; B 279,9; C 293,0 s (`points.csv` degli otto run). Il ritorno cade entro T solo con budget 1 e 2: li' gli hit esaustivi possono essere gonfiati. Ampiezza non misurata.»
  - **D2:** «B non e' toccata dal riuso esaustivo. Solo i punti con budget 1 e 2 possono avere hit gonfiati (T ≈ 131 e 96 s contro 91,6 s). Ampiezza non misurata.»
  - **A5 e D5:** vedi il punto 2.
  - **Changelog:** il 143 s veniva da 5 274 / 37 req/s. Suggerisco uno script (per esempio `tools/frontier_tc.py` → `data/derived/frontier_tc.csv`), cosi' i valori di T sono tracciabili come gli altri CSV.

**2. Lo 0,82 / 0,10 di A5 non si ricostruisce dalla frontiera.**
- **Pagine:** 19 (§5.4), 20 (§6), 21 (tabella 3, P2).
- **Errore.** Alla politica A il miss esaustivo misurato e' 0,855 (agentico 0,154). Lo 0,82 coincide invece con il miss esaustivo del design primario (0,821, run del 21 settembre, `UNDERTOW-CONTESTO.md` §4.1–4.2).
- **Correzione.** Prima scrivere in A5 da quale politica e da quali miss vengono 0,82 e 0,10, poi il limite. Se il punto e' A, la via del riuso non si applica (T ≈ 65 s). D5 eredita lo stesso limite.

**3. `main-clean.tex` e' obsoleto.**
- **Pagine:** in `main-clean.pdf`: titolo a p. 1, «??» alle pp. 9, 13, 17, 18, 19 (due) e 23.
- **Errore.** Ha l'intestazione PAM, «[TODO: choose title]», autori anonimi, e non include `A-details`: da qui i 7 riferimenti indefiniti.
- **Correzione.** Cancellarlo (non e' tracciato) oppure rigenerarlo come copia di `main.tex`, che e' gia' pulito.

**4. L'abstract contiene una riga INTERPRETATIVO e una frase senza riga.**
- **Pagina:** 1.
- **Errore.** «A characteristic-time model reproduces these values post hoc, so the effect is structural rather than a testbed artefact» usa B7, che e' INTERPRETATIVO, mentre la regola d'uso 1 ammette solo MISURATO e SOSTENUTO. L'eccezione e' scritta solo in un commento di `00-abstract.tex`. «Structural rather than a testbed artefact» non sta in nessuna riga, e B7 usa la distribuzione del generatore, quindi non puo' escludere un artefatto del generatore.
- **Correzione.** Registrare l'eccezione in `claims.md` (regola 1 e changelog) e scrivere:
  > Computed post hoc, a characteristic-time model reproduces the change of sign and the measured values.

  Sono 16 parole contro 18, quindi si resta sotto le 200.

**5. Una frase di §5.2 non ha una riga in `claims.md`.**
- **Pagina:** 18.
- **Errore.** «The change of sign is therefore structural rather than an artefact of our testbed.»
- **Correzione.** Toglierla, oppure aggiungerla a B7 come INTERPRETATIVO con il limite: «it uses our generator's distribution, so it cannot exclude an artefact of the generator».

**6. La frase sul netto con SIEVE va oltre S5.**
- **Pagina:** 19 (§5.5).
- **Errore.** «negative with SIEVE and S3-FIFO, where it comes from fewer misses of the other classes»: S5 da' questa origine solo per S3-FIFO. Con SIEVE i miss umani salgono (0,1823 → 0,1878) e scendono solo gli esaustivi (0,8000 → 0,7728, `criteri.csv`).
- **Correzione.** «…negative with SIEVE and S3-FIFO; with S3-FIFO it comes from fewer exhaustive and human misses.»

**7. B.3 attribuisce ai miss un «5 su 5» che vale per il tasso d'origine.**
- **Pagina:** 27.
- **Errore.** «The simulated miss is slightly higher … at all five points»: in S1 il 5 su 5 e' per `origin_rps`, i miss sono piu' alti solo «quasi ovunque».
- **Correzione.** «The simulated origin rate is slightly higher than the measured one at all five points (+0.4% to +0.9%), and the simulated miss ratios almost everywhere, within the tolerance.»

**8. Alcuni numeri sono giusti ma mancano in `claims.md`.**
- **Pagine:** 6, 13, 14, 15, 16, 18, 30, 31.
- **Errore.** Li ho verificati tutti sui CSV, ma non stanno nelle righe:
  - «about 8%» a p. 6 (dalle medie viene 8,34%);
  - figura 2: termini 0 → 12 (+2.196, +0.363, −0.615) e SE 0.104;
  - figura 3a: esaustiva 0.8356, umana 0.2300 → 0.2306;
  - figura 4: hit agentico 0.882 → 0.817 e 0.973 → 0.955;
  - figura 5: «no policy 555 ± 49 ms», α = 0.35, β = 0.10;
  - tabella 2: λT a scope 0.06 e 0.20 (0.39 / 1.00 / 0.12 / 0.27), su cui poggia «stays well below 1»;
  - figura 6: valori intermedi 89.7, 0.761, 43.9;
  - figura 8: «mean 240».
- **Correzione.** Aggiungerli alle righe C8, B2, A2, A3, A6, B7, B5 e C3.

**9. «Real agents» e' piu' forte di quello che i dati dicono.**
- **Pagine:** 11 (etichetta della figura 1), 31 (figura 8).
- **Errore.** I client sono classificati in base allo user agent dichiarato, che non verifichiamo; la riga E dice «DA QUALIFICARE».
- **Correzione.** Negli script delle figure: «closest to honeypot agents» e «Honeypot agent-class clients».

**10. Una frase di Results non e' MISURATO.**
- **Pagina:** 13 (§4.3).
- **Errore.** La frase su Zhang et al. e' posizionamento, non misura, e ripete §2.2 (p. 4).
- **Correzione.** Toglierla e tenere solo la frase sul totale offerto.

**11. In §6.1 ci sono frasi che non vengono dalla sezione D.**
- **Pagine:** 21–22.
- **Errore.** «a classical model may be enough…» usa B7 dentro Implications. La frase sulla novita' («We did not find prior work…») non ha una riga in `claims.md`.
- **Correzione.** Etichettare la prima come «Interpretive, post hoc». Per la seconda, aggiungere una riga con le fonti in `VERIFICHE-chiuse.md` oppure toglierla.

**12. B.2 rimanda a una sezione che non ne parla.**
- **Pagina:** 27.
- **Errore.** «sizes and overhead … fixed in advance for the simulator (Appendix B.3)», ma B.3 non nomina ne' le dimensioni ne' i 512 byte.
- **Correzione.** Aggiungere a B.3: «Object sizes are the reconstructed chapter responses plus a fixed 512-byte overhead, fixed in the pre-registration of the first phase.»

**13. Bibliografia: algoritmi nominati senza citazione.**
- **Pagine:** 4, 19, 22, 28.
- **Errore.** ARC e' nominato senza citazione, anche se `megiddo2003arc` e' gia' nel `.bib`. SIEVE, S3-FIFO e W-TinyLFU non hanno nessuna voce. Le voci non citate non vengono stampate, ma `liu2025somesite` («Liu and others») e `tene-latency` («check: venue and year») sono segnaposto.
- **Correzione.** Citare ARC. Aggiungere SIEVE (NSDI '24), S3-FIFO (SOSP '23) e W-TinyLFU (ACM TOS 2017) dopo averli verificati sulle fonti primarie. Togliere i due segnaposto.

**14. Ordine e stile delle citazioni (cosmetico).**
- **Pagine:** 1, 4, 5, 22, 27, 30.
- **Errore.** Citazioni in ordine sparso, come «[2,21,3,14]», «[7,1,8]», «[13,10]». La didascalia della figura 7 cita in stile autore-anno.
- **Correzione.** `\usepackage{cite}` e `\cite` nello script della figura 7.

**15. Una pagina quasi vuota.**
- **Pagina:** 29.
- **Errore.** Contiene solo «C Supplementary figures»; le figure stanno alle pp. 30–31.
- **Correzione.** Dare a `\undertowfig` un argomento di posizione e usare `[!ht]` nell'appendice C.

**16. Una parola spezzata in tabella.**
- **Pagina:** 5 (tabella 1).
- **Errore.** «Top-/Full».
- **Correzione.** `\mbox{TopFull}`.

**17. Ripetizioni fra testo e appendice.**
- **Correzione generale:** tenere ogni cosa in un solo posto e dall'altro mettere un rimando.
  - p. 8 §3.3 e p. 28 B.4: i rate 0 / 13.9968 / 27.9965 / 41.9977.
  - p. 23 §7 e p. 28 B.4: «α is read from the result files and λ from the campaign script…», quasi identico.
  - pp. 8, 12, 14, 23 e 28: «shared mapping, 1,211 s, 3 repetitions» compare cinque volte.
  - p. 26: B.1 ripete l'hash degli indirizzi dell'appendice A.
  - p. 26 B.1 e p. 3 §2.1: «did not verify the signatures cryptographically».
  - p. 26 B.1 e p. 31 figura 8: i numeri dell'honeypot (31 client, 4 / 678, 1,929 coppie, 284, 37, 19.4%).
  - p. 17 §5.2 e p. 27 B.2: «3.1 / 1.4 / ±30%».
  - p. 18 §5.3 e p. 30 figura 6: tutti i numeri della didascalia.
  - p. 17 §5.2 e p. 30 figura 7: previsione senza marca temporale, −47%.
  - p. 14 figura 3 e p. 28 B.4: «1.09×».
- **Ripetizioni dentro il testo (fuori dalla lista richiesta):**
  - la riserva sulla frontiera alle pp. 15 e 23 (si risolve con il punto 1);
  - «7 of 8 … W-TinyLFU» alle pp. 19 e 22;
  - «identity alone can be insufficient» due volte nello stesso paragrafo a p. 20.

**18. I sorgenti per arXiv (non il PDF).**
- **Errore.** arXiv pubblica anche il `.tex`. Contiene commenti con «PAM» (`references.bib` riga 2, `02-background.tex` riga 3), i marcatori `\claim{…}` con gli ID interni e commenti in italiano con percorsi `docs/`.
- **Correzione.** Ripulire i sorgenti prima del caricamento, per esempio con `arxiv_latex_cleaner`.
