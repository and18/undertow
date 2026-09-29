# Ritrattazioni

Sette correzioni fatte durante il progetto: sei affermazioni smentite (R1-R6) e un artefatto
del generatore di carico che spostava alcune misure (R7). Sono elencate qui, per intero,
perche' nascondere una correzione e' peggio che averla dovuta fare — e perche' il criterio
con cui sono cadute e' parte del metodo.

**Due fatti valgono per le prime sei.** Primo: erano **interpretazioni**, non misure.
Nessun dato misurato e' stato smentito da R1-R6; sono cadute le spiegazioni che vi erano
state appoggiate sopra. Secondo: sono state trovate **prima della pubblicazione**, da
controlli che abbiamo deciso noi di eseguire.

**R7 e' diversa:** e' un difetto di disegno nel generatore, e ha spostato valori misurati
(A9, D8, B2). Vale anche per R7 il secondo fatto: trovata prima della pubblicazione, dal
simulatore, e verificata sul lab con una pre-registrazione.

I dati che le sostenevano stanno in `archive/retired/`, **non** in `data/evidence/`.

---

## R1 — «Il rinvio domina il blocco»

**Affermata:** 19 settembre 2026, dopo la prima campagna di politiche.
**Sosteneva:** che rinviare le richieste invece di rifiutarle spostasse la frontiera
lavoro/latenza verso l'alto, essendo uno spostamento temporale invece di una perdita.
**Falsificata da:** i tre punti mancanti della frontiera, budget 1, 2 e 3
(`tre-20260920-0*`). Le pendenze fra segmenti consecutivi risultano monotone crescenti
**attraverso il cambio di meccanismo**: 0,01 → 2,22 → 3,36 → 4,02 → 10,00 → 20,98 →
102,25 ms per mille richieste servite in piu'.
**Sostituita da:** blocco e rinvio giacciono su **un'unica curva convessa**: sono due
parametrizzazioni dello stesso scambio, non politiche alternative. Il rinvio offre un
controllo continuo dove il blocco offre un interruttore, e questo resta un vantaggio
pratico — ma non di frontiera.

---

## R2 — «Aggiungere traffico agentico riduce il lavoro all'origine»

**Affermata:** 18 settembre, ritirata il 19 per insufficienza statistica, **riabilitata
per errore il 21** sulla base dei dati del 14 settembre, ritirata definitivamente il 21.
**Sosteneva:** che l'auto-localita' della classe agentica rendesse il suo effetto netto
sul backend negativo.
**Falsificata da:** la serie marginale con mappatura separata
(`tre-20260921-150237`, `tre-20260921-162248`). Il netto da 0 a 36 req/s agentici e'
**+0,392 ± 0,158 req/s, t = +2,48**: positivo.
**Perche' era sopravvissuta cosi' a lungo:** i dati del 14 settembre su cui era stata
riabilitata erano confusi dalla sovrapposizione degli insiemi di lavoro (vedi R3).
**Sostituita da:** il costo marginale **cambia segno** lungo la serie — +0,1032 ± 0,0127
al 13% di quota, −0,0352 ± 0,0053 al 30% — ma il netto resta positivo. Il massimo
interno e' reale; il risparmio netto no.

> **Nota del 26 settembre 2026.** Superato da claims.md v3.6: A9 afferma solo che il netto
> non è negativo; la replica pre-registrata ha IC 95% [−0,0601, +0,5361], che contiene lo
> zero.

> **Nota del 29 settembre 2026.** Superato da claims.md v3.7: con la traversata esaustiva
> corretta (R7) l'aggiunta della classe agentica **costa**, +1,102 ± 0,080 req/s, IC 95%
> [+0,909, +1,295]. La ritrattazione di R2 esce rafforzata: il netto piccolo delle misure
> precedenti era in parte prodotto dall'artefatto.

---

## R3 — «La separazione working-set ha falsificato la critica del workload cache-friendly»

