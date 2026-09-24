#!/usr/bin/env python3
"""
honeypot_aggregate.py — tutti gli aggregati dell'honeypot usati nel paper, su una finestra
temporale fissa [--from, --to) in UTC (claim C3, C5, C6; FIG-A3).

PERCHE'
  honeypot_scope.py e honeypot_window.py leggono tutto quello che trovano nella cartella dei
  log: con la rotazione, il periodo cambia a ogni lancio. Questo script fissa la finestra e
  ricalcola gli stessi aggregati con la stessa logica, cosi' i numeri del paper si
  riottengono da uno snapshot dei log.

LOGICA RIUSATA (identica, salvo il filtro temporale)
  classify(), bookchap(), field(), pct() da honeypot_scope.py; finestra scorrevole da
  honeypot_window.py.
  C3  per ogni client con almeno --min-req richieste nella finestra del paper: massimo di URL
      distinti in una finestra scorrevole di --window s (143 = T_C del banco); classe del
      client = classe piu' frequente delle sue richieste. Per classe: client, mediana, media,
      p90, max (pct: indice int(q*n) sui valori ordinati, come negli script originali).
  C5  honeypot_scope.py, sezione 4: per ogni connessione (client, conn) con almeno 2
      richieste, ordinate per conn_req, coppie consecutive che si mappano su (libro,
      capitolo); contigua = stesso libro e |Δcapitolo| = 1, ripetuta = stesso libro e stesso
      capitolo. Classe della connessione = classe dell'ultima richiesta letta (conn_meta).
      Il denominatore sono COPPIE. Si riportano anche le connessioni che contribuiscono
      almeno una coppia, i client distinti di quelle connessioni e tutte le connessioni
      della classe.
  C6  honeypot_scope.py, sezione 6: richiesta firmata se sig_agent o sig_input e' presente e
      non vuoto; firmate / totali per classe della richiesta.
  Totali: richieste nella finestra, client, connessioni; righe scartate e fuori finestra.

DIFFERENZE DAGLI SCRIPT ORIGINALI (solo queste)
  1. Filtro sulla finestra [--from, --to) in UTC.
  2. honeypot_window.epoch() ignorava il fuso orario del timestamp; qui il timestamp e' letto
     con il suo offset e convertito in UTC, poi troncato al secondo come epoch(). I fusi
     trovati sono stampati: se sono tutti +00:00, la differenza e' nulla.
  3. Conseguenza del filtro: per C5/C6 le righe senza timestamp valido, che
     honeypot_scope.py contava, qui sono escluse perche' non collocabili nella finestra;
     il loro numero e' stampato e scritto nei totali (lines_without_valid_timestamp).
  Selezione delle righe: C3 esattamente come honeypot_window.py (campi u, ip, ua, t letti
  con r.get, riga tenuta se u, ip e t non sono vuoti); C5/C6 e totali esattamente come
  honeypot_scope.py (field() con i nomi alternativi, riga tenuta se url e ip ci sono,
  «GET /x HTTP/1.1» ridotto al percorso).

PRIVACY
  L'IP serve solo come chiave di raggruppamento in memoria, attraverso un HMAC con una chiave
  casuale nuova a ogni lancio: nessun IP, nessun hash, nessuna riga di log viene stampata o
  scritta. Nei CSV ci sono solo conteggi e quantili per classe.

SCRIVE (data/derived/)
  honeypot_totals.csv        quantita', valore
  honeypot_window.csv        classe, client, mediana, media, p90, max       (C3)
  honeypot_contiguity.csv    classe, coppie, contigue, ripetute, quote,
                             connessioni con coppie, client, connessioni    (C5)
  honeypot_signed.csv        classe, firmate, totali, quota                 (C6)

Uso:
    python3 tools/honeypot_aggregate.py --logs data/hplogs/snapshot-20260924 \\
        --from 2026-08-12T00:00:00+00:00 --to 2026-09-22T00:00:00+00:00
"""
import argparse
import csv
import glob
import gzip
import hashlib
import hmac
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "derived"
CLS = ["agent", "training", "search", "other-bot", "browser", "unknown"]


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", required=True, help="cartella dello snapshot dei log")
    ap.add_argument("--from", dest="t0", required=True, help="inizio, ISO 8601 con fuso")
    ap.add_argument("--to", dest="t1", required=True, help="fine esclusa, ISO 8601 con fuso")
    ap.add_argument("--window", type=int, default=143, help="secondi; 143 = T_C del banco")
    ap.add_argument("--min-req", type=int, default=5, help="come gli script originali")
    return ap.parse_args()


