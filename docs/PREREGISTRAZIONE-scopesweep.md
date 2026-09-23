# Pre-registrazione dello sweep di AGENT_SCOPE
**21 settembre 2026, 23:50 — scritta PRIMA del lancio.**
Questo file non va modificato dopo aver visto i risultati.

## Il meccanismo, corretto

Il "confine di residenza" del documento master e' **ritirato**: si basava su una
capienza di 681 oggetti, ricavata dividendo 128 MB per 192,4 KB, che sono i byte di
lavoro a PostgreSQL per richiesta e non la dimensione dell'oggetto memorizzato.

Misura diretta da `varnish_main_n_object` a cache piena:

- **capienza = 5 274 oggetti** (31,1% del corpus), 134,2 MB occupati su 134,2
- **oggetto medio = 24,8 KB**, non 192,4

L'insieme di lavoro agentico (339 basi × 3 capitoli = 1 017 oggetti) e' quindi
**0,19× la capienza**: sta comodamente dentro. Non e' a cavallo di nessun confine, e
la spiegazione che avevo costruito su quella geometria non regge.

Il meccanismo corretto e' il **tempo caratteristico della cache** (approssimazione di
Che, 2002). Con capienza C e tasso di miss M, un oggetto sopravvive se viene
rivisitato entro T_C = C/M. Per una classe con tasso λ e insieme di lavoro W, il
tasso per oggetto e' λ/W e il miss ratio vale exp(−λ·T_C/W).

Qui: T_C = 5 274 / 37 = **143 s**. Con quel solo numero, e nessun parametro libero:

| classe | λ | W | x = λT_C/W | miss previsto | miss osservato |
|---|---|---|---|---|---|
| esaustiva | 28 | 16 954 | 0,235 | **0,790** | 0,821 / 0,800 |
| umana Zipf(1) | 55 | 16 954 | distribuito | **0,249** | 0,227 / 0,232 |
| agentica | 12 | 1 017 | 1,682 | **0,186** | **0,180** |
| agentica | 36 | 1 017 | 5,046 | 0,006 | 0,044 |

Tre punti su quattro tornano. Il quarto no, e si sa perche': a x ≈ 5 il modello
uniforme sovrastima la residenza, perche' la concentrazione Zipf(0,6) *dentro* lo
scope lascia una coda fredda che continua a generare miss. **Il modello vale per
x ≲ 2 e va dichiarato cosi'.**

## Perche' la classe agentica e' l'unica sensibile

miss = exp(−x) con x = λT_C/W. L'elasticita' del miss al proprio volume e' **−x**.

- La classe **agentica** ha un insieme **limitato**: x ≈ 1,7, quindi elasticita'
  esponenziale. Triplicare il volume divide il miss per e².
- La classe **umana** ha un insieme **a coda pesante** (Zipf, senza scala): la
  sensibilita' e' logaritmica, non esponenziale.
- La classe **esaustiva** ha un insieme **molto piu' grande** di quanto il suo volume
  possa tenere: x = 0,235, regime lineare, miss ≈ 1 e quasi immobile.

La classe agentica non e' speciale perche' e' "IA": e' speciale perche' ha un insieme
di lavoro **limitato e piccolo rispetto alla capienza**, che e' cio' che rende
l'esponenziale ripido.

## Previsione registrata

Elasticita' = miss(λ=12) / miss(λ=36), a scope fisso.

| scope | W | W/capienza | x(12) | x(36) | **rapporto previsto** |
|---|---|---|---|---|---|
| 0,02 | 1 017 | 0,19 | 1,68 | 5,05 | gia' misurato: **4,09** |
| **0,06** | 3 052 | 0,58 | 0,56 | 1,68 | **≈ 3,1** |
| **0,20** | 10 172 | 1,93 | 0,17 | 0,50 | **≈ 1,4** |

Entrambi i punti nuovi hanno x ≤ 2, cioe' cadono nel regime in cui il modello ha
funzionato. Tolleranza dichiarata: ±30%.

**Ritiro la previsione precedente.** Avevo registrato una relazione *non monotona*,
derivata dal confine di residenza. Il modello corretto prevede una relazione
**monotona decrescente**: piu' grande l'insieme di lavoro, minore l'elasticita'.

## Criterio di falsificazione

Il meccanismo e' confermato se, congiuntamente:

1. **4,09 > r(0,06) > r(0,20)**, con ciascuno scarto di almeno 2 errori standard
   combinati;
2. **r(0,20) < 2,0** — soglia derivata dal modello (prevede 1,40), non scelta guardando
   i dati;
3. r(0,06) e r(0,20) cadono entro il ±30% dei valori previsti.

Cade se: i rapporti non decrescono in modo monotono; oppure r(0,20) ≥ 2,0; oppure i
valori sono fuori tolleranza in direzioni opposte, che indicherebbe un modello
sbagliato e non solo mal calibrato.

## Perche' non testiamo scope piu' piccoli

A scope 0,006 il modello prevede miss 0,004 a λ=12 e ~0 a λ=36: hit ratio 0,996 contro
1,000. Il rapporto sarebbe enorme ma **non misurabile**, perche' entrambi i valori
sono dentro il rumore. La saturazione e' essa stessa una previsione del modello, ma
non produce un dato utile e non vale 2h40.

Nota che deriva dall'honeypot: lo scope mediano osservato per la classe `agent` e'
**0,0008**, cioe' proprio nel regime saturo. Se il modello e' giusto, gli agenti reali
con insiemi di lavoro cosi' piccoli sono quasi gratuiti all'origine — e il problema
si presenta solo quando il loro scope cresce verso la capienza della cache. E' una
previsione che il paper puo' enunciare e che non abbiamo modo di verificare qui.

## Se la previsione fallisce

Il meccanismo del tempo caratteristico cade. Resta la caratterizzazione empirica
(4,09× contro 1,02× e 1,03×) senza spiegazione meccanicistica: livello 2,
pubblicabile, piu' debole. Non si riapre la fase sperimentale per cercarne un terzo.
