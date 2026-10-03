"""
app.py - Application of the system under test.

Models a text archive with two kinds of endpoint:

  CACHEABLE      indexes and chapters, served with explicit Cache-Control.
                 This is the case studied by Zhang et al. (SoCC 2025).

  NON-CACHEABLE  full-text search, which hits the database on every
                 request. This is the case nobody has measured, and where
                 the collapse is faster because the cache can absorb
                 nothing.

The limited resource is the gunicorn thread pool (gthread worker,
single process): conceptually identical to a WebLogic Work Manager.
When the threads run out, requests queue in the socket backlog, and
the latency stops degrading linearly.

Metrics exposed on /metrics for scraping.
"""

import os
import threading
import time
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool as pgpool
from flask import Flask, Response, abort, jsonify, request
from prometheus_client import (
    CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest,
)

# OBJECT_TTL, if set, takes precedence: it is the experiment's
# variable on expiry. The Gutenberg corpus never changes, so with a
# long TTL an object lives until it is evicted and we measure the upper
# bound of reuse. On a real site the useful life is min(residency, TTL),
# and the class with the longest return interval is the first to lose
# the benefit.
CACHE_TTL = int(os.environ.get("OBJECT_TTL") or os.environ.get("CACHE_TTL") or 3600)
DB_POOL_MIN = int(os.environ.get("DB_POOL_MIN", "2"))
DB_POOL_MAX = int(os.environ.get("DB_POOL_MAX", "16"))

# ------------------------------------------------------ per-class budget --

BUDGET_LOW = int(os.environ.get("BUDGET_LOW", "0"))
# Zero wait, and the reason is structural.
#
# The semaphore is acquired by before_request, which already runs on a
# gunicorn thread. A request that WAITS for a slot keeps that thread
# busy while it waits: with BUDGET_WAIT=0.5 the 2026-08-23 campaign
# measured a monotonic worsening, up to 6.4 times the reference with
# budget=1. The mechanism added latency without freeing anything.
#
# With zero wait, the request either gets a slot at once or immediately
# receives 503 with Retry-After, and the thread is free again in
# microseconds. Only this way does the batch class occupy at most
# BUDGET_LOW threads and the interactive class keep THREADS minus
# BUDGET_LOW guaranteed.
BUDGET_WAIT = float(os.environ.get("BUDGET_WAIT", "0"))

# Admission by identity: the classes listed here receive 403 BEFORE any
# work — no query, no pool slot, no object inserted in
# cache. It is the policy the industry is adopting (Cloudflare, default
# of 15 September 2026), brought to the origin instead of the edge.
#
# Empty = no block, i.e. the pre-existing behaviour. The names
# are those the application assigns to request._cls, not the user
# agents: read them from ut_requests_inflight_class before using them.
#
# LIMIT TO DECLARE: the block is at the origin, so a request
# of the blocked class that finds the object in cache is served
# by Varnish anyway. On the origin load the effect is identical to
# a block at the edge (a hit does not reach the origin in any case);
# it differs only in how many requests the client sees satisfied.
BLOCK_CLASSES = {c.strip() for c in
                 os.environ.get("BLOCK_CLASSES", "").split(",")
                 if c.strip()}

_low_sem = (threading.BoundedSemaphore(BUDGET_LOW)
            if BUDGET_LOW > 0 else None)

# Fixed set of search terms. The cost of a full-text search
# depends on how many chapters contain the term — 83 ms for "whale",
# 1330 ms for "night" — so a freely chosen term would make
# the query cost an uncontrolled variable of the workload. With a
# fixed set, sampled identically by the two profiles, the average cost
# per request is a known constant of the experiment.
# The terms must be chosen by measuring them on the corpus: see tools/pick_terms.py.
SEARCH_TERMS = []  # populated from profiles/search-terms.txt

app = Flask(__name__)

# --------------------------------------------------------------- metrics --

REQ = Counter("ut_requests_total", "Requests served",
              ["endpoint", "status", "cacheable"])
LAT = Histogram("ut_request_seconds", "Application-side latency",
                ["endpoint", "cacheable"],
                buckets=(.001, .005, .01, .025, .05, .1, .25, .5,
                         1, 2.5, 5, 10, 30, 60))
INFLIGHT = Gauge("ut_requests_inflight", "Requests being processed")
INFLIGHT_CLS = Gauge("ut_requests_inflight_class", "In flight per class", ["cls"])
BUDGET_ADMITTED = Counter("ut_budget_admitted_total", "Admitted", ["cls"])
BUDGET_SHED = Counter("ut_budget_shed_total", "Rejected by budget", ["cls"])
BLOCKED = Counter("ut_blocked_total", "Requests rejected per class",
                  ["cls"])
BUDGET_WAITED = Histogram("ut_budget_wait_seconds", "Wait for a slot",
                          buckets=(.001, .01, .05, .1, .25, .5, 1, 2))
DBWAIT = Histogram("ut_db_pool_wait_seconds", "Wait for a DB connection",
                   buckets=(.0001, .001, .005, .01, .05, .1, .5, 1, 5, 10))