# ---- da honeypot_scope.py, invariati --------------------------------------------------
def lines(path):
    files = sorted(glob.glob(os.path.join(path, "*"))) if os.path.isdir(path) else [path]
    for f in files:
        if os.path.isdir(f):
            continue
        op = gzip.open if f.endswith(".gz") else open
        try:
            with op(f, "rt", errors="replace") as fh:
                for ln in fh:
                    ln = ln.strip()
                    if ln.startswith("{"):
                        try:
                            yield json.loads(ln)
                        except Exception:
                            pass
        except Exception as e:
            print(f"  (salto {os.path.basename(f)}: {type(e).__name__})", file=sys.stderr)


def field(r, *names):
    for n in names:
        if n in r and r[n] not in ("", "-", None):
            return r[n]
    return None


def classify(ua):
    u = (ua or "").lower()
    if any(k in u for k in ("gptbot", "claudebot", "ccbot", "google-extended", "bytespider",
                            "meta-externalagent", "applebot-extended")): return "training"
    if any(k in u for k in ("googlebot", "bingbot", "duckduckbot", "baiduspider",
                            "yandexbot", "applebot")):                    return "search"
    if any(k in u for k in ("chatgpt-user", "claude-user", "perplexity", "oai-searchbot",
                            "claude-searchbot", "gemini", "copilot")):    return "agent"
    if any(k in u for k in ("bot", "crawler", "spider", "scrapy", "curl", "wget",
                            "python-requests", "httpx", "go-http")):      return "other-bot"
    if any(k in u for k in ("mozilla", "safari", "chrome", "firefox")):   return "browser"
    return "unknown"


def bookchap(p):
    m = re.search(r"/book/(\d+)[^/]*/chapter-0*(\d+)", p or "")
    if m:
        return (m.group(1), int(m.group(2)))
    n = re.findall(r"(\d+)", p or "")
    return (None, int(n[-1])) if n else None


def pct(v, q):
    if not v:
        return 0
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))]
# ---------------------------------------------------------------------------------------


def to_utc(ts):
    """Timestamp ISO 8601 -> (secondi UTC, fuso come scritto nel log)."""
    s = str(ts).strip()
    m = re.search(r"(Z|[+-]\d{2}:?\d{2})$", s)
    tz = m.group(1) if m else "(nessuno)"
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None, tz
    if d.tzinfo is None:
        return None, tz          # senza fuso non si puo' collocare nella finestra
    return d.astimezone(timezone.utc).timestamp(), tz


def iso_bound(s):
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        sys.exit(f"--from/--to senza fuso orario: {s}")
    return d.astimezone(timezone.utc).timestamp()


def write(name, header, rows):
    with (OUT / name).open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    print(f"scritto data/derived/{name}")