**Affermata:** la mattina del 21 settembre.
**Sosteneva:** che decorrelare l'insieme di lavoro agentico dalla testa popolare umana
non cambiasse nulla, e che quindi la critica «avete costruito un workload cache-friendly
e avete scoperto che e' cache-friendly» fosse smentita dai dati.
**Falsificata due volte.** Primo: il confronto era **non appaiato** — il comparatore
corretto era la serie del 14 settembre agli stessi α e β, non un valore del 19 settembre
proveniente da un'altra configurazione. Secondo, e piu' grave: il run del 20 settembre
era un **no-op**. `AGENT_MUL` non era inoltrato a k6 da `treclassi.sh`, quindi la
campagna aveva rieseguito per quattro ore la configurazione del 14 settembre
(`tre-20260920-102015`, `114026`, `130038`, tutte INVALIDE).
**Sostituita da:** la critica era **corretta**. Con la mappatura effettivamente separata,
il lavoro all'origine sale di +0,714 (t = 5,74) e +1,012 (t = 7,74) req/s, e l'hit
agentico scende di 0,061 e 0,017. La sovrapposizione stava regalando hit alla classe
agentica.
**Correttivo introdotto:** `treclassi.sh` inoltra ora tutti i parametri agentici, e ogni
directory di run scrive `env.txt` con l'ambiente completo e il commit del codice. Il
no-op era rimasto invisibile ventiquattro ore perche' i run non registravano la propria
configurazione.

---

## R4 — «Confine di residenza a 681 oggetti»

**Affermata:** 21 settembre, come meccanismo esplicativo dell'intero risultato.
**Sosteneva:** che la capienza della cache fosse di 681 oggetti (128 MB divisi per
192,4 KB) e che l'insieme di lavoro agentico, a 1 017 oggetti, stesse «a cavallo» di
quel confine — da cui la sua sensibilita'.
**Falsificata da:** la misura diretta. `varnish_main_n_object` a cache piena da'
**5 274 oggetti** e 134,2 MB occupati, cioe' un oggetto medio di **24,8 KB**. La stima
era sbagliata di **7,75 volte**, e l'insieme agentico sta a **0,19×** la capienza, non
a 1,49×: comodamente dentro. *(Nota del 24 settembre, claims v3.2: la capienza oggi in C2
e' **5 263 ± 8 oggetti**, oggetto medio 24,9 KB, dalle finestre sature dei run a scope
0,20; l'errore della stima resta di circa 7,7 volte e l'insieme agentico resta a 0,19×.)*
**L'errore:** i 192,4 KB erano i byte di lavoro a PostgreSQL per richiesta misurati da
`classcost.py` — corpo del capitolo, righe di indice, byte dei capitoli correlati — non
la dimensione dell'oggetto HTTP memorizzato da Varnish. Due grandezze diverse, confuse
da una divisione.
**Sostituita da:** il **tempo caratteristico della cache**, T_C = capienza / tasso di
miss = 143 s, con miss = exp(−λ·T_C/W). Vedi R6 per i suoi limiti.
**Regola introdotta:** nessun numero derivato per divisione senza aver verificato cosa
misura il divisore.

---

## R5 — «B domina C in senso di Pareto»

**Affermata:** 20-21 settembre.
**Sosteneva:** che la politica che blocca solo la classe esaustiva dominasse
strettamente quella che blocca anche l'agentica, servendo piu' richieste a latenza
uguale o migliore.
**Falsificata da:** l'aritmetica. Sulla singola ripetizione C aveva p99 57,8 contro 57,9
di B, quindi era **nominalmente piu' veloce** e la dominanza stretta non si applicava.
**Aggiornata, non solo ritirata:** con tre ripetizioni per punto la differenza di p99 e'
**+0,03 ± 0,73 ms**, con IC 95% **[−1,99, +2,05] che contiene lo zero**; le richieste
servite in piu' sono **2 807 ± 185, t = 15,19**.
**Formulazione ammessa, unica:** *a questo punto operativo B serve 2 807 ± 185 richieste
in piu' di C con una differenza di p99 umano indistinguibile da zero; il blocco
aggiuntivo della classe agentica non produce un beneficio di latenza misurabile.*
La parola «domina» resta vietata.