DBBUSY = Gauge("ut_db_pool_busy", "DB connections in use")
DBEXHAUSTED = Counter("ut_db_pool_exhausted_total",
                      "Failed attempts to obtain a connection")
POOLCFG = Gauge("ut_pool_config", "Configuration parameters", ["param"])

# ------------------------------------------------------------- DB pool --

_pool = None
_busy = 0


def get_pool():
    global _pool
    if _pool is None:
        _pool = pgpool.ThreadedConnectionPool(
            DB_POOL_MIN, DB_POOL_MAX,
            host=os.environ.get("PGHOST", "db"),
            port=os.environ.get("PGPORT", "5432"),
            dbname=os.environ.get("PGDATABASE", "undertow"),
            user=os.environ.get("PGUSER", "undertow"),
            password=os.environ["PGPASSWORD"],
        )
    return _pool


@contextmanager
def db():
    """Connection from the pool, measuring the wait time.

    The wait time is the key metric: it grows from zero to macroscopic
    values the moment the pool is exhausted, and it is the
    second link in the saturation chain.
    """
    global _busy
    t0 = time.perf_counter()
    conn = None
    try:
        conn = get_pool().getconn()
    except pgpool.PoolError:
        DBEXHAUSTED.inc()
        raise
    finally:
        DBWAIT.observe(time.perf_counter() - t0)

    _busy += 1
    DBBUSY.set(_busy)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _busy -= 1
        DBBUSY.set(_busy)
        get_pool().putconn(conn)


def query(sql, args=(), one=False):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            if cur.description is None:
                return None
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
    out = [dict(zip(cols, r)) for r in rows]
    return (out[0] if out else None) if one else out


# ------------------------------------------------------------ middleware --

def request_class():
    """Classify the request for the test bench."""
    ua = request.headers.get("User-Agent", "")
    # Three classes, not two. The agentic profile has existed in workload.js
    # since 9 September, but the application did not distinguish it: it ended up in "high"
    # together with human traffic, so it was neither observable nor
    # governable separately. It is needed for the policy that blocks
    # training and agent while letting search through, i.e. the
    # Cloudflare default since 15 September 2026.
    if "lowloc" in ua:
        return "low"
    if "undertow-agent" in ua:
        return "agent"
    return "high"


@app.before_request
def _start():
    request._t0 = time.perf_counter()
    request._cls = request_class()
    request._slot = False
    INFLIGHT.inc()
    INFLIGHT_CLS.labels(request._cls).inc()

    # Before the semaphore and before any query: a blocked request
    # must not consume work at the origin.
    if request._cls in BLOCK_CLASSES:
        BLOCKED.labels(request._cls).inc()
        abort(403)

    if _low_sem is not None and request._cls == "low":
        t = time.perf_counter()
        got = (_low_sem.acquire(timeout=BUDGET_WAIT) if BUDGET_WAIT > 0
               else _low_sem.acquire(blocking=False))
        BUDGET_WAITED.observe(time.perf_counter() - t)
        if not got:
            BUDGET_SHED.labels("low").inc()
            abort(503)
        request._slot = True
        BUDGET_ADMITTED.labels("low").inc()


@app.teardown_request
def _release(exc=None):
    if getattr(request, "_slot", False):
        _low_sem.release()
        request._slot = False


@app.after_request
def _end(resp):
    INFLIGHT.dec()
    INFLIGHT_CLS.labels(getattr(request, "_cls", "?")).dec()
    ep = request.endpoint or "unknown"
    cacheable = resp.headers.get("X-UT-Cacheable", "0")
    LAT.labels(ep, cacheable).observe(time.perf_counter() - request._t0)
    REQ.labels(ep, str(resp.status_code), cacheable).inc()
    return resp


@app.errorhandler(403)
def _blocked(e):
    return uncacheable(jsonify(error="class blocked")), 403


@app.errorhandler(503)
def _shed(e):
    r = jsonify(error="capacity budget", retry_after=2)
    r.status_code = 503
    r.headers["Retry-After"] = "2"
    r.headers["X-UT-Cacheable"] = "0"
    return r


def cacheable(resp, ttl=None):
    resp.headers["Cache-Control"] = f"public, max-age={ttl or CACHE_TTL}"
    resp.headers["X-UT-Cacheable"] = "1"
    return resp


def uncacheable(resp):
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-UT-Cacheable"] = "0"
    return resp


# ------------------------------------------------------------- endpoints --

@app.get("/health")
def health():
    """Trivial endpoint: no DB access.

    Used by the null test, which must verify that the load generator
    holds a multiple of the test rate without the target being the
    limit. If /health also degrades, the problem is elsewhere.
    """
    return uncacheable(jsonify(ok=True))


@app.get("/")
def index():
    stats = query(
        "SELECT (SELECT count(*) FROM books) AS books,"
        "       (SELECT count(*) FROM chapters) AS chapters", one=True)
    return cacheable(jsonify(stats))


@app.get("/library")
def library():
    rows = query("SELECT id, title, author, n_chapters FROM books"
                 " ORDER BY title")
    return cacheable(jsonify(rows))


