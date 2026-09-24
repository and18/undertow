# Undertow — istruzioni per Claude Code

Progetto di ricerca indipendente di Andrea Licitra: quanto costa all'origine ogni classe di
traffico (umana, esaustiva, agentica) e da cosa dipende quel costo. Testbed k6 → Varnish →
gunicorn/Flask → PostgreSQL sul server `lab`; honeypot pubblico `theslowshelf.org` sul server
`honeypot`. Obiettivo: tesi + paper (prima arXiv, sede scelta dopo il freeze del paper).

**Rispondi sempre in italiano, con linguaggio semplice.** Il paper e il README sono in inglese.

## Fase attuale

Esperimenti **chiusi**, evidenze **congelate**, figure costruite. Prossimo passo: scrittura, in
quest'ordine: Results → Methodology → Mechanism → Limitations → Related Work → Implications →
Introduction → Abstract → Conclusion. Gli esperimenti non generano piu' la storia: verificano
che quella congelata regga.

## Fonti di verita' — in quest'ordine

1. `docs/claims.md` — cosa si puo' affermare e con quale stato. **Vince su tutto.**
2. `docs/VERIFICHE-chiuse.md` — numeri finali e letteratura verificata.
3. `docs/registry.csv` — ogni run, il suo ruolo, il claim o la figura che alimenta.
4. `docs/retractions.md` — le sei interpretazioni ritirate. Non riproporle.
5. `docs/UNDERTOW-CONTESTO.md` — contesto di lavoro. Altri documenti (master, thesis,
   findings) sono **struttura, non fonte numerica**: se un numero diverge, vince `claims.md`.

## Regole di rigore

- Ogni frase del paper appartiene a una riga di `claims.md`. Nessun claim nuovo senza una misura.
- Parole vietate dove i dati non le sostengono: "domina" (B contro C), "il traffico agentico
  riduce il lavoro all'origine", "benigno", "confine di residenza".
- Nessun ragionamento sull'esito di un controllo prima di averlo eseguito.
- Nessun numero derivato per divisione senza verificare cosa misura il divisore.
- Rapporti ed elasticita' si calcolano **dalle medie**, mai da valori gia' arrotondati.
- Mappatura **condivisa** e **separata** non si mescolano mai nello stesso confronto
  (errore trovato il 23 settembre: vedi il changelog di `claims.md` v3).
- Arrotondamento decimale half-up (`figure_style.num`), segno meno tipografico.

## Git

- Si committa **solo** da questa copia (`~/undertow` in WSL). Lab e honeypot sono in sola lettura.
- **Mai** righe `Co-Authored-By` o `Claude-Session` nei messaggi di commit.
- Mai `git push --force`. Prima di ogni commit: `git status` e `git diff --stat`, e mostra il
  riepilogo ad Andrea. Il push lo approva lui.
- Nei blocchi di comandi lunghi usa `set -e`: se un passo fallisce, ci si ferma.

## Server `lab` e `honeypot`

- Solo lettura. Comandi nella forma compatta `ssh lab '...'`, niente heredoc.
- **I log dell'honeypot contengono IP in chiaro.** Non leggerli, non stamparli, non copiarli.
  Si usano solo script che aggregano o fanno hash (`tools/honeypot_*.py`) e si riporta solo
  l'output aggregato. `data/hplogs/` non si legge mai.
- Testi Gutenberg: non si ridistribuiscono (solo ID e schema).
- Se mai servisse lanciare una campagna: verificare `env.txt` 30 secondi dopo il lancio.

## Figure

- `make figures` rigenera tutto da `data/derived/` (su Windows: `python analysis/build_figures.py`).
- Nessuna figura si ritocca a mano: si corregge lo script o il CSV. Nessuna figura da Grafana.
- Design system in `analysis/figure_style.py` (font Source Sans 3, colori semantici per classe,
  ± 1 SE sempre disegnato). Ogni script di figura ha in testa il suo "design pass".
- La build si ferma su glifi mancanti, testo fuori margine o sovrapposto.

## Aperti al 24 settembre

- Chiusi il 24 settembre: FIG-06 (C1 da `tools/cpu_validation.py`), A7 (divisore α·λ
  configurato, 0 / 13,9968 / 27,9965 / 41,9977), C2 (5 263 ± 8 oggetti da
  `tools/cache_capacity.py`).
- B3, B4, B5: i CSV di FIG-A1 e FIG-A2, ora generati da script, cambiano valori stampati
  (elasticita' a scope 0,06: 1,62 invece di 1,63; p99 umano +37,0 invece di +36,9 ms,
  t 37,3; origine 52,6 invece di 52,7). Da decidere se aggiornare righe e didascalie.
- Capitolo 5: GPTBot 217 (decisions §17) contro 20,4 (§5.3.3); denominatori della cache
  245 MB / 438 MB; tabella 5.3.2 non confrontabile con la nuova analisi.
- `docs/thesis.md`, `findings.md`, `contribution-boundary.md`: narrativa superata, da spostare
  in `docs/archive/` nella fase di pulizia.
