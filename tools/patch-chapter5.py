#!/usr/bin/env python3
"""
patch-chapter5.py - Correzioni fattuali al Capitolo 5. VERSIONE 2.

La v1 falliva su un'ancora: la bibliografia usa "535–542" con en dash, non
con trattino. Stesso problema in 5.10, che usa un em dash. Corretti entrambi.

PERCHE' UN PATCH E NON UNA RISCRITTURA
  Il capitolo e' passato per un audit il 17 settembre e ogni affermazione
  quantitativa porta fonte, denominatore e finestra. Riscriverlo per intero
  significherebbe rimettere in gioco mille righe verificate per cambiarne
  sette. La revisione STRUTTURALE si fa nella fase di scrittura.

Ogni sostituzione e' ancorata: se un'ancora non si trova, non scrive nulla.

Uso:  cd ~/undertow && python3 tools/patch-chapter5.py
"""
import sys, os

EN = "\u2013"
EM = "\u2014"

P = "docs/chapter5-where-the-web-is-going.md"
if not os.path.exists(P):
    sys.exit(f"{P} non trovato: esegui dalla radice del repo (~/undertow)")
s = open(P, encoding="utf-8").read()
if "5.3.5" in s:
    sys.exit("patch gia' applicata (5.3.5 presente)")

E = []

E.append((
"""The active drafts are `draft-ietf-aipref-vocab` and
`draft-ietf-aipref-attach` (both at revision -04 as of late 2025, with
subsequent updates during 2026).""",
"""The active drafts are `draft-ietf-aipref-vocab`, at revision **-08 of
13 September 2026**, and `draft-ietf-aipref-attach`, at revision **-05 of
18 August 2026** (verified against the IETF Datatracker on 22 September
2026)."""))

E.append((
"""Announced on 1 July 2026 and effective **15 September 2026**, Cloudflare
changed its default handling of AI crawler traffic. The change, as
documented:""",
"""Announced on 1 July 2026 and **stated to take effect on 15 September
2026**, Cloudflare described a change to its default handling of AI crawler
traffic. The wording matters. The only primary source located is the
prospective announcement of 1 July 2026; a systematic search on 22 September
2026 found **no Cloudflare post or changelog dated on or near 15 September
confirming activation**. Several third-party accounts describe the change as
a network-wide default block, and the primary text does not support that
reading. The change, as documented in the announcement:"""))

E.append((
"""- It applies to **new domains and customers, new sites added by existing
  customers, and all existing free-tier customers**. Paying customers with
  existing configurations retain them.""",
"""- The changelog text specifies **new domains onboarding to Cloudflare**.
  The blog post is read by some sources as extending to new sites added by
  existing customers and to existing free-tier customers; this wider scope
  **could not be confirmed against a primary source and should be verified
  or dropped before submission**. Paying customers with existing
  configurations retain them."""))

E.append((
"""Zhang, Y., Cai, Y., Wildani, A. and Klimovic, A. (2025). *Rethinking Web
Cache Design for the AI Era*. SoCC '25, pp. 535""" + EN + """542.
doi:10.1145/3772052.3772255.""",
"""Hua, P. and Xiao, Y. (2026). *Semantics Delivery Network: Rethinking Web
Retrieval Infrastructure for LLM Agents*. HotNets 2026. arXiv:2609.22486.

Zhang, Y., Cai, J., Wildani, A. and Klimovic, A. (2025). *Rethinking Web
Cache Design for the AI Era*. SoCC '25, pp. 535""" + EN + """542.
doi:10.1145/3772052.3772255. *Note for Related Work: this study varies the
proportion of AI traffic from 0% to 100% and reports cache hit ratios; it
does not measure per-request cost, and it fixes the overlap between AI and
human working sets at 10""" + EN + """20% without varying it.*"""))

E.append((
"""On the measurement site, over 36 days, **exactly one operator of
twenty-nine sent Web Bot Auth signature headers**: AhrefsBot, on all
19,744 of its requests.""",
"""On the measurement site, over 36 days, **exactly one operator of
twenty-nine sent Web Bot Auth signature headers**: AhrefsBot, on all
19,744 of its requests. A later retrieval covering 41 days (12 August """ + EN + """
21 September 2026, 520,038 classified requests) gives **19,930 signed
requests, 3.83% of the total** """ + EM + """ and, notably, **none from clients
declaring an agentic user agent**. In this sample, signing and declaring
oneself an agent were disjoint behaviours."""))