@app.get("/book/<int:book_id>")
def book(book_id):
    b = query("SELECT id, title, author, n_chapters FROM books"
              " WHERE id = %s", (book_id,), one=True)
    if not b:
        return uncacheable(jsonify(error="not found")), 404
    b["chapters"] = query(
        "SELECT n, title, words FROM chapters WHERE book_id = %s ORDER BY n",
        (book_id,))
    return cacheable(jsonify(b))


@app.get("/book/<int:book_id>/ch/<int:n>")
def chapter(book_id, n):
    """Chapter: cacheable, in the long tail.

    It does what a real page does: content, book metadata,
    index for navigation, outgoing links. A single primary-key lookup
    would cost ~5 ms, and at that cost the thread pool would not
    fill up at any traffic composition: the experiment could not
    produce the phenomenon it must measure. The cost here is not
    artificially inflated, it is that of a real application page.
    """
    row = query(
        "SELECT book_id, n, title, body FROM chapters"
        " WHERE book_id = %s AND n = %s", (book_id, n), one=True)
    if not row:
        return uncacheable(jsonify(error="not found")), 404

    row["book"] = query(
        "SELECT id, title, author, n_chapters FROM books WHERE id = %s",
        (book_id,), one=True)
    row["toc"] = query(
        "SELECT n, title, words FROM chapters WHERE book_id = %s ORDER BY n",
        (book_id,))
    # Excerpts of the linked chapters. A cacheable page is expensive to
    # generate — that is why it is put in cache. Without this
    # work the chapter costs ~6 ms, and by Little's law the 16-thread pool
    # would saturate only beyond 2600 req/s at the origin: a rate
    # the GIL does not allow reaching. The experiment could not
    # produce the phenomenon it must measure.
    row["related"] = query(
        "SELECT c.book_id, c.n, c.title, b.title AS book_title,"
        "       left(c.body, 400) AS excerpt,"
        "       ts_headline('english', c.body,"
        "                   plainto_tsquery('english', %s),"
        "                   'MaxFragments=1, MaxWords=30') AS preview "
        "FROM links l"
        "  JOIN chapters c ON c.book_id = l.dst_book AND c.n = l.dst_n"
        "  JOIN books b ON b.id = c.book_id "
        "WHERE l.src_book = %s AND l.src_n = %s",
        (row["title"], book_id, n))
    resp = cacheable(row and jsonify(row))
    # TTL as an experiment variable. The Gutenberg corpus never changes,
    # so without this an object in cache lives until it is
    # evicted: we measure the upper bound of reuse. On a real site
    # the useful life is min(residency, TTL), and the class with the longest
    # return interval is the first to lose the benefit.
    ttl = int(os.environ.get("OBJECT_TTL", "0"))
    if ttl > 0:
        resp.headers["Cache-Control"] = f"public, max-age={ttl}"
    else:
        resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.get("/search")
def search():
    """Full-text search: NOT cacheable, expensive.

    No cache can absorb it. It is the case absent from existing
    work and the one where saturation arrives first.
    """
    q = (request.args.get("q") or "").strip()
    if not q:
        return uncacheable(jsonify(error="q required")), 400
    rows = query(
        # ts_headline must be applied AFTER the LIMIT, not before. Computed
        # on the whole set of matches, the cost depends on how many
        # chapters contain the term: 77 ms for "whale", 2075 ms for
        # "love". The query cost would become an uncontrolled
        # variable of the workload. With the subquery, the snippets are
        # generated on exactly 25 rows whatever the term.
        "SELECT book_id, n, title, rank,"
        "       ts_headline('english', body, plainto_tsquery('english', %s),"
        "                   'MaxFragments=3, MaxWords=40') AS snippet "
        "FROM ("
        "  SELECT book_id, n, title, body,"
        "         ts_rank(tsv, plainto_tsquery('english', %s)) AS rank "
        "  FROM chapters WHERE tsv @@ plainto_tsquery('english', %s) "
        "  ORDER BY rank DESC LIMIT 25"
        ") t", (q, q, q))
    return uncacheable(jsonify(query=q, results=rows))


@app.get("/links/<int:book_id>/<int:n>")
def links(book_id, n):
    """Outgoing links from a chapter: feeds the agentic traversal."""
    rows = query(
        "SELECT dst_book, dst_n FROM links WHERE src_book = %s AND src_n = %s",
        (book_id, n))
    return cacheable(jsonify(rows))


# The metrics must NOT go through the application's thread pool:
# when the pool saturates, the scrape would queue up and the instrumentation
# would switch off at exactly the moment we want to measure. start_http_server
# opens a socket and a thread of its own, independent of gunicorn.
from prometheus_client import start_http_server

def _init_metrics():
    POOLCFG.labels("threads").set(int(os.environ.get("THREADS", "32")))
    POOLCFG.labels("backlog").set(int(os.environ.get("BACKLOG", "256")))
    POOLCFG.labels("db_pool_max").set(DB_POOL_MAX)
    start_http_server(9000)

_init_metrics()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)