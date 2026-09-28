# Esito della fase 2 del simulatore — politiche di sostituzione e sessioni realistiche
**28 settembre 2026.** Confronto contro `docs/PREREG-simulatore-fase2.md` (commit `cf214d2`) con
l'emendamento 1 (`a9c854d`), entrambi pushati prima di scrivere codice. Codice in `tools/sim/`
(`policies.py`, `test_policies.py`, `fase2.py`), committato prima di ogni esecuzione
(`5c64713`, correzione `79f5014`). Uscite in `data/sim/fase2/`. **Ogni numero di questo
documento e' SIMULATO**: nessuno e' una misura, nessuno entra in Results come evidenza di A1,
A3 o A9. Nessun dato del lab e' stato usato.

## Cancelli, nell'ordine pre-registrato

| cancello | esito | dettaglio | file |
|---|---|---|---|
| K collaudo delle politiche | **PASSA** | 14 tracce piccole con sequenza derivata a mano; invarianti su 10 000 richieste a 5 MB e 128 MiB (byte ≤ capienza, hit ⇔ presente, byte ricontati); con capienza = corpus solo i miss obbligatori (4 870 su 4 870) | `k.txt` |
| R0 regressione | **PASSA** | LRU × Q-GEN: 180 righe su 180 identiche a `data/sim/fase1/reps.csv`, cifra per cifra | `r0.csv` |
| calibrazione Q-REAL | **PASSA** | p_r = 0,190751953, p_c = 0,037933502 (semi 101-105): 4,238% contigue, 19,482% ripetute, al primo giro | `calibrazione.csv` |
| G0-R | **PASSA** | semi 1-5, S12: contigue **4,24%** (4,25 ± 0,5), ripetute **19,61%** (19,44 ± 1,0) | `g0r.csv` |

Senza soglia (G0-R): scostamenti k = 0/1/2 nelle richieste agentiche di Q-REAL 0,319 / 0,356
/ 0,325 (la catena sposta peso verso k = 1, come previsto); oggetti agentici distinti in 620 s
a S12, seme 1: 979 con Q-REAL, 1 004 con Q-GEN.

## Esito criterio per criterio

Criteri decisi nella pre-registrazione: segno di A1 a scope 0,02 «regge» se m < 0 e t ≤ −3;
dipendenza se m₀,₀₂ < m₀,₀₆ < m₀,₂₀ con differenze consecutive a t ≥ 3; cambio di segno se in
piu' m₀,₀₂ < 0 (t ≤ −3) e m₀,₂₀ > 0 (t ≥ 3); A3 se d₁₂ e d₃₆ > 0 con t ≥ 3; netto «non negativo»
se t > −2. 20 semi per punto.

| combinazione | m₀,₀₂ (t) | m₀,₀₆ | m₀,₂₀ | segno a 0,02 | dipendenza | cambio di segno | d₁₂ (t) | d₃₆ (t) | A3 | netto P0 → 36, IC 95% | netto |
|---|---|---|---|---|---|---|---|---|---|---|---|
| LRU × GEN (rif.) | −0,0451 (−13,5) | +0,1647 | +0,4461 | regge | regge | regge | +0,882 (12,3) | +0,839 (10,4) | regge | +0,331 [+0,170, +0,491] | non negativo |
| SIEVE × GEN | −0,0070 (−2,7) | +0,0149 | +0,3631 | **indeterminato** | regge | **non regge** | +0,334 (6,3) | +0,051 (0,8) | **indeterminato** | −0,374 [−0,498, −0,251] | **negativo** |
| S3-FIFO × GEN | −0,0720 (−19,4) | +0,0376 | +0,3685 | regge | regge | regge | +0,348 (4,5) | +0,420 (4,8) | regge | −2,170 [−2,339, −2,001] | **negativo** |
| W-TinyLFU × GEN | −0,0212 (−7,9) | +0,0136 | +0,3274 | regge | regge | regge | +0,459 (6,9) | +0,125 (2,0) | **indeterminato** | −0,040 [−0,173, +0,092] | non negativo |
| LRU × REAL | −0,0315 (−9,1) | +0,1425 | +0,3718 | regge | regge | regge | +0,806 (11,0) | +0,944 (10,4) | regge | +0,572 [+0,409, +0,735] | non negativo |
| SIEVE × REAL | −0,0051 (−1,6) | +0,0115 | +0,3323 | **indeterminato** | regge | **non regge** | +0,324 (4,4) | +0,124 (1,7) | **indeterminato** | −0,349 [−0,472, −0,225] | **negativo** |
| S3-FIFO × REAL | −0,0685 (−17,5) | +0,0410 | +0,3077 | regge | regge | regge | +0,298 (3,9) | +0,510 (5,0) | regge | −2,077 [−2,257, −1,896] | **negativo** |
| W-TinyLFU × REAL | −0,0216 (−6,7) | +0,0187 | +0,2943 | regge | regge | regge | +0,446 (4,9) | +0,105 (1,9) | **indeterminato** | −0,034 [−0,152, +0,085] | non negativo |