def main():
    A = parse_args()
    t0, t1 = iso_bound(A.t0), iso_bound(A.t1)
    key = os.urandom(32)
    anon = lambda ip: hmac.new(key, str(ip).encode(), hashlib.sha256).digest()

    ev = defaultdict(list)                  # client -> [(t, url)]         C3
    ccls = defaultdict(Counter)             # client -> classi delle richieste
    conns = defaultdict(list)               # (client, conn) -> [(n, url)]   C5
    conn_meta = {}
    clients = set()                         # client delle righe di C5/C6 (come honeypot_scope)
    signed = defaultdict(Counter)           # classe -> {True/False}        C6
    tzs, tzs_in = Counter(), Counter()
    n_lines = n_skip = n_nots = n_out = n_in = 0
    first = last = None

    print(f"lettura di {A.logs} ...", file=sys.stderr)
    for r in lines(A.logs):
        n_lines += 1
        # C3: stessa selezione e stessi campi di honeypot_window.py (r.get di u, ip, ua, t;
        # secondi interi come epoch(), che scartava le frazioni), ma in UTC
        wu, wip, wts = r.get("u"), r.get("ip"), r.get("t")
        if wu and wip and wts:
            we, _ = to_utc(wts)
            if we is not None and t0 <= we < t1:
                wc = anon(wip)
                ev[wc].append((math.floor(we), wu))
                ccls[wc][classify(r.get("ua", ""))] += 1
        path = field(r, "u", "request_uri", "uri", "path", "request", "url")
        ip = field(r, "ip", "remote_addr", "client_ip", "addr")
        ua = field(r, "ua", "http_user_agent", "user_agent", "agent") or ""
        cid = field(r, "conn", "connection", "conn_id", "connection_id", "tcp_conn")
        cnum = field(r, "conn_req", "connection_requests", "req_num")
        ts = field(r, "t", "time_iso8601", "time", "timestamp", "@timestamp")
        sig = field(r, "sig_agent") or field(r, "sig_input")
        if not path or not ip:
            n_skip += 1
            continue
        if isinstance(path, str) and " " in path:
            parts = path.split()
            path = parts[1] if len(parts) > 2 else path
        if not ts:
            n_nots += 1
            continue
        e, tz = to_utc(ts)
        tzs[tz] += 1
        if e is None:
            n_nots += 1
            continue
        if not (t0 <= e < t1):
            n_out += 1
            continue
        n_in += 1
        tzs_in[tz] += 1
        first = e if first is None or e < first else first
        last = e if last is None or e > last else last
        cl = classify(ua)
        c = anon(ip)
        clients.add(c)
        signed[cl][bool(sig)] += 1
        if cid is not None:
            k = (c, str(cid))
            conns[k].append((int(cnum) if str(cnum).isdigit() else len(conns[k]), path))
            conn_meta[k] = cl

    del key
    iso = lambda e: datetime.fromtimestamp(e, timezone.utc).isoformat() if e else ""
    print(f"\nrighe JSON lette {n_lines:,}; scartate senza url o ip {n_skip:,}; "
          f"senza timestamp valido {n_nots:,}; fuori finestra {n_out:,}; nella finestra {n_in:,}")
    print(f"prima e ultima richiesta nella finestra (UTC): {iso(first)} -> {iso(last)}")
    print("fusi orari nei timestamp (tutte le righe con timestamp):")
    for tz, n in tzs.most_common():
        print(f"  {tz:10s} {n:,}   (nella finestra: {tzs_in.get(tz, 0):,})")

    # ---- C3 -------------------------------------------------------------------------
    W = A.window
    peak = defaultdict(list)
    for c, e in ev.items():
        if len(e) < A.min_req:
            continue
        e.sort()
        dq, seen, best = deque(), Counter(), 0
        for t, u in e:
            dq.append((t, u)); seen[u] += 1
            while dq and dq[0][0] < t - W:
                _, ou = dq.popleft(); seen[ou] -= 1
                if seen[ou] == 0:
                    del seen[ou]
            best = max(best, len(seen))
        peak[ccls[c].most_common(1)[0][0]].append(best)
    rows = []
    print(f"\nC3 — URL distinti al picco in {W} s, client con almeno {A.min_req} richieste")
    for cl in CLS:
        P = peak.get(cl)
        if not P:
            continue
        row = [cl, len(P), pct(P, .5), f"{sum(P) / len(P):.1f}", pct(P, .9), max(P)]
        rows.append(row)
        print("  {:10s} client {:>6,}  mediana {:>5}  media {:>7}  p90 {:>5}  max {:>5}".format(*row))
    write("honeypot_window.csv", ["class", "clients", "median", "mean", "p90", "max"], rows)

    # ---- C5 -------------------------------------------------------------------------
    adj = defaultdict(lambda: [0, 0, 0])
    conn_with_pairs, cli_with_pairs = Counter(), defaultdict(set)
    conn_all = Counter(conn_meta.values())
    conn_multi = Counter(conn_meta[k] for k, v in conns.items() if len(v) >= 2)
    for k, v in conns.items():
        if len(v) < 2:
            continue
        seq = [bookchap(p) for _, p in sorted(v)]
        a = rp = t = 0
        for x, y in zip(seq, seq[1:]):
            if x is None or y is None:
                continue
            t += 1
            if x[0] == y[0]:
                if abs(y[1] - x[1]) == 1: a += 1
                if y[1] == x[1]:          rp += 1
        if t:
            s = adj[conn_meta[k]]; s[0] += a; s[1] += rp; s[2] += t
            conn_with_pairs[conn_meta[k]] += 1
            cli_with_pairs[conn_meta[k]].add(k[0])
    rows = []
    print("\nC5 — contiguita' (honeypot_scope.py sez. 4; denominatore = coppie)")
    for cl in CLS:
        s = adj.get(cl)
        if not s or not s[2]:
            continue
        row = [cl, s[2], s[0], s[1], f"{100 * s[0] / s[2]:.2f}", f"{100 * s[1] / s[2]:.2f}",
               conn_with_pairs[cl], len(cli_with_pairs[cl]), conn_multi[cl], conn_all[cl]]
        rows.append(row)
        print("  {:10s} coppie {:>7,}  contigue {:>6,}  ripetute {:>6,}  {:>6}%  {:>6}%  "
              "conn. con coppie {:>6,}  client {:>5,}  conn. >=2 rich. {:>6,}  conn. {:>7,}"
              .format(*row))
    write("honeypot_contiguity.csv",
          ["class", "pairs", "contiguous", "repeated", "contiguous_pct", "repeated_pct",
           "connections_with_pairs", "clients_with_pairs", "connections_2plus",
           "connections"], rows)

    # ---- C6 -------------------------------------------------------------------------
    rows = []
    print("\nC6 — richieste firmate (sig_agent o sig_input)")
    for cl in CLS:
        c = signed.get(cl)
        if not c:
            continue
        n = sum(c.values())
        rows.append([cl, c[True], n, f"{100 * c[True] / n:.2f}"])
    ts_ = sum(c[True] for c in signed.values()); tt = sum(sum(c.values()) for c in signed.values())
    rows.append(["total", ts_, tt, f"{100 * ts_ / tt:.2f}" if tt else ""])
    for row in rows:
        print("  {:10s} firmate {:>8,}  totali {:>8,}  {:>6}%".format(*row))
    write("honeypot_signed.csv", ["class", "signed", "requests", "signed_pct"], rows)

    # ---- totali ---------------------------------------------------------------------
    rows = [["window_from_utc", iso(t0)], ["window_to_utc_excluded", iso(t1)],
            ["first_request_utc", iso(first)], ["last_request_utc", iso(last)],
            ["requests", n_in], ["clients", len(clients)], ["clients_c3", len(ev)], ["connections", len(conns)],
            ["lines_read", n_lines], ["lines_without_url_or_ip", n_skip],
            ["lines_without_valid_timestamp", n_nots], ["lines_outside_window", n_out],
            ["window_s", W], ["min_requests_per_client", A.min_req]]
    for cl in CLS:
        rows.append([f"requests_{cl}", sum(signed[cl].values())])
    print(f"\ntotali: richieste {n_in:,}  client {len(clients):,}  connessioni {len(conns):,}")
    write("honeypot_totals.csv", ["quantity", "value"], rows)


if __name__ == "__main__":
    main()
