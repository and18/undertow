#!/usr/bin/env python3
"""
honeypot_aggregate.py — all the honeypot aggregates used in the paper, over a fixed time
window [--from, --to) in UTC (claim C3, C5, C6; FIG-A3).

WHY
  honeypot_scope.py and honeypot_window.py read everything they find in the log folder:
  with rotation, the period changes at every launch. This script fixes the window and
  recomputes the same aggregates with the same logic, so that the paper's numbers can be
  obtained again from a snapshot of the logs.

REUSED LOGIC (identical, except the time filter)
  classify(), bookchap(), field(), pct() from honeypot_scope.py; sliding window from
  honeypot_window.py.
  C3  for each client with at least --min-req requests in the paper's window: maximum of distinct
      URLs in a sliding window of --window s (143 = T_C of the testbed); client class =
      most frequent class of its requests. Per class: clients, median, mean,
      p90, max (pct: index int(q*n) on the sorted values, as in the original scripts).
  C5  honeypot_scope.py, section 4: for each connection (client, conn) with at least 2
      requests, ordered by conn_req, consecutive pairs that map to (book,
      chapter); contiguous = same book and |Δchapter| = 1, repeated = same book and same
      chapter. Connection class = class of the last request read (conn_meta).
      The denominator is PAIRS. Also reported are the connections that contribute
      at least one pair, the distinct clients of those connections and all the connections
      of the class.
  C6  honeypot_scope.py, section 6: signed request if sig_agent or sig_input is present and
      non-empty; signed / total per request class.
  Totals: requests in the window, clients, connections; discarded and out-of-window lines.

DIFFERENCES FROM THE ORIGINAL SCRIPTS (only these)
  1. Filter on the window [--from, --to) in UTC.
  2. honeypot_window.epoch() ignored the time zone of the timestamp; here the timestamp is read
     with its offset and converted to UTC, then truncated to the second as epoch(). The time zones
     found are printed: if they are all +00:00, the difference is nil.
  3. Consequence of the filter: for C5/C6 the lines without a valid timestamp, which
     honeypot_scope.py counted, are excluded here because they cannot be placed in the window;
     their number is printed and written in the totals (lines_without_valid_timestamp).
  Row selection: C3 exactly as honeypot_window.py (fields u, ip, ua, t read
  with r.get, row kept if u, ip and t are not empty); C5/C6 and totals exactly as
  honeypot_scope.py (field() with the alternative names, row kept if url and ip are there,
  «GET /x HTTP/1.1» reduced to the path).

PRIVACY
  The IP is used only as an in-memory grouping key, through an HMAC with a random key
  new at every launch: no IP, no hash, no log row is printed or
  written. The CSVs hold only counts and quantiles per class.

WRITES (data/derived/)
  honeypot_totals.csv        quantity, value
  honeypot_window.csv        class, clients, median, mean, p90, max         (C3)
  honeypot_contiguity.csv    class, pairs, contiguous, repeated, shares,
                             connections with pairs, clients, connections   (C5)
  honeypot_signed.csv        class, signed, total, share                    (C6)

Usage:
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
    ap.add_argument("--logs", required=True, help="folder of the log snapshot")
    ap.add_argument("--from", dest="t0", required=True, help="start, ISO 8601 with time zone")
    ap.add_argument("--to", dest="t1", required=True, help="end excluded, ISO 8601 with time zone")
    ap.add_argument("--window", type=int, default=143, help="seconds; 143 = T_C of the testbed")
    ap.add_argument("--min-req", type=int, default=5, help="as the original scripts")
    return ap.parse_args()


# ---- from honeypot_scope.py, unchanged ------------------------------------------------
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
            print(f"  (skipping {os.path.basename(f)}: {type(e).__name__})", file=sys.stderr)


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
    """ISO 8601 timestamp -> (UTC seconds, time zone as written in the log)."""
    s = str(ts).strip()
    m = re.search(r"(Z|[+-]\d{2}:?\d{2})$", s)
    tz = m.group(1) if m else "(none)"
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None, tz
    if d.tzinfo is None:
        return None, tz          # without a time zone it cannot be placed in the window
    return d.astimezone(timezone.utc).timestamp(), tz


def iso_bound(s):
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        sys.exit(f"--from/--to without a time zone: {s}")
    return d.astimezone(timezone.utc).timestamp()


def write(name, header, rows):
    with (OUT / name).open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    print(f"written data/derived/{name}")


def main():
    A = parse_args()
    t0, t1 = iso_bound(A.t0), iso_bound(A.t1)
    key = os.urandom(32)
    anon = lambda ip: hmac.new(key, str(ip).encode(), hashlib.sha256).digest()

    ev = defaultdict(list)                  # client -> [(t, url)]         C3
    ccls = defaultdict(Counter)             # client -> classes of the requests
    conns = defaultdict(list)               # (client, conn) -> [(n, url)]   C5
    conn_meta = {}
    clients = set()                         # clients of the C5/C6 rows (as honeypot_scope)
    signed = defaultdict(Counter)           # class -> {True/False}        C6
    tzs, tzs_in = Counter(), Counter()
    n_lines = n_skip = n_nots = n_out = n_in = 0
    first = last = None

    print(f"reading {A.logs} ...", file=sys.stderr)
    for r in lines(A.logs):
        n_lines += 1
        # C3: same selection and same fields as honeypot_window.py (r.get of u, ip, ua, t;
        # whole seconds as epoch(), which discarded the fractions), but in UTC
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
    print(f"\nJSON lines read {n_lines:,}; discarded without url or ip {n_skip:,}; "
          f"without valid timestamp {n_nots:,}; outside window {n_out:,}; in the window {n_in:,}")
    print(f"first and last request in the window (UTC): {iso(first)} -> {iso(last)}")
    print("time zones in the timestamps (all rows with a timestamp):")
    for tz, n in tzs.most_common():
        print(f"  {tz:10s} {n:,}   (in the window: {tzs_in.get(tz, 0):,})")

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
    print(f"\nC3 — distinct URLs at the peak in {W} s, clients with at least {A.min_req} requests")
    for cl in CLS:
        P = peak.get(cl)
        if not P:
            continue
        row = [cl, len(P), pct(P, .5), f"{sum(P) / len(P):.1f}", pct(P, .9), max(P)]
        rows.append(row)
        print("  {:10s} clients {:>6,}  median {:>5}  mean {:>7}  p90 {:>5}  max {:>5}".format(*row))
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
    print("\nC5 — contiguity (honeypot_scope.py sec. 4; denominator = pairs)")
    for cl in CLS:
        s = adj.get(cl)
        if not s or not s[2]:
            continue
        row = [cl, s[2], s[0], s[1], f"{100 * s[0] / s[2]:.2f}", f"{100 * s[1] / s[2]:.2f}",
               conn_with_pairs[cl], len(cli_with_pairs[cl]), conn_multi[cl], conn_all[cl]]
        rows.append(row)
        print("  {:10s} pairs {:>7,}  contiguous {:>6,}  repeated {:>6,}  {:>6}%  {:>6}%  "
              "conn. with pairs {:>6,}  clients {:>5,}  conn. >=2 req. {:>6,}  conn. {:>7,}"
              .format(*row))
    write("honeypot_contiguity.csv",
          ["class", "pairs", "contiguous", "repeated", "contiguous_pct", "repeated_pct",
           "connections_with_pairs", "clients_with_pairs", "connections_2plus",
           "connections"], rows)

    # ---- C6 -------------------------------------------------------------------------
    rows = []
    print("\nC6 — signed requests (sig_agent or sig_input)")
    for cl in CLS:
        c = signed.get(cl)
        if not c:
            continue
        n = sum(c.values())
        rows.append([cl, c[True], n, f"{100 * c[True] / n:.2f}"])
    ts_ = sum(c[True] for c in signed.values()); tt = sum(sum(c.values()) for c in signed.values())
    rows.append(["total", ts_, tt, f"{100 * ts_ / tt:.2f}" if tt else ""])
    for row in rows:
        print("  {:10s} signed {:>8,}  total {:>8,}  {:>6}%".format(*row))
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
    print(f"\ntotals: requests {n_in:,}  clients {len(clients):,}  connections {len(conns):,}")
    write("honeypot_totals.csv", ["quantity", "value"], rows)


if __name__ == "__main__":
    main()