---

## R6 — «Il tempo caratteristico predice quantitativamente l'elasticita'»

**Affermata:** 21 settembre, in `PREREGISTRAZIONE-scopesweep.md`, **prima** che fossero
disponibili i primi risultati a scope 0,06 e 0,20, senza marca temporale indipendente
(«previsione precedente», claims v3.2).
**Sosteneva:** che il rapporto fra il miss ratio al 13% e al 30% di quota agentica
valesse circa **3,1** a scope 0,06 e **1,4** a scope 0,20, entro il ±30%.
**Falsificata da:** lo sweep stesso. Osservati **1,62** e **1,16**. Il primo sbaglia del
**48%**, fuori tolleranza. Dei tre criteri scritti con la previsione due sono soddisfatti —
la monotonia decrescente (4,05 > 1,62 > 1,16) e r(0,20) < 2,0 — ma erano richiesti
congiuntamente.
**Causa:** l'approssimazione **uniforme**, che avevo dichiarato come semplificazione e
poi usato per generare i numeri. Rifacendo lo stesso calcolo con la distribuzione reale
— basi Zipf(0,6) e tre capitoli contigui — si ottengono 7,75 / 2,06 / 1,29: forma
giusta, ampiezza ancora sovrastimata. **Quel ricalcolo e' post-hoc e va etichettato
come tale.**
**Sostituita da:** il modello resta come **strumento interpretativo** che spiega
direzione e ordinamento, non come previsione validata. La previsione fallita si
pubblica insieme al risultato.

---

## R7 — Artefatto della traversata esaustiva (indice di iterazione globale)

**Trovato:** 28 settembre 2026, dal simulatore; **verificato sul lab:** 28 settembre;
**recepito:** claims.md v3.7, 29 settembre.
**Che cos'era.** In `harness/load/workload.js` la classe esaustiva sceglieva il capitolo con
`permuteTrav(offset + TRAV_SKIP + exec.scenario.iterationInTest)`, e `iterationInTest` conta
le iterazioni **di tutte le classi**. Lo stesso capitolo tornava quindi disponibile
all'esaustiva ogni N/λ secondi (204 s a λ = 83, 142 s a λ = 119), cioe' il percorso della
classe esaustiva dipendeva dal rate totale λ, che nel disegno cambia fra P0 (0 req/s
agentiche), S12 e S36 anche a parita' di α·λ = 28 req/s. Non era una misura sbagliata: era
una seconda variabile che cambiava insieme a quella manipolata.
**Cosa spostava.**
- **A9, sgonfiato.** Con la traversata globale il miss esaustivo scendeva da P0 a S36 di
  −0,0566 (0,8580 → 0,8014, replica 25-26 set); con la traversata corretta di −0,0324
  (0,8576 → 0,8252). Il calo in piu' faceva sembrare meno costosa l'aggiunta agentica: il
  netto 0 → 36 era +0,392 ± 0,158 e +0,238 ± 0,110 (IC con lo zero), e' **+1,102 ± 0,080**.
- **D8, gonfiato in ampiezza.** La direzione resta (il miss esaustivo scende quando cresce
  l'agentica, sotto separazione), ma circa il 57% del calo misurato prima e' effetto della
  cache; il resto era artefatto.
- **B2, gonfiato in modulo.** Il termine esaustivo della scomposizione fra S12 e S36 passa
  da −0,551 ± 0,025 a **−0,288 ± 0,047**.
- **S5 (simulatore), gonfiato.** Il netto negativo con S3-FIFO passa da −2,17 a −1,05; con
  W-TinyLFU da circa zero a +0,56; con LRU da +0,33 a +1,20. Cambiano anche S3 (SIEVE: il segno
  a scope 0,02 ora regge) e S4 (S3-FIFO: A3 a 36 req/s ora indeterminato).
- **Non spostati oltre l'errore:** il segno di A1 a scope 0,02 (−0,0405 ± 0,0061 prima,
  **−0,0348 ± 0,0043** dopo) e l'effetto della sovrapposizione A3 (+0,926 e +0,800 dopo,
  contro +0,882 e +0,872). A1 agli scope 0,06 e 0,20 si rimisura il 29 settembre
  (`docs/PREREG-lab-trav-own-scope-20260929.md`).