E.append((
"""### 5.3.4 Interpretation""",
"""### 5.3.5 Working-set size within a cache-relevant window

One behavioural quantity deserves separate treatment, because it is the
parameter the experimental chapters turn out to depend on most: **how many
distinct objects a single client touches within a window short enough to
matter to a cache.**

Counting distinct URLs per client over a whole observation period answers
the wrong question. An object survives in an LRU-like cache only if it is
re-requested within the cache's characteristic time """ + EM + """ on the testbed of
the following chapters, approximately 143 seconds. Measured over a sliding
window of that length across 41 days, the agentic class (31 clients with at
least five requests) gives:

| Statistic | Distinct URLs in a 143 s window |
|---|---|
| Median | 4 |
| Mean | 240 |
| 90th percentile | **670** |
| Maximum | 678 |

The distribution is strongly bimodal: most agentic clients touch a handful
of pages, a minority several hundred. Widening the window to 600 s or
3600 s barely moves these figures for this class. For training crawlers it
does: the 3600 s median is 129 against 12 at 143 s """ + EM + """ that class spreads
its accesses thinly over time, which is precisely why it caches badly.

*Limitations:* 31 clients, one site, 41 days. The 90th percentile of so
small a sample is fragile, and nothing here licenses a statement about
agentic traffic on the web at large.

### 5.3.4 Interpretation"""))

E.append((
"""*Design implication:* origin request volume ceases to be a proxy for
interaction volume.""",
"""A concrete architectural proposal in this direction appeared while this
chapter was being written. Hua and Xiao's *Semantics Delivery Network*
(HotNets 2026) argues that semantic chunk retrieval should become a
first-class network-delivery abstraction, and reports that a page-first
retrieval path processes between two and three orders of magnitude more
content than the agent ultimately consumes. It is cited as evidence that
this scenario is being actively designed for, not as evidence that it will
obtain.

*Design implication:* origin request volume ceases to be a proxy for
interaction volume."""))

E.append((
"""**Behavioural differences may imply cost differences.** If classes access
content with different locality, they interact differently with a shared
cache, and therefore potentially impose different costs on the tiers
behind it. Whether they do, and by how much, is an empirical question
that external data cannot answer """ + EM + """ it requires a controlled origin.""",
"""**Behavioural differences may imply cost differences.** If classes access
content with different locality, they interact differently with a shared
cache, and therefore potentially impose different costs on the tiers
behind it. Whether they do, and by how much, is an empirical question
that external data cannot answer """ + EM + """ it requires a controlled origin.
*The experimental chapters answer it, and the answer is less simple than
the question: the per-request cost of the agentic class is not a fixed
quantity at all, but changes sign as a function of the size of that class's
working set. The quantity measured in """ + chr(167) + """5.3.5 is therefore not a descriptive
statistic but the input on which that cost depends.*"""))

E.append((
"""**Claims requiring verification before submission**""",
"""**Resolved during verification of 22 September 2026**

- *aipref draft revisions.* Resolved: attach-05 (18 August 2026) and
  vocab-08 (13 September 2026), verified against the IETF Datatracker.
  Item 4 below is closed.
- *Web Bot Auth standardisation status.* Confirmed:
  `draft-ietf-webbotauth-httpsig-protocol-00`, 1 September 2026, Standards
  Track, built on RFC 9421, defining `Signature-Agent` alongside
  `Signature-Input`.
- *Post-activation data for the 15 September change.* Searched and **not
  found**. """ + chr(167) + """5.7.2 has been reworded: the only primary source is the
  prospective announcement, and its scope is narrower than several
  third-party accounts suggest. Item 5 below is closed as "searched,
  nothing published".
- *Cloudflare cost figures.* Confirmed absent. Cloudflare publishes volumes,
  traffic shares and crawl-to-refer ratios, never per-class cost in
  currency, bandwidth or CPU. No claim that it does may be made.
- *Zhang et al. author list and method.* Corrected in the bibliography and
  annotated: the study varies the AI proportion from 0% to 100% but
  measures hit ratios rather than per-request cost, and fixes working-set
  overlap at 10""" + EN + """20% without varying it.

**Claims requiring verification before submission**"""))

for old, new in E:
    if old not in s:
        sys.exit("ANCORA NON TROVATA, niente scritto. Attesa:\n---\n" + old[:200] + "\n---")
    s = s.replace(old, new, 1)

open(P, "w", encoding="utf-8").write(s)
print(f"{P}: {len(E)} correzioni applicate\n")
print("NON corretto, e va deciso nella fase di scrittura:")
print("  - la tabella 5.3.2 usa un classificatore a 8 categorie su 443.232 richieste")
print("    in 36 giorni; le analisi del 21-22 settembre ne usano 6 su 520.038 in 41.")
print("    NON sono confrontabili e non le ho fuse.")
print("  - 5.3.3 riporta GPTBot a 20,4 richieste per connessione; decisions.md 17")
print("    dice 217. Le due cifre vanno riconciliate o distinte (media contro massimo).")
print("  - la collocazione del capitolo: cosi' com'e' e' prospettico e precede i")
print("    risultati.")