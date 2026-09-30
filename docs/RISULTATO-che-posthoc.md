# Marginale agentico previsto dall'approssimazione del tempo caratteristico — calcolo post hoc
**30 settembre 2026. POST HOC, INTERPRETATIVO, NON PRE-REGISTRATO.** Scritto per rispondere a un
revisore secondo cui il cambio di segno di A1 e' previsto dall'approssimazione del tempo
caratteristico (Fagin 1977; Che et al. 2002). Nessun numero di questo documento e' una misura
nuova ne' una previsione scritta prima dei dati: le misure del lab con cui si confronta erano
gia' note. Script `tools/che_posthoc.py`, uscite `data/posthoc/che_posthoc.csv`. **B3 resta
RESPINTO** (vedi sotto).

## Cosa si calcola

Per ciascuno dei sei punti di A1 (S12 e S36 a scope 0,02, 0,06, 0,20; mappatura separata) si
costruisce il tasso di richieste di ogni capitolo dalla distribuzione vera del generatore
(`harness/load/workload.js`), con le tre classi del disegno:

- **umana**, (1 − α − β)·λ ≈ 55 req/s: rango r = min(floor(N^u), N − 1), quindi
  P(r = k) = log((k+1)/k) / log N (il rango 0 non esce mai), capitolo = permute(r);
- **agentica**, β·λ = 12 o 36 req/s: base di rango k con P(k) = ((k+1)/S)^0,4 − (k/S)^0,4 (skew
  0,6, S = floor(N·scope)), capitolo base = (k·3266489917 + 42) mod N; ogni sessione chiede base,
  base + 1, base + 2, quindi ogni capitolo riceve β·λ/3 per la somma delle P(k) dei blocchi che
  lo contengono (capitoli distinti: 1 017 / 3 051 / 10 020 raggiungibili);
- **esaustiva**, α·λ ≈ 28 req/s.

Cache LRU a capienza in byte: footprint = byte di `data/derived/chapter_sizes.csv` + 512,
capienza 134 217 728 byte (il modello di dimensioni del simulatore validato nella fase 1). Per ogni
configurazione T si risolve dall'equazione di capienza Σ_j footprint_j · occupazione_j(T) = C;
`origin_rps` e' la somma dei tassi di miss; m = (O(S36) − O(S12)) / 23,9990.

**Due versioni della classe esaustiva, dichiarate e scritte nello script prima di eseguirlo e
riportate entrambe:**
- **(A) Che stretto (IRM).** Anche l'esaustiva e' un processo di Poisson, di tasso α·λ/N per
  capitolo; hit = 1 − exp(−μT) con μ = somma dei tassi delle tre classi.
- **(B) Esaustiva periodica.** E' il processo misurato con `TRAV_MODE=scen`: ogni capitolo torna
  ogni P = N/(α·λ) ≈ 605 s. Estensione del tempo caratteristico a traffico di rinnovo: con μ =
  umana + agentica, occupazione e hit delle richieste di Poisson = 1 − exp(−μT)·max(0, 1 − T/P);
  hit delle richieste esaustive = 1 − exp(−μT) (T < P in tutti i punti).

Nessun parametro e' stimato da questi marginali. Le dimensioni degli oggetti e H vengono dalla
fase 1, dove sono state controllate solo contro la capienza (C2) e i byte per richiesta del lab.

## Esito: segno e valore del marginale

| scope | lab, `scen` (MISURATO) | (A) Che stretto | (B) esaustiva periodica | simulatore, SCEN (SIMULATO) |
|---|---|---|---|---|
| 0,02 | **−0,0348** | −0,0218 (modulo −37%) | **−0,0311** (modulo −11%) | −0,0308 |
| 0,06 | **+0,1430** | +0,1722 (+20%) | **+0,1488** (+4%) | +0,1500 |
| 0,20 | **+0,4209** | +0,4669 (+11%) | **+0,4282** (+2%) | +0,4308 |

- **Segno:** entrambe le versioni danno il **cambio di segno** (negativo a 0,02, positivo a 0,06 e
  0,20) e l'ordinamento m₀,₀₂ < m₀,₀₆ < m₀,₂₀.
- **Valore:** (B) sta entro l'11% dal lab a 0,02 e entro il 4% a 0,06 e 0,20, ed e' quasi
  identica al simulatore. (A) sbaglia di piu', perche' tratta la traversata esaustiva come
  Poisson: prevede un miss esaustivo di 0,69 contro 0,83 misurato, quindi livelli di circa 4 req/s
  troppo bassi (per esempio S12 a 0,02: 34,1 contro 38,2).

Livelli e miss per classe della versione (B) contro il lab (umana / agentica / esaustiva):

