#!/usr/bin/env python3
"""
honeypot_scope.py - Il controllo che ancora il generatore agentico alla realta'.

PERCHE' ADESSO
  Lo sweep di AGENT_SCOPE misura come cambia la sensibilita' del costo al
  variare dell'ampiezza dell'insieme di lavoro di una classe. Quel risultato
  vale come descrizione del mondo solo se sappiamo DOVE, su quell'asse, si
  trovano gli agenti veri. L'honeypot e' l'unica fonte che ce lo puo' dire, ed
  e' offline: non costa tempo di laboratorio e gira in parallelo allo sweep.

  Misura le quattro quantita' che tarano il generatore, e nient'altro:

    AGENT_SESSION = 3      <- pagine per sessione
    AGENT_SCOPE   = 0,02   <- frazione del sito toccata da un singolo client
    AGENT_SKEW    = 0,6    <- concentrazione delle richieste di un client
    3 capitoli contigui    <- contiguita' delle richieste in una sessione

COSA NON PUO' DIMOSTRARE, e va scritto nel paper
  Niente sul costo: l'honeypot non ha un backend confrontabile. Niente di
  causale. E nessuna generalizzazione: e' un sito, per di piu' costruito per
  essere visitato. Serve a giustificare una taratura, non a sostenere un claim.

PRIVACY
  Gli indirizzi IP non vengono mai stampati ne' scritti. Servono solo come
  chiave di raggruppamento e sono sostituiti da un hash troncato.

Uso:
  python3 honeypot_scope.py --peek                 # mostra i campi del log
  python3 honeypot_scope.py /path/ai/log [--pages 18720]
"""
import sys, os, json, gzip, glob, hashlib, argparse, re
from collections import defaultdict, Counter

ap = argparse.ArgumentParser()
ap.add_argument("path", nargs="?", default="data/hplogs")
ap.add_argument("--pages", type=int, default=18720, help="pagine totali del sito")
ap.add_argument("--peek", action="store_true")
ap.add_argument("--min-req", type=int, default=5, help="client sotto questa soglia ignorati")
A = ap.parse_args()

def lines(path):
    files = sorted(glob.glob(os.path.join(path, "*"))) if os.path.isdir(path) else [path]
    for f in files:
        if os.path.isdir(f): continue
        op = gzip.open if f.endswith(".gz") else open
        try:
            with op(f, "rt", errors="replace") as fh:
                for ln in fh:
                    ln = ln.strip()
                    if ln.startswith("{"):
                        try: yield json.loads(ln)
                        except Exception: pass
        except Exception as e:
            print(f"  (salto {os.path.basename(f)}: {e})", file=sys.stderr)

if A.peek:
    for i, r in enumerate(lines(A.path)):
        print(json.dumps(r, indent=2)[:1500]); break
    else:
        print(f"nessuna riga JSON trovata in {A.path}")
    sys.exit()

def field(r, *names):
    for n in names:
        if n in r and r[n] not in ("", "-", None): return r[n]
    return None

anon = lambda s: hashlib.sha256(str(s).encode()).hexdigest()[:10]

def classify(ua):
    u = (ua or "").lower()
    if any(k in u for k in ("gptbot","claudebot","ccbot","google-extended","bytespider",
                            "meta-externalagent","applebot-extended")): return "training"
    if any(k in u for k in ("googlebot","bingbot","duckduckbot","baiduspider",
                            "yandexbot","applebot")):                    return "search"
    if any(k in u for k in ("chatgpt-user","claude-user","perplexity","oai-searchbot",
                            "claude-searchbot","gemini","copilot")):     return "agent"
    if any(k in u for k in ("bot","crawler","spider","scrapy","curl","wget",
                            "python-requests","httpx","go-http")):       return "other-bot"
    if any(k in u for k in ("mozilla","safari","chrome","firefox")):     return "browser"
    return "unknown"

pagenum = lambda p: (lambda m: int(m[-1]) if m else None)(re.findall(r"(\d+)", p or ""))

clients   = defaultdict(lambda: {"urls": Counter(), "cls": Counter(), "n": 0})
conns     = defaultdict(list)
conn_meta = {}
total = skipped = 0
tmin = tmax = None

print(f"lettura di {A.path} ...", file=sys.stderr)
for r in lines(A.path):
    total += 1
    path = field(r, "request_uri", "uri", "path", "request", "url")
    ip   = field(r, "remote_addr", "client_ip", "ip", "addr")
    ua   = field(r, "http_user_agent", "user_agent", "ua", "agent") or ""
    cid  = field(r, "connection", "conn_id", "connection_id", "tcp_conn")
    cnum = field(r, "connection_requests", "conn_req", "req_num")
    ts   = field(r, "time_iso8601", "time", "timestamp", "@timestamp")
    if not path or not ip: skipped += 1; continue
    if isinstance(path, str) and " " in path:           # "GET /x HTTP/1.1"
        parts = path.split()
        path = parts[1] if len(parts) > 2 else path
    if ts:
        tmin = ts if tmin is None or ts < tmin else tmin
        tmax = ts if tmax is None or ts > tmax else tmax
    c = anon(ip)
    clients[c]["urls"][path] += 1
    clients[c]["cls"][classify(ua)] += 1
    clients[c]["n"] += 1
    if cid is not None:
        k = (c, str(cid))
        conns[k].append((int(cnum) if str(cnum).isdigit() else len(conns[k]), path))
        conn_meta[k] = classify(ua)