**Come e' stato trovato.** Nella fase 2 del simulatore (`docs/RISULTATO-simulatore-fase2.md`)
il netto negativo con S3-FIFO veniva quasi tutto dalla classe esaustiva; l'ipotesi annotata
allora era che la traversata dipendesse da λ. Due controlli:
- **fase 2b, pre-registrata** (`docs/PREREG-simulatore-fase2b.md`, `52d294c`; uscite in
  `data/sim/fase2b/`): con un contatore proprio della classe il calo del miss esaustivo da P0
  a S36 **resta** (LRU −0,0315 ± 0,0007, |Δ|/SE circa 46), quindi e' in parte un effetto
  della cache, ma e' circa **meta'** (53%) di quello con il contatore globale (−0,0600, che
  coincide con il lab);
- **esplorativo, non pre-registrato** (`tools/sim/esplora_artefatto.py`, `f684b05`,
  committato prima dell'esecuzione; `data/sim/esplorativo-artefatto/`): i marginali di A1 si
  spostano di circa 0,015 ai tre scope (cambio di segno e ordinamento reggono), A3 e A7 non
  cambiano, il netto di A9 passa da circa +0,33 a circa +1,1. Da qui le previsioni per il lab.
**Verifica sul lab.** Pre-registrazione `docs/PREREG-lab-trav-own-20260928.md` (`204459c`,
pushata prima del lancio): opzione `TRAV_MODE=scen` in `workload.js`, che mette l'esaustiva in
uno scenario k6 proprio con un contatore solo suo (sequenza verificata capitolo per capitolo
contro il simulatore); stessi cinque punti della replica del 25-26 settembre, stesso ordine,
unica differenza `TRAV_MODE`. Campagna del 28 settembre, 13:41-20:22 UTC, cinque run con gate
`ok`, nessuno rifatto; analisi con `tools/trav_own_analysis.py` (`188b8cb`, collaudato prima
sulla replica). Esito (`docs/RISULTATO-lab-trav-own-20260928.md`): **V1-V4 passano** e i
cinque livelli stanno tutti negli IC previsti (V5). Dichiarato: con `TRAV_MODE=scen` gli arrivi
esaustivi diventano regolari invece che casuali, e il confronto con la replica e' fra giorni
diversi.
**Cosa resta.** A scope 0,02 i run `scen` sono primari; quelli a traversata globale restano
nel registry come misura precedente. Il default di `workload.js` resta quello vecchio, per
riprodurre i run passati; ogni run nuovo dichiara `TRAV_MODE` in `env.txt`.

---

## Cosa hanno in comune

Tre delle prime sei (R3, R4, R6) hanno la stessa origine: **ragionare sull'esito di un
controllo prima di eseguirlo**. R7 ha un'origine diversa: una variabile di disegno che
cambiava insieme a quella manipolata, nascosta in un contatore condiviso; l'ha trovata un
modello indipendente del generatore (il simulatore), non un controllo sui dati. R4 in particolare nasce da una divisione fatta senza
verificare cosa misurasse il divisore.

Le regole che ne sono derivate, ora nella stop-list del progetto:

- nessun ragionamento sull'esito di un controllo prima di averlo eseguito;
- nessun numero derivato per divisione senza verificare cosa misura il divisore;
- nessun lancio di campagna senza verificare `env.txt` trenta secondi dopo;
- ogni previsione si registra prima, con il criterio di falsificazione, e si pubblica
  anche quando fallisce.
