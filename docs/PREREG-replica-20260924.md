# Pre-registrazione della replica nello stesso giorno
**24 settembre 2026 — scritta e committata PRIMA del lancio.**
Questo file non va modificato dopo il lancio. Il commit che lo contiene e' anche quello
che il lab esegue: il suo hash finisce nell'ultima riga di ogni `env.txt` della campagna.

## Scopo

Tre righe di `claims.md` poggiano su run di giorni diversi o su un solo run per punto:

- **A1**, punto a scope 0,02: marginale −0,03525 ± 0,00526 da `tre-20260921-150237` e
  `-162248` (stesso giorno, mai ripetuto);
- **A3**: condivisa (20 set) contro separata (21 set);
- **A9**: β = 0 (20 set) contro β·λ = 36 (21 set).

La campagna rimisura i cinque punti in una sola notte, cosi' ogni confronto e' fra run
dello stesso giorno, e misura quanto si spostano i run ripetuti rispetto al 20-21 set.
E' una verifica, non un esperimento nuovo: non produce claim nuovi. Gli esiti aggiornano
lo stato di A1, A3 e A9 secondo la colonna «cosa lo falsifica» di `claims.md`.

## Disegno

Solo configurazioni gia' usate. Umana 55 ed esaustiva 28 req/s fisse; cambia solo la
classe agentica (0 / 12 / 36 req/s) e la mappatura.

| punto | mappatura | AGENT_MUL | α | β | λ | agentica (β·λ) | run di riferimento |
|---|---|---|---|---|---|---|---|
| S12 | separata | 3266489917 | 0,2947 | 0,1263 | 95 | 11,9985 | `tre-20260921-150237` |
| S36 | separata | 3266489917 | 0,2353 | 0,3025 | 119 | 35,9975 | `tre-20260921-162248` |
| C12 | condivisa | 2654435761 | 0,2947 | 0,1263 | 95 | 11,9985 | `tre-20260920-114026` |
| C36 | condivisa | 2654435761 | 0,2353 | 0,3025 | 119 | 35,9975 | `tre-20260920-130038` |
| P0 | — | 2654435761 | 0,3373 | 0 | 83 | 0 | `tre-20260920-102015` |

Configurazione comune, identica allo sweep del 21 set:

- `WARMUP=300`, `MEASURE_FORCE=620`, `REPS=5`, `GATE=0` — letti in `env.txt` di
  `tre-20260921-150237` e `-162248` (unica differenza fra i due: `LAMBDA` e `POINTS`);
- `AGENT_SCOPE=0.02`: il 21 set era assente, cioe' il default 0,02. Ora e' esplicito,
  cosi' compare in `env.txt`; il valore che arriva a k6 e' lo stesso;
- `AGENT_SESSION` 3 e `AGENT_SKEW` 0,6 di default, `SEED` 42 di default, `TOTAL_MB`
  128 (`VARNISH_SIZE=128m`), `.env` del lab invariato (budget 0, nessun `BLOCK_CLASSES`).
  Nessuna variabile di `docker-compose.yml` era impostata nella shell il 21 set: lo
  script di lancio le toglie dall'ambiente, cosi' valgono `.env` e i default.

Harness: il lab e' a `7daa68b`; `git diff 7daa68b HEAD -- harness` e' vuoto. Rispetto a
`9d5d016` (il commit dei run del 21 set) l'unica differenza in `treclassi.sh` e'
`7e5aa0a`, che inoltra a k6 `AGENT_SCOPE`, `AGENT_SESSION` e `AGENT_SKEW` con default
uguali a quelli di `workload.js`. I run di riferimento C12, C36 e P0 sono anteriori a
`env.txt`: 5 ripetizioni e misura di 620 s risultano da `points.csv`, λ dai JSON di k6
(riga A9).

**P0.** Con β = 0 non parte nessuna richiesta agentica, quindi `AGENT_MUL` non ha
effetto; si usa il default, come nel run di riferimento.

### La mappatura condivisa e' davvero quella umana

Verificato nel codice il 24 set, prima di scrivere questo file.

- `workload.js`: la classe umana usa `permute(r) = (r·2654435761 + SEED) mod N`; la
  classe agentica usa `permuteAgent(r) = (r·AGENT_MUL + SEED) mod N`, con
  `AGENT_MUL = parseInt(__ENV.AGENT_MUL || '2654435761')`. Con `AGENT_MUL=2654435761`
  le due funzioni sono la stessa espressione.
- `treclassi.sh` passa `-e AGENT_MUL="${AGENT_MUL:-2654435761}"` a k6 (dal `9d5d016`).
- Esattezza numerica: il prodotto massimo, 16 953 × 3 266 489 917 ≈ 5,5·10¹³, e'
  sotto 2⁵³, quindi in double il calcolo e' esatto.