LRU × GEN riproduce la fase 1 (R0): e' il riferimento, non una risposta.

**Miss umano con e senza traffico agentico** (Δ_h = miss_h(S) − miss_h(P0), ± SE ≈ 0,0008;
metrica del blog Cloudflare del 2 aprile 2026, qui espressa come miss):

| combinazione | miss_h(P0) | 0,02 a 12 | 0,02 a 36 | 0,06 a 12 | 0,06 a 36 | 0,20 a 12 | 0,20 a 36 |
|---|---|---|---|---|---|---|---|
| LRU × GEN | 0,2273 | +0,0031 | +0,0071 | +0,0057 | +0,0149 | +0,0078 | +0,0216 |
| SIEVE × GEN | 0,1855 | +0,0036 | +0,0047 | +0,0065 | +0,0147 | +0,0078 | +0,0216 |
| S3-FIFO × GEN | 0,2002 | −0,0012 | +0,0004 | +0,0001 | +0,0096 | +0,0003 | +0,0108 |
| W-TinyLFU × GEN | 0,1752 | +0,0040 | +0,0085 | +0,0058 | +0,0164 | +0,0050 | +0,0171 |
| LRU × REAL | 0,2273 | +0,0037 | +0,0070 | +0,0057 | +0,0136 | +0,0075 | +0,0198 |
| SIEVE × REAL | 0,1855 | +0,0040 | +0,0050 | +0,0074 | +0,0151 | +0,0098 | +0,0261 |
| S3-FIFO × REAL | 0,2002 | −0,0007 | +0,0004 | +0,0006 | +0,0091 | +0,0015 | +0,0112 |
| W-TinyLFU × REAL | 0,1752 | +0,0040 | +0,0089 | +0,0060 | +0,0152 | +0,0064 | +0,0175 |

Miss per classe, `origin_rps` e oggetti in cache di ogni punto sono in `data/sim/fase2/criteri.csv`.

## Risposta alla domanda

Regola pre-registrata: una combinazione «regge» se reggono il segno di A1 a 0,02, la
dipendenza dall'insieme di lavoro e A3.

- **(a) altre politiche, sessioni del generatore — regge in parte.** Con **S3-FIFO** regge
  tutto (segno, dipendenza, cambio di segno, A3). Con **W-TinyLFU** reggono segno, dipendenza e
  cambio di segno; A3 e' indeterminato (d₃₆ +0,125, t = 1,96). Con **SIEVE** regge solo la
  dipendenza; il segno a 0,02 e' indeterminato (−0,0070, t = −2,66), il cambio di segno non
  regge, A3 e' indeterminato (d₃₆ +0,051, t = 0,76).
- **(b) LRU, sessioni realistiche — regge.** Segno a 0,02 (−0,0315, t = −9,1), dipendenza,
  cambio di segno e A3 (+0,81 e +0,94).
- **(c) entrambe — regge in parte, con lo stesso quadro di (a):** S3-FIFO regge tutto;
  W-TinyLFU tutto tranne A3 (d₃₆ t = 1,90); SIEVE solo la dipendenza.

