#!/usr/bin/env python3
"""
patch-chapter5.py - Correzioni fattuali al Capitolo 5.

PERCHE' UN PATCH E NON UNA RISCRITTURA
  Il capitolo e' stato sottoposto ad audit il 17 settembre e ogni affermazione
  quantitativa porta fonte, denominatore e finestra. Riscriverlo per intero
  significherebbe rimettere in gioco mille righe gia' verificate per cambiarne
  sette. La revisione STRUTTURALE - se il capitolo debba spostarsi dopo i
  risultati - si fa nella fase di scrittura, non adesso.

COSA CORREGGE
  1. aipref: le revisioni erano ferme a -04 di fine 2025.
  2. Cloudflare 15 settembre: era descritto come "effective"; nessuna fonte
     primaria conferma l'entrata in vigore, e l'annuncio e' piu' ristretto.
  3. Zhang et al.: il secondo autore e' Jinqing Cai, non "Cai, Y.".
  4. Web Bot Auth: aggiunto il dato aggiornato sulla finestra a 41 giorni.
  5. Nuovo paragrafo 5.3.5: l'insieme di lavoro in finestra, che e' la misura
     honeypot piu' rilevante per il risultato sperimentale.
  6. SemDN: aggiunto allo Scenario B e alla bibliografia.
  7. 5.10: la domanda "se le differenze di comportamento implichino differenze
     di costo" ora ha una risposta e va detto.
  8. Note di revisione aggiornate.

Ogni sostituzione e' ancorata: se un'ancora non si trova, lo script NON scrive
nulla e dice quale.

Uso:  cd ~/undertow && python3 tools/patch-chapter5.py
"""
import sys, os

P = "docs/chapter5-where-the-web-is-going.md"
if not os.path.exists(P):
    sys.exit(f"{P} non trovato: esegui dalla radice del repo (~/undertow)")
s = open(P).read()
if "5.3.5" in s:
    sys.exit("patch gia' applicata (5.3.5 presente)")

E = []

# ---- 1. aipref, revisioni aggiornate
E.append((
"""The active drafts are `draft-ietf-aipref-vocab` and
`draft-ietf-aipref-attach` (both at revision -04 as of late 2025, with
subsequent updates during 2026).""",
"""The active drafts are `draft-ietf-aipref-vocab`, at revision **-08 of
13 September 2026**, and `draft-ietf-aipref-attach`, at revision **-05 of
18 August 2026** (verified against the IETF Datatracker on 22 September
2026).""" ))

# ---- 2. il 15 settembre: annuncio, non entrata in vigore confermata
E.append((
"""Announced on 1 July 2026 and effective **15 September 2026**, Cloudflare
changed its default handling of AI crawler traffic. The change, as
documented:""",
"""Announced on 1 July 2026 and **stated to take effect on 15 September
2026**, Cloudflare described a change to its default handling of AI crawler
traffic. **The wording matters: the only primary source located is the
prospective announcement of 1 July 2026. No Cloudflare post or changelog
dated on or near 15 September 2026 confirming activation was found during a
systematic search on 22 September 2026.** Several third-party accounts
describe the change as a network-wide default block; the primary text does
not support that reading. The change, as documented in the announcement:""" ))

E.append((
"""- It applies to **new domains and customers, new sites added by existing
  customers, and all existing free-tier customers**. Paying customers with
  existing configurations retain them.""",
"""- The changelog text specifies **new domains onboarding to Cloudflare**.
  The blog post is read by some sources as extending to new sites added by
  existing customers and to existing free-tier customers; **this wider scope
  could not be confirmed against a primary source and should be verified or
  dropped before submission**. Paying customers with existing configurations
  retain them.""" ))

# ---- 3. Zhang, secondo autore
E.append((
"""Zhang, Y., Cai, Y., Wildani, A. and Klimovic, A. (2025). *Rethinking Web
Cache Design for the AI Era*. SoCC '25, pp. 535-542.
doi:10.1145/3772052.3772255.""",
"""Zhang, Y., Cai, J., Wildani, A. and Klimovic, A. (2025). *Rethinking Web
Cache Design for the AI Era*. SoCC '25, pp. 535-542.
doi:10.1145/3772052.3772255. *Note for Related Work: this study varies the
proportion of AI traffic from 0% to 100% and reports cache hit ratios; it
does not measure per-request cost, and it fixes the overlap between AI and
human working sets at 10-20% without varying it.*

Hua, P. and Xiao, Y. (2026). *Semantics Delivery Network: Rethinking Web
Retrieval Infrastructure for LLM Agents*. HotNets 2026. arXiv:2609.22486.""" ))
# variante con trattino unicode, se il file usa l'en dash
E.append((None, None))  # segnaposto, gestito sotto

# ---- 4. Web Bot Auth, finestra aggiornata
E.append((
"""On the measurement site, over 36 days, **exactly one operator of
twenty-nine sent Web Bot Auth signature headers**: AhrefsBot, on all
19,744 of its requests.""",
"""On the measurement site, over 36 days, **exactly one operator of
twenty-nine sent Web Bot Auth signature headers**: AhrefsBot, on all
19,744 of its requests. A later retrieval covering 41 days (12 August -
21 September 2026, 520,038 classified requests) gives **19,930 signed
requests, 3.83% of the total** - and, notably, **none of them from clients
declaring an agentic user agent**. Signing and declaring oneself an agent
were, in this sample, disjoint behaviours.""" ))

