# Ritrattazioni

Sei affermazioni fatte durante il progetto e poi smentite. Sono elencate qui, per
intero, perche' nascondere una correzione e' peggio che averla dovuta fare — e perche'
il criterio con cui sono cadute e' parte del metodo.

**Due fatti valgono per tutte e sei.** Primo: erano **interpretazioni**, non misure.
Nessun dato misurato e' mai stato smentito; sono cadute le spiegazioni che vi erano
state appoggiate sopra. Secondo: sono state trovate **prima della pubblicazione**, da
controlli che abbiamo deciso noi di eseguire.

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

## Cosa hanno in comune

Tre delle sei (R3, R4, R6) hanno la stessa origine: **ragionare sull'esito di un
controllo prima di eseguirlo**. R4 in particolare nasce da una divisione fatta senza
verificare cosa misurasse il divisore.

Le regole che ne sono derivate, ora nella stop-list del progetto:

- nessun ragionamento sull'esito di un controllo prima di averlo eseguito;
- nessun numero derivato per divisione senza verificare cosa misura il divisore;
- nessun lancio di campagna senza verificare `env.txt` trenta secondi dopo;
- ogni previsione si registra prima, con il criterio di falsificazione, e si pubblica
  anche quando fallisce.