- Controllo eseguito (emulazione in double delle due funzioni, N = 16 954, SEED = 42):
  **0 ranghi su 16 954** mappati su capitoli diversi; entrambi i moltiplicatori danno
  una biiezione (MCD con N = 1); delle 339 basi agentiche a scope 0,02, **339 su 339**
  cadono fra i primi 339 ranghi umani con 2654435761, **7 su 339** con 3266489917.
- I run condivisi del 20 set non passavano `AGENT_MUL` a k6, quindi usavano il default
  di `workload.js`, 2654435761: stessa permutazione di C12 e C36.

### Ordine: C12, S12, S36, P0, C36

La proposta iniziale era S12, C12, P0, C36, S36. Se durante la notte c'e' una deriva
lineare di *d* req/s per posizione, un confronto fra due punti distanti *k* posizioni
riceve una distorsione *k·d*. Distanze nei due ordini:

| confronto | criterio | S12, C12, P0, C36, S36 | **C12, S12, S36, P0, C36** |
|---|---|---|---|
| S12 – S36 | R1 | 4 | **1** |
| S12 – C12 | R2 a 12 | 1 | **1** |
| S36 – C36 | R2 a 36 | 1 | **2** |
| S36 – P0 | R3 | 2 | **1** |
| somma / massimo | | 8 / 4 | **5 / 2** |

Tutti e quattro i confronti adiacenti non si possono avere: S36 compare in tre confronti
e in una sequenza ha al piu' due vicini. Si sceglie di lasciare a distanza 2 il confronto
con l'effetto di riferimento piu' grande (A3 a 36, t = 7,74) e di tenere adiacenti R1
(il claim centrale) e R3 (l'effetto piu' piccolo, t = 2,48). La mappatura resta alternata:
condivisa ai due estremi, separata al centro.

**Limite dichiarato.** Nessun punto e' ripetuto nella notte, quindi la deriva *dentro*
la notte non si misura. R4 misura la differenza fra giorni, non fra ore.

## Comandi esatti

Lo script `tools/replica-20260924.sh` (in questo stesso commit) chiama
`harness/load/treclassi.sh`, non modificato, una volta per punto:

```
AGENT_MUL=<mul> AGENT_SCOPE=0.02 LAMBDA=<λ> REPS=5 GATE=0 \
  WARMUP=300 MEASURE_FORCE=620 POINTS="<α>:<β>" bash treclassi.sh
```

Prima di partire lo script si ferma se: l'harness differisce da `HEAD`; ci sono
container attivi; questo file non e' nel commit. Per ogni punto: 30 s dopo l'avvio
legge `env.txt` del run appena creato e si ferma se una chiave del disegno non e' quella
attesa o se `BUDGET_LOW`, `BLOCK_CLASSES`, `VARNISH_SIZE`, `AGENT_SESSION` o
`AGENT_SKEW` risultano impostate nella shell; a fine punto applica il gate. L'elenco
punto → run → esito va in `harness/results/replica-20260924.tsv`.

Lancio, sul lab:

```
cd ~/undertow && git pull --ff-only && git log -1 --oneline
nohup setsid bash tools/replica-20260924.sh > harness/results/replica-20260924.log 2>&1 < /dev/null &
```

## Durata stimata

Un punto con 5 ripetizioni dura **80 minuti** (per ripetizione: riavvio di Varnish 8 s,
warm-up 300 s, misura 620 s, avvio di k6 e `gracefulStop`, pausa 15 s). Misurato sui
run di riferimento: `150237` → `162248` 80 min 11 s, `214946` → `230947` 80 min 01 s.

Cinque punti: **circa 6 h 41 min**. Ogni punto rifatto aggiunge 80 min (al massimo
cinque, uno per punto).

## Grandezza e calcoli