# ---- 5. nuovo 5.3.5, l'insieme di lavoro in finestra
E.append((
"""### 5.3.4 Interpretation""",
"""### 5.3.5 Working-set size within a cache-relevant window

One behavioural quantity deserves separate treatment because it is the
parameter the experimental chapters turn out to depend on most: **how many
distinct objects a single client touches within a window short enough to
matter to a cache.**

Counting distinct URLs per client over the whole observation period answers
the wrong question. An object survives in an LRU-like cache only if it is
re-requested within the cache's characteristic time - on the testbed of the
following chapters, approximately 143 seconds. Measured over a sliding
window of that length across 41 days, the agentic class (31 clients with at
least five requests) gives:

| Statistic | Distinct URLs in a 143 s window |
|---|---|
| Median | 4 |
| Mean | 240 |
| 90th percentile | **670** |
| Maximum | 678 |

The distribution is strongly bimodal: most agentic clients touch a handful
of pages, a minority touch several hundred. Widening the window to 600 s or
3600 s barely moves these figures for this class, while for training
crawlers the 3600 s figure (median 129) is an order of magnitude above the
143 s figure (median 12) - the training class spreads its accesses thinly,
which is precisely why it caches badly.

*Limitations:* 31 clients on one site over 41 days; the 90th percentile of
so small a sample is fragile, and nothing here licenses a statement about
agentic traffic on the web at large.

### 5.3.4 Interpretation""" ))

# ---- 6. SemDN nello Scenario B
E.append((
"""*Design implication:* origin request volume ceases to be a proxy for
interaction volume.""",
"""A concrete architectural proposal in this direction appeared during the
writing of this chapter: Hua and Xiao's *Semantics Delivery Network*
(HotNets 2026) argues that semantic chunk retrieval should become a
first-class network-delivery abstraction, and reports that a page-first
retrieval path processes between two and three orders of magnitude more
content than the agent ultimately consumes. It is cited here as evidence
that the scenario is being actively designed for, not as evidence that it
will obtain.

*Design implication:* origin request volume ceases to be a proxy for
interaction volume.""" ))

# ---- 7. 5.10, la domanda ora ha una risposta
E.append((
"""**Behavioural differences may imply cost differences.** If classes access
content with different locality, they interact differently with a shared
cache, and therefore potentially impose different costs on the tiers
behind it. Whether they do, and by how much, is an empirical question
that external data cannot answer - it requires a controlled origin.""",
"""**Behavioural differences may imply cost differences.** If classes access
content with different locality, they interact differently with a shared
cache, and therefore potentially impose different costs on the tiers
behind it. Whether they do, and by how much, is an empirical question
that external data cannot answer - it requires a controlled origin. *The
experimental chapters answer it, and the answer is less simple than the
question: the per-request cost of the agentic class is not a fixed quantity
at all, but changes sign as a function of the size of that class's working
set. The quantity measured in §5.3.5 is therefore not a descriptive
statistic but the input the cost depends on.*""" ))

# ---- 8. note di revisione
E.append((
"""**Claims requiring verification before submission**""",
"""**Resolved during verification of 22 September 2026**

- *aipref draft revisions.* Resolved: attach-05 (18 August 2026) and
  vocab-08 (13 September 2026), verified against the IETF Datatracker.
  Item 4 below is therefore closed.
- *Web Bot Auth standardisation status.* Confirmed:
  `draft-ietf-webbotauth-httpsig-protocol-00`, 1 September 2026, Standards
  Track, built on RFC 9421, defining `Signature-Agent` alongside
  `Signature-Input`.
- *Post-activation data for the 15 September change.* Searched and **not
  found**. §5.7.2 has been reworded: the only primary source is the
  prospective announcement, and the scope described there is narrower than
  several third-party accounts suggest. Item 5 below is closed as
  "searched, nothing published".
- *Cloudflare cost figures.* Confirmed absent: Cloudflare publishes volumes,
  traffic shares and crawl-to-refer ratios, never per-class cost in
  currency, bandwidth or CPU. Any claim that it does must not be made.
- *Zhang et al. author list and method.* Corrected in the bibliography, and
  annotated: they vary the AI proportion from 0% to 100% but measure hit
  ratios rather than per-request cost, and fix working-set overlap at
  10-20% without varying it.

**Claims requiring verification before submission**""" ))

# applica
for pair in E:
    if pair[0] is None:
        continue
    old, new = pair
    if old not in s:
        sys.exit("ANCORA NON TROVATA, niente scritto. Attesa:\n---\n" + old[:220] + "\n---")
    s = s.replace(old, new, 1)

open(P, "w").write(s)
print(f"{P}: {len([p for p in E if p[0]])} correzioni applicate\n")
print("Non corretto, e va fatto nella fase di scrittura:")
print("  - la tabella di composizione 5.3.2 usa un classificatore a 8 categorie su")
print("    443.232 richieste in 36 giorni; le analisi del 21-22 settembre usano un")
print("    classificatore a 6 categorie su 520.038 richieste in 41 giorni. NON sono")
print("    direttamente confrontabili e non le ho fuse: va deciso quale usare.")
print("  - la collocazione del capitolo. Cosi' com'e' e' prospettico e precede i")
print("    risultati; l'argomento per spostarlo dopo il meccanismo e' che le sue")
print("    affermazioni diventano sostenute invece che anticipate.")