# Esito dello sweep di AGENT_SCOPE
**22 settembre 2026.** Confronto contro `PREREGISTRAZIONE-scopesweep.md`, scritta prima
del lancio e non modificata.

> **Correzione del 23 settembre 2026.** Le righe a scope 0,02 di questo documento (origine 36,95 → 35,81, marginale −0,0477; p99 umano 75,9 ms; origine 35,8 req/s) venivano dai run a mappatura **condivisa** del 20 settembre. I valori corretti, dai run separati `tre-20260921-150237`/`-162248`, sono: origine 37,66 → 36,82, marginale **−0,0353 ± 0,0053**; p99 umano **76,1 ms**; origine **36,8 req/s**; rapporto dei miss **4,05** (4,09 era il rapporto di valori arrotondati). Il documento resta com'era per traccia storica; i numeri validi sono in `claims.md` v3. Nessuna conclusione cambia: il segno a scope 0,02 resta negativo (t = −6,7).

---

## 1. Verdetto sui criteri pre-registrati: 2 su 3

| scope | W | W/capienza | miss @13% | miss @30% | **rapporto** | previsto | scarto |
|---|---|---|---|---|---|---|---|
| 0,02 | 1 017 | 0,19 | 0,180 | 0,044 | **4,09** | 4,09 | — |
| 0,06 | 3 052 | 0,58 | 0,376 | 0,231 | **1,63** | 3,10 | **−47%** |
| 0,20 | 10 172 | 1,93 | 0,546 | 0,470 | **1,16** | 1,40 | −17% |

- **Criterio 1, monotonia decrescente: SODDISFATTO.** 4,09 > 1,63 > 1,16.
- **Criterio 2, r(0,20) < 2,0: SODDISFATTO.** 1,16.
- **Criterio 3, entro ±30%: NON SODDISFATTO.** Lo scope 0,06 sbaglia del 47%.

Avevo scritto «confermato se **congiuntamente**». Quindi, alla lettera: **la previsione
quantitativa e' fallita.** La direzione e l'ordinamento reggono; i numeri no.

### Dove ha sbagliato, e perche'

L'errore e' nell'approssimazione **uniforme**, che avevo dichiarato come semplificazione
ma poi usato per generare i numeri. Rifacendo lo stesso calcolo di Che con la
distribuzione **vera** — basi Zipf(0,6) e 3 oggetti contigui per sessione, quindi
tasso p_r·λ/3 per oggetto — e con T_C misurato punto per punto:

| scope | uniforme (pre-registrato) | Che con distribuzione reale | **osservato** |
|---|---|---|---|
| 0,02 | 29,19 | 7,75 | **4,09** |
| 0,06 | 3,08 | 2,06 | **1,63** |
| 0,20 | 1,40 | 1,29 | **1,16** |

Molto piu' vicino, e la forma e' giusta, ma **il modello sovrastima sistematicamente
l'elasticita' in tutti e tre i punti**. La cache reale e' meno sensibile di quanto la
teoria preveda.

**Questo calcolo e' post-hoc e va etichettato cosi' nel paper.** Non sostituisce la
previsione fallita: la spiega. Il modello di Che resta uno strumento di
*interpretazione*, non una previsione validata.

---

## 2. Il risultato che conta, e che non avevo previsto

Il rapporto fra miss ratio era la metrica sbagliata su cui concentrarsi. Quella giusta
e' il **costo marginale**, che e' anche la quantita' che serve davvero a una politica
di ammissione:

| scope | W/capienza | origine @13% | origine @30% | **costo marginale per richiesta agentica** |
|---|---|---|---|---|
| 0,02 | 0,19 | 36,95 ± 0,09 | 35,81 ± 0,09 | **−0,0477 ± 0,0054** |
| 0,06 | 0,58 | 40,10 ± 0,05 | 43,95 ± 0,15 | **+0,1605 ± 0,0067** |
| 0,20 | 1,93 | 42,13 ± 0,06 | 52,65 ± 0,12 | **+0,4383 ± 0,0055** |

> **Stessa classe, stessi volumi, stessa cache, stesso corpus, stesso generatore.
> Cambia soltanto l'ampiezza dell'insieme di lavoro, e il costo marginale passa da
> −0,048 a +0,438 richieste all'origine — cioe' da risparmio netto a piu' della meta'
> di quanto costa un crawler esaustivo (0,82).**

Gli errori standard sono dell'ordine di 0,005: le tre differenze sono separate da
decine di sigma. E' il risultato piu' solido dell'intero progetto.

**Perche' e' migliore del rapporto di miss ratio:** e' un cambio di **segno**, non di
magnitudine; e' la grandezza che una politica di ammissione usa davvero; ed e'
dimostrato **per costruzione** invece che inferito. L'etichetta "agentico" non dice
nulla sul costo; l'ampiezza dell'insieme di lavoro lo dice tutto.

---

## 3. L'esternalita' sulla classe umana compare, e dipende dallo scope

| scope | hit umano @30% | **p99 umano @30%** |
|---|---|---|
| 0,02 | 0,768 | 75,9 ± 1,3 ms |
| 0,06 | 0,759 | 88,0 ± 0,7 ms |
| 0,20 | 0,753 | **113,0 ± 0,7 ms** |

Da scope 0,02 a 0,20: **+37,1 ± 1,4 ms, t = 26,1**. Ma l'hit umano si muove solo di
1,06× (miss 0,232 → 0,247). **La degradazione umana non e' spostamento di cache: e'
carico all'origine**, salito da 35,8 a 52,7 req/s a parita' di volume totale.

Conseguenza: **lo stesso traffico agentico e' benigno o dannoso per gli utenti umani a
seconda dell'ampiezza del suo insieme di lavoro.** A scope 0,02 costa 4,5 ms di p99
umano; a scope 0,20 ne costa 37.

---

## 4. Cosa cambia nel claim

**Sopravvive e si rafforza:** che il costo decisionale non sia una proprieta' della
classe. Ora e' dimostrato con un cambio di segno del costo marginale, a parita' di
tutto tranne un parametro strutturale del workload.

**Si indebolisce:** il modello del tempo caratteristico come *previsione*. Rimane come
interpretazione che spiega la direzione, sovrastimando l'ampiezza. Va presentato cosi'
in §4 del master: strumento interpretativo, non modello validato. La pre-registrazione
fallita **va pubblicata insieme al risultato**, non nascosta: e' cio' che rende
credibile il resto.

**Nuovo:** l'ampiezza dell'insieme di lavoro, non la classe, e' la variabile che
governa sia il costo marginale sia l'esternalita' sugli altri. Questo rende il criterio
operativo del §13.3 piu' concreto: non serve calcolare x = λT_C/W con precisione, basta
sapere **dove cade W rispetto alla capienza**.

**Da ritirare in piu':** la previsione numerica 3,1 / 1,4, e con essa l'idea che il
modello uniforme fosse utilizzabile.

---

## 5. Implicazione per l'honeypot, e una lacuna da chiudere

Se lo scope e' la variabile che governa tutto, la sua misura sul traffico reale diventa
il numero piu' importante del lavoro. E la mia misura e' **metodologicamente sbagliata
per questo scopo**: `honeypot_scope.py` conta gli URL distinti per client **sull'intero
periodo di 40 giorni**, mentre cio' che conta per la cache e' quanti oggetti distinti un
client tocca **entro una finestra dell'ordine di T_C**, cioe' ~143 secondi.

La misura su 40 giorni **sovrastima** l'insieme di lavoro istantaneo, e non di poco.

Va rifatta con finestre scorrevoli. E' offline, costa secondi, e chiude l'ultima lacuna
che conosco.