- Grandezza: `origin_rps` di `points.csv` (miss all'origine al secondo, 2 decimali,
  scritto da `treclassi.sh`: e' il dato grezzo disponibile, come nei run di riferimento).
- Per punto: media Ō delle 5 ripetizioni, SE = deviazione standard campionaria / √5.
  SE di una differenza: √(SE₁² + SE₂²). t di Welch, gradi di liberta' di
  Welch–Satterthwaite, quantile della t di Student (come `tools/net_agentic.py`).
- Rate agentici: quelli **configurati**, β·λ, come in `tools/scope_ttest.py`; divisore
  di R1 = 35,9975 − 11,9985 = **23,9990**.
- Nessun valore arrotondato entra nei calcoli. I riferimenti qui sotto sono ricalcolati
  dalle ripetizioni dei run di riferimento il 24 set.
- Mappatura: R1 usa solo punti separati; R2 confronta separata e condivisa, che e'
  l'oggetto del test; R3 usa S36 e P0, dove la mappatura non ha effetto. Nessun altro
  confronto mescola le due mappature.
- R1, R2 e R3 usano **solo** i run di questa notte. I run vecchi entrano solo come
  costanti di riferimento in R1(b) e R4.

## Previsioni e criteri

**R1 — A1, marginale a scope 0,02.**
m = (Ō(S36) − Ō(S12)) / 23,9990, SE_m = √(SE(S36)² + SE(S12)²) / 23,9990.
Riferimento: m_ref = **−0,035251**, SE_ref = **0,005261** (medie 37,664 e 36,818;
`claims.md` riporta −0,0353 ± 0,0053).
Regge se valgono entrambe:
(a) m < 0 e t = m / SE_m ≤ −3;
(b) |m − m_ref| ≤ 3 · √(SE_m² + SE_ref²).
Altrimenti fallisce, e si dice quale delle due condizioni manca.
In `claims.md`, A1 cade con «ripetizione con esito diverso».

**R2 — A3, effetto della sovrapposizione.**
Per q = 12 e q = 36: d_q = Ō(Sq) − Ō(Cq), t_q = d_q / √(SE(Sq)² + SE(Cq)²).
Riferimento: +0,7140 (t = 5,74) e +1,0120 (t = 7,74).
Regge se d_q > 0 e t_q ≥ 3 **per entrambi** i valori di q. Se regge per uno solo, R2
fallisce e si riporta l'esito per ciascun q.
In `claims.md`, A3 cade con «ripetizione senza differenza».

**R3 — A9, netto 0 → 36 req/s agentici.**
n = Ō(S36) − Ō(P0), t di Welch, IC 95% = n ± t₀,₉₇₅(df) · SE.
Riferimento: +0,392 ± 0,158, IC 95% [+0,02, +0,76], t = 2,48.
Regge se t > −2, cioe' il netto non e' significativamente negativo. L'IC 95% si riporta
comunque. R3 non verifica che il netto sia positivo: un netto nullo regge.
In `claims.md`, A9 cade con «netto significativamente negativo in ripetizione».

**R4 — deriva fra giorni.**
Per S12, S36, P0, C12 e C36: Δ = Ō(nuovo) − Ō(riferimento) in req/s,
SE_Δ = √(SE² + SE_ref²), e Δ / SE_Δ. Ogni punto si confronta con il run di
riferimento della stessa mappatura (C12 e C36 con i run condivisi del 20 set).
Riferimenti:

| punto | mappatura | run | Ō | SE |
|---|---|---|---|---|
| S12 | separata | `tre-20260921-150237` | 37,6640 | 0,0845 |
| S36 | separata | `tre-20260921-162248` | 36,8180 | 0,0938 |
| P0 | — | `tre-20260920-102015` | 36,4260 | 0,1274 |
| C12 | condivisa | `tre-20260920-114026` | 36,9500 | 0,0912 |
| C36 | condivisa | `tre-20260920-130038` | 35,8060 | 0,0910 |

E' una misura: **non ha una soglia di successo**. Si riportano i cinque valori,
qualunque siano.

## Regole

1. **Un criterio che fallisce si riporta** e il run non si ripete.
2. **Gate**, per ripetizione, le stesse soglie di `treclassi.sh`: `dropped_iterations`
   > 0 oppure `http_req_failed` > 1%. Con `GATE=0`, come il 21 set, `treclassi.sh`
   registra comunque la ripetizione. Un run (un punto, 5 ripetizioni) non passa se ha
   almeno una ripetizione fuori gate o meno di 5 ripetizioni. Si dichiara e lo script lo
   rifa' **una sola volta, a fine coda**, per intero (5 ripetizioni, nuova cartella).
   L'analisi usa il run rifatto; l'originale entra nel registry come INVALIDA. Se anche
   il run rifatto non passa, il punto non e' utilizzabile e i criteri che lo usano sono
   **non valutabili** (ne' retti ne' caduti). Nessun terzo tentativo.
3. **Arresto per configurazione.** Se lo script si ferma al controllo di `env.txt`
   (30 s, durante il warm-up) nessun dato di misura esiste: il run si dichiara INVALIDA
   nel registry, si corregge la causa senza toccare questo file e si rilancia.
4. **Nessuna analisi prima della fine della campagna.** Durante la notte si leggono solo
   `env.txt`, il file `.tsv` (esito del gate) e le righe di stato del log. Le righe per
   ripetizione del log (`p99 umano=… origine=…`) non si guardano.
5. **Dopo la campagna**: uno script in `tools/` calcola R1-R4 esattamente con le formule
   qui sopra; l'esito va in `docs/RISULTATO-replica-20260924.md`; i run entrano nel
   registry; `claims.md` cambia solo come previsto dalle righe A1, A3 e A9.