| punto | T (s) | O (B) | O lab | miss (B) | miss lab |
|---|---|---|---|---|---|
| 0,02 S12 | 104,4 | 38,39 | 38,23 | 0,231 / 0,186 / 0,838 | 0,230 / 0,183 / 0,836 |
| 0,02 S36 | 98,7 | 37,64 | 37,39 | 0,234 / 0,045 / 0,827 | 0,231 / 0,045 / 0,825 |
| 0,06 S12 | 99,7 | 40,70 | 40,47 | 0,233 / 0,385 / 0,830 | 0,230 / 0,383 / 0,828 |
| 0,06 S36 | 84,9 | 44,28 | 43,90 | 0,242 / 0,235 / 0,805 | 0,239 / 0,231 / 0,802 |
| 0,20 S12 | 96,3 | 42,65 | 42,35 | 0,236 / 0,548 / 0,826 | 0,234 / 0,538 / 0,823 |
| 0,20 S36 | 74,9 | 52,93 | 52,45 | 0,249 / 0,474 / 0,791 | 0,247 / 0,467 / 0,788 |

**Fattore del miss agentico 12 → 36 req/s** (la grandezza di B3): (B) 4,10 / 1,64 / 1,16; (A)
4,33 / 1,65 / 1,16; lab `scen` 4,08 / 1,66 / 1,15.

## λT medio per oggetto agentico

λ = tasso agentico del capitolo, T = tempo caratteristico della configurazione. Versione (B);
la (A) da' valori simili (tabella completa nel CSV).

| scope | a 12 req/s: media / mediana / pesata per richiesta | a 36 req/s: media / mediana / pesata per richiesta |
|---|---|---|
| 0,02 | 1,23 / 0,75 / 6,12 | 3,49 / 2,12 / 17,35 |
| 0,06 | 0,39 / 0,24 / 2,50 | 1,00 / 0,61 / 6,39 |
| 0,20 | 0,115 / 0,070 / 0,96 | 0,269 / 0,162 / 2,24 |

Lettura, interpretativa: a scope 0,02 l'oggetto agentico tipico passa da λT ≈ 1 a λT ≈ 3,5, cioe'
dalla parte ripida di 1 − e^(−λT) alla saturazione. Il miss delle 12 req/s gia' presenti crolla,
e questo termine supera il costo delle richieste aggiunte (e' il meccanismo di B2). A scope 0,20
λT resta molto sotto 1 a entrambi i tassi, quindi il miss agentico resta alto e il marginale si
avvicina al costo pieno delle richieste aggiunte. Il tempo caratteristico scende con il tasso
agentico, di piu' a scope grande (da 104 a 99 s a 0,02; da 96 a 75 s a 0,20).

## B3 resta RESPINTO

B3 afferma che l'approssimazione **predice quantitativamente** l'elasticita'. La previsione scritta
il 21 settembre (`docs/PREREGISTRAZIONE-scopesweep.md`) dava 3,1 e 1,4 contro 1,66 e 1,15
osservati ed e' fallita: **resta RESPINTO**. Quella previsione usava un modello piu' semplice:
- tasso **uniforme** λ/W su tutto l'insieme di lavoro, senza skew Zipf(0,6) ne' sessioni;
- **un solo** T_C = 143 s (capienza in oggetti / tasso di miss), uguale a 12 e a 36 req/s;
- miss = exp(−x).

Il calcolo di questo documento, fatto **dopo** aver visto i dati, usa la distribuzione vera, T
risolto per ogni configurazione con la capienza in byte e le tre classi. Ricostruisce segno e
valori, ma e' un adattamento a posteriori, non una previsione. Non cambia lo stato di B3 e non
rende predittiva, in senso pre-registrato, l'approssimazione.

## Cautele

1. **Post hoc.** Le misure erano note; il modello e' stato costruito per spiegarle. Le due versioni
   sono dichiarate nello script prima dell'esecuzione (lo script e' stato scritto il 29 settembre
   ed eseguito il 30; e' committato insieme a questo documento, dopo l'esecuzione).
2. **Scelta fra (A) e (B).** (B) corrisponde al processo misurato (`TRAV_MODE=scen`), ed e' quella
   che torna meglio. Sono riportate entrambe.
3. **Stesso modello di dimensioni del simulatore.** L'accordo fra (B) e il simulatore (scarti su m
   fra 0,0003 e 0,0026) non e' una verifica indipendente: condividono dimensioni, H e capienza. Mostra
   che, per questo generatore, l'LRU simulato si comporta come l'approssimazione.
4. **Cosa risponde al revisore.** Si', con la distribuzione degli accessi del generatore
   l'approssimazione del tempo caratteristico riproduce il cambio di segno di A1, in entrambe le
   versioni, e nella versione periodica anche i valori. Non l'abbiamo previsto in anticipo in
   questa forma: la nostra previsione semplificata di B3 era sbagliata.

## Cosa implica (da decidere, non fatto qui)

Se e come citare questo calcolo in `claims.md` (per esempio a sostegno di B4, INTERPRETATIVO,
etichettato come post hoc) e nel paper (Mechanism). B3 non cambia.