print(f"\n{'='*66}\n  HONEYPOT - taratura del generatore agentico\n{'='*66}")
print(f"richieste lette      : {total:,}   (scartate {skipped:,})")
print(f"periodo              : {tmin} -> {tmax}")
print(f"client distinti      : {len(clients):,}")
print(f"connessioni distinte : {len(conns):,}" if conns else
      "connessioni          : campo assente, la sezione 1 sara' saltata")
print(f"pagine del sito      : {A.pages:,}")

def pct(v, q):
    if not v: return 0
    v = sorted(v); i = min(len(v)-1, int(q*len(v)))
    return v[i]

CLS = ["agent", "training", "search", "other-bot", "browser", "unknown"]

# ---- 1. AGENT_SESSION -------------------------------------------------
if conns:
    print(f"\n--- 1. PAGINE PER SESSIONE  (tara AGENT_SESSION, valore attuale 3)")
    print(f"{'classe':12s} {'sessioni':>9s} {'mediana':>8s} {'media':>7s} {'p75':>5s} {'p90':>5s} {'p99':>6s}")
    per = defaultdict(list)
    for k, v in conns.items(): per[conn_meta[k]].append(len(v))
    for cl in CLS:
        L = per.get(cl)
        if not L: continue
        print(f"{cl:12s} {len(L):9,d} {pct(L,.5):8d} {sum(L)/len(L):7.1f} "
              f"{pct(L,.75):5d} {pct(L,.90):5d} {pct(L,.99):6d}")

# ---- 2. AGENT_SCOPE ---------------------------------------------------
print(f"\n--- 2. AMPIEZZA DELL'INSIEME DI LAVORO  (tara AGENT_SCOPE, attuale 0,0200)")
print("    frazione del sito toccata da un singolo client, sui client con"
      f" almeno {A.min_req} richieste")
print(f"{'classe':12s} {'client':>7s} {'mediana':>9s} {'media':>9s} {'p90':>9s} {'max':>9s}")
scopes = defaultdict(list)
for c, d in clients.items():
    if d["n"] < A.min_req: continue
    scopes[d["cls"].most_common(1)[0][0]].append(len(d["urls"]) / A.pages)
for cl in CLS:
    S = scopes.get(cl)
    if not S: continue
    print(f"{cl:12s} {len(S):7,d} {pct(S,.5):9.4f} {sum(S)/len(S):9.4f} "
          f"{pct(S,.90):9.4f} {max(S):9.4f}")
print("\n    >>> il valore da confrontare con AGENT_SCOPE=0,0200 e' la mediana"
      " della riga 'agent'")

# ---- 3. AGENT_SKEW ----------------------------------------------------
print(f"\n--- 3. CONCENTRAZIONE  (tara AGENT_SKEW, attuale 0,6)")
print("    quota delle richieste di un client che cade sul 10% di URL piu' visitati")
print(f"{'classe':12s} {'client':>7s} {'mediana':>9s} {'media':>9s}")
conc = defaultdict(list)
for c, d in clients.items():
    if d["n"] < max(10, A.min_req): continue
    cnt = sorted(d["urls"].values(), reverse=True)
    k = max(1, len(cnt)//10)
    conc[d["cls"].most_common(1)[0][0]].append(sum(cnt[:k]) / sum(cnt))
for cl in CLS:
    C = conc.get(cl)
    if not C: continue
    print(f"{cl:12s} {len(C):7,d} {pct(C,.5):9.3f} {sum(C)/len(C):9.3f}")
print("    riferimento: uniforme = 0,10   Zipf(0,6) su 339 = ~0,30   Zipf(1) = ~0,55")

# ---- 4. contiguita' ---------------------------------------------------
if conns:
    print(f"\n--- 4. CONTIGUITA'  (tara il modello 'capitoli contigui')")
    print("    quota di richieste consecutive con numero di pagina adiacente")
    print(f"{'classe':12s} {'sessioni':>9s} {'contigue':>9s} {'ripetute':>9s}")
    adj = defaultdict(lambda: [0, 0, 0])
    for k, v in conns.items():
        if len(v) < 2: continue
        seq = [pagenum(p) for _, p in sorted(v)]
        a = r = t = 0
        for x, y in zip(seq, seq[1:]):
            if x is None or y is None: continue
            t += 1
            if abs(y-x) == 1: a += 1
            if y == x: r += 1
        if t:
            s = adj[conn_meta[k]]; s[0] += a; s[1] += r; s[2] += t
    for cl in CLS:
        s = adj.get(cl)
        if not s or not s[2]: continue
        print(f"{cl:12s} {s[2]:9,d} {s[0]/s[2]:9.3f} {s[1]/s[2]:9.3f}")

# ---- 5. composizione --------------------------------------------------
print(f"\n--- 5. COMPOSIZIONE DEL TRAFFICO")
tot = Counter()
for d in clients.values():
    for cl, n in d["cls"].items(): tot[cl] += n
S = sum(tot.values()) or 1
for cl in CLS:
    if tot.get(cl): print(f"{cl:12s} {tot[cl]:10,d} richieste  {100*tot[cl]/S:5.1f}%")

print(f"\n{'='*66}")
print("  Questo output giustifica o smentisce i parametri del generatore.")
print("  Se la mediana di scope per la classe 'agent' e' lontana da 0,0200,")
print("  va detto nel paper, e lo sweep di scope diventa ancora piu' utile")
print("  perche' copre l'intervallo in cui cade il valore vero.")
print(f"{'='*66}")