In tutte le 8 combinazioni **la dipendenza dall'insieme di lavoro regge** (il marginale cresce
con lo scope, differenze consecutive con t ≥ 3,4) e d₁₂ e' positivo con t ≥ 3,9. Quello che
dipende dalla politica e' il segno a scope 0,02 e d₃₆.

## Previsioni contro esiti

Scritte prima di eseguire; si riportano tutte.

| combinazione | previsione | esito | |
|---|---|---|---|
| LRU × GEN | m₀,₀₂ ≈ −0,045; dipendenza e cambio di segno reggono; A3 ≈ +0,85; netto ≈ +0,33; Δ_h piccolo e positivo | −0,0451; reggono; +0,88 / +0,84; +0,33; +0,003…+0,022 | **giusta** |
| SIEVE × GEN | m₀,₀₂ positivo o indeterminato | indeterminato (−0,0070, t −2,66) | giusta |
| | dipendenza si', cambio di segno probabilmente no | dipendenza si', cambio di segno no | giusta |
| | A3 positivo, piu' piccolo | d₁₂ +0,33 si'; d₃₆ +0,05 non distinguibile da zero: indeterminato | **sbagliata in parte** |
| | netto positivo | **negativo**, −0,37 | **sbagliata** |
| | Δ_h piu' piccolo che in LRU | circa uguale (piu' piccolo solo a 0,02 con 36) | **sbagliata** |
| S3-FIFO × GEN | m₀,₀₂ positivo o indeterminato | **negativo**, −0,0720 (piu' negativo che in LRU) | **sbagliata** |
| | cambio di segno probabilmente no | **regge** | **sbagliata** |
| | A3 positivo, piu' piccolo | +0,35 / +0,42 | giusta |
| | netto positivo | **negativo**, −2,17 | **sbagliata** |
| | Δ_h piu' piccolo che in LRU | ~0 a scope 0,02; +0,011 a 0,20 con 36 (LRU +0,022) | giusta |
| W-TinyLFU × GEN | m₀,₀₂ positivo | **negativo**, −0,0212 | **sbagliata** |
| | cambio di segno no | **regge** | **sbagliata** |
| | m₀,₂₀ piu' alto che in LRU (rifiuto della coda agentica) | **piu' basso**, +0,327 contro +0,446 | **sbagliata** |
| | A3 positivo, piu' piccolo | d₁₂ +0,46 si'; d₃₆ +0,12, t 1,96: indeterminato | sbagliata in parte |
| | netto positivo | ~0 (−0,04, IC contiene lo zero) | **sbagliata** |
| | Δ_h il piu' piccolo | simile a LRU | **sbagliata** |
| LRU × REAL | m₀,₀₂ negativo, meno che in GEN | −0,0315 contro −0,0451 | giusta |
| | dipendenza, cambio di segno, A3 simili a GEN | reggono; +0,81 / +0,94 | giusta |
| | netto positivo, **piu' piccolo** che in GEN | positivo ma **piu' grande**, +0,57 contro +0,33 | **sbagliata in parte** |
| | Δ_h simile a GEN | simile | giusta |
| SIEVE × REAL | come SIEVE × GEN | stesso quadro: segno indeterminato, cambio di segno no, A3 indeterminato, netto negativo | come sopra |
| S3-FIFO × REAL | come S3-FIFO × GEN | stesso quadro: tutto regge, netto −2,08 | come sopra |
| W-TinyLFU × REAL | come W-TinyLFU × GEN | stesso quadro | come sopra |

**La previsione centrale e' smentita.** Avevamo previsto che il segno negativo a scope 0,02
fosse una proprieta' dell'LRU sotto scansione e che sparisse con le politiche resistenti alle
scansioni. Nel simulatore non sparisce con S3-FIFO (piu' negativo) ne' con W-TinyLFU; diventa
indeterminato solo con SIEVE. Anche il meccanismo proposto (a 12 req/s il miss agentico sarebbe
gia' basso e resterebbe poco da ridurre) e' vero a meta': il miss agentico a 12 req/s scende
molto (0,185 con LRU, 0,054 / 0,078 / 0,050 con SIEVE / S3-FIFO / W-TinyLFU), ma il segno non
segue quell'ordine.

## Osservazioni che la pre-registrazione non chiedeva di interpretare

Riportate come osservazioni SIMULATE, **senza meccanismo verificato**.

- **Netto negativo con SIEVE e S3-FIFO.** Con S3-FIFO il netto P0 → 36 e' −2,17 (GEN) e
  −2,08 (REAL). Dalla scomposizione per classe a scope 0,02 (`criteri.csv`): il miss esaustivo
  scende da 0,8231 (P0) a 0,7416 (S36), cioe' circa −2,28 req/s sulle 28 req/s esaustive; l'umano
  resta fermo (+0,0004); l'agentica aggiunge circa +0,10 req/s. Il netto negativo viene dalla
  classe esaustiva. Anche sotto LRU il miss esaustivo scende (0,859 → 0,799), nella direzione di
  D8 misurata sul lab, ma li' il netto resta positivo. Un'ipotesi **non verificata** e' la
  struttura del generatore: la traversata esaustiva usa l'indice globale di iterazione, quindi
  a λ = 83 (P0) e λ = 119 (S36) ripassa sul corpus con una spaziatura diversa, anche a parita' di
  28 req/s esaustive. **Non e' un risparmio dimostrato ne' un'affermazione sul Web**: la riga
  E «Il traffico agentico fa risparmiare lavoro all'origine» resta RITIRATA e A9 (lab, LRU)
  resta «non negativo».
- **Politiche diverse, livelli diversi.** A parita' di traffico, `origin_rps` a P0 e' 36,6
  (LRU), 31,9 (SIEVE), 34,1 (S3-FIFO), 29,6 (W-TinyLFU). W-TinyLFU tiene piu' oggetti in cache
  (~5 800 contro ~5 200), il che fa pensare che ammetta meno oggetti grandi (non verificato).
- **Sessioni realistiche.** Q-REAL cambia poco: stesso quadro di Q-GEN per ogni politica. Con
  LRU il marginale a 0,02 e' meno negativo (−0,032 contro −0,045) e il netto piu' alto.

## Dichiarazioni

1. **Correzione di codice durante K.** Il primo avvio di `test_policies.py` (a `5c64713`) si e'
   fermato con un `MemoryError` nello sketch di W-TinyLFU, perche' i test usano lettere come
   chiavi. Le verifiche di LRU, SIEVE e S3-FIFO erano gia' passate; nessuna di W-TinyLFU aveva un
   esito. Correzione in `79f5014`: le chiavi non intere si convertono in un intero deterministico;
   le chiavi intere delle tracce vere non cambiano. K rieseguito per intero: PASSA. Nessun
   parametro toccato.
2. **Scelte dichiarate nell'emendamento 1**, implementate cosi': vittime di W-TinyLFU dalla coda
   della prova e poi della protetta; chiave rimossa dal fantasma di S3-FIFO quando l'oggetto
   torna; il contatore dei campioni di TinyLFU dimezzato insieme agli altri (§3.3 del paper).
   S3-FIFO ha un ripiego (sfratto da S se M non puo' sfrattare) mai previsto dal paper: si conta
   in `guard`, non riportato perche' non richiesto.
3. **TTL** non modellato nelle politiche nuove: ogni ripetizione dura 920 s contro 86 400 s di TTL;
   il codice lo verifica con un'asserzione.
4. **Hash nei file.** Tutte le uscite (`k.txt`, `r0.csv`, `calibrazione.csv`, `g0r.csv`,
   `reps.csv`, `criteri.csv`) portano `79f5014`: nessun cambio di codice dopo K.

## Limiti

- Tutto e' SIMULATO su **un** generatore sintetico, **una** capienza (128 MiB), un corpus. Le
  politiche nuove non sono validate sul lab: la fase 1 valida solo LRU.
- Q-REAL riproduce due statistiche di coppia dell'honeypot (contiguita' e ripetizioni), non il
  comportamento degli agenti reali; la sessione e' un VU, sull'honeypot una connessione TCP (C5).
- Gli effetti che dipendono dalla politica (segno a 0,02 con SIEVE, d₃₆, netto) non hanno un
  meccanismo verificato.
- Il miss simulato leggermente piu' alto del lab (limite della fase 1) vale anche qui.
