#!/usr/bin/env python3
"""
honeypot_window.py - Insieme di lavoro dentro una finestra temporale.

PERCHE'
  honeypot_scope.py conta gli URL distinti per client sull'intero periodo di
  osservazione. Per la cache quella grandezza non serve: un oggetto sopravvive
  solo se rivisitato entro il tempo caratteristico T_C = capienza / tasso di
  miss, che sul nostro banco vale ~143 s. Quello che conta e' quanti oggetti
  distinti un client tocca DENTRO una finestra di quell'ordine.

  La misura su 40 giorni sovrastima l'insieme di lavoro istantaneo. Dato che lo
  sweep ha mostrato che il costo marginale agentico passa da -0,048 a +0,438
  al variare dell'ampiezza dell'insieme, questo e' ora il numero piu'
  importante che l'honeypot possa fornire.

COSA FA
  Per ogni client e per ogni finestra scorrevole di durata W, conta gli URL
  distinti. Riporta la distribuzione del massimo per client, che e' il valore
  che il generatore dovrebbe riprodurre.

COSA NON PUO' DIMOSTRARE
  Niente sul costo. E' una taratura, e vale per questo sito.

PRIVACY
  Nessun IP viene stampato o scritto: solo hash troncati come chiave.

Uso:  sudo python3 honeypot_window.py /var/log/nginx --pages 18720
"""
import sys, os, json, gzip, glob, hashlib, argparse
from collections import defaultdict, Counter, deque

ap = argparse.ArgumentParser()
ap.add_argument("path", nargs="?", default="/var/log/nginx")
ap.add_argument("--pages", type=int, default=18720)
ap.add_argument("--windows", default="143,600,3600",
                help="durate in secondi, separate da virgola; 143 = T_C del banco")
ap.add_argument("--min-req", type=int, default=5)
A = ap.parse_args()
WINDOWS = [int(w) for w in A.windows.split(",")]

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

def epoch(ts):
    """2026-09-21T00:00:21+00:00 -> secondi, senza dipendenze esterne."""
    try:
        d, t = ts[:19].split("T")
        Y, M, D = (int(x) for x in d.split("-"))
        h, m, s = (int(x) for x in t.split(":"))
        days = (Y-1970)*365 + (Y-1969)//4 + sum((0,31,59,90,120,151,181,212,243,273,304,334)[:M-1]) + (D-1)
        if M > 2 and Y % 4 == 0: days += 1
        return days*86400 + h*3600 + m*60 + s
    except Exception:
        return None

anon = lambda s: hashlib.sha256(str(s).encode()).hexdigest()[:10]

ev = defaultdict(list)          # client -> [(t, url)]
cls = defaultdict(Counter)
total = 0
print(f"lettura di {A.path} ...", file=sys.stderr)
for r in lines(A.path):
    u, ip, ua, ts = r.get("u"), r.get("ip"), r.get("ua", ""), r.get("t")
    if not (u and ip and ts): continue
    e = epoch(ts)
    if e is None: continue
    c = anon(ip)
    ev[c].append((e, u)); cls[c][classify(ua)] += 1; total += 1

print(f"\n{'='*70}\n  INSIEME DI LAVORO IN FINESTRA — quello che la cache vede davvero\n{'='*70}")
print(f"richieste {total:,}   client {len(ev):,}   sito {A.pages:,} pagine")
print(f"finestre: {', '.join(str(w)+'s' for w in WINDOWS)}   (143 s = T_C del banco)\n")

def pct(v, q):
    if not v: return 0
    v = sorted(v); return v[min(len(v)-1, int(q*len(v)))]

CLS = ["agent", "training", "search", "other-bot", "browser", "unknown"]
for W in WINDOWS:
    peak = defaultdict(list)
    for c, e in ev.items():
        if len(e) < A.min_req: continue
        e.sort()
        dq, seen, best = deque(), Counter(), 0
        for t, u in e:
            dq.append((t, u)); seen[u] += 1
            while dq and dq[0][0] < t - W:
                _, ou = dq.popleft(); seen[ou] -= 1
                if seen[ou] == 0: del seen[ou]
            best = max(best, len(seen))
        peak[cls[c].most_common(1)[0][0]].append(best)
    print(f"--- finestra {W}s: URL distinti al picco, per client")
    print(f"{'classe':12s} {'client':>7s} {'mediana':>8s} {'media':>8s} {'p90':>7s} {'max':>7s}"
          f" {'scope mediano':>14s} {'scope p90':>10s}")
    for cl in CLS:
        P = peak.get(cl)
        if not P: continue
        print(f"{cl:12s} {len(P):7,d} {pct(P,.5):8d} {sum(P)/len(P):8.1f} {pct(P,.9):7d} "
              f"{max(P):7d} {pct(P,.5)/A.pages:14.5f} {pct(P,.9)/A.pages:10.5f}")
    print()

print(f"{'='*70}")
print("  Da confrontare con AGENT_SCOPE del generatore: 0,02 = 339 basi = 1 017")
print("  oggetti nominali. Lo sweep ha misurato il costo marginale agentico a")
print("  0,02 / 0,06 / 0,20, cioe' 1 017 / 3 052 / 10 172 oggetti contro una")
print("  capienza di 5 274. Il picco in finestra dice dove cadono gli agenti veri.")
print(f"{'='*70}")