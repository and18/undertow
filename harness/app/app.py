"""
app.py - Applicazione del sistema sotto test.

Modella un archivio testuale con due nature di endpoint:

  CACHEABLE      indici e capitoli, serviti con Cache-Control esplicito.
                 E' il caso studiato da Zhang et al. (SoCC 2025).

  NON CACHEABLE  ricerca full-text, che colpisce il database a ogni
                 richiesta. E' il caso che nessuno ha misurato, e dove
                 il collasso e' piu' rapido perche' la cache non puo'
                 assorbire nulla.

La risorsa limitata e' il pool di thread di gunicorn (worker gthread,
processo singolo): concettualmente identico a un Work Manager WebLogic.
Quando i thread finiscono, le richieste si accodano nel backlog del
socket, e la latenza smette di degradare linearmente.

Metriche esposte su /metrics per lo scrape.
"""

import os
import time
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool as pgpool
from flask import Flask, Response, jsonify, request
from prometheus_client import (
    CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest,
)

CACHE_TTL = int(os.environ.get("CACHE_TTL", "3600"))
DB_POOL_MIN = int(os.environ.get("DB_POOL_MIN", "2"))
DB_POOL_MAX = int(os.environ.get("DB_POOL_MAX", "16"))

app = Flask(__name__)

# --------------------------------------------------------------- metriche --

REQ = Counter("ut_requests_total", "Richieste servite",
              ["endpoint", "status", "cacheable"])
LAT = Histogram("ut_request_seconds", "Latenza lato applicazione",
                ["endpoint", "cacheable"],
                buckets=(.001, .005, .01, .025, .05, .1, .25, .5,
                         1, 2.5, 5, 10, 30, 60))
INFLIGHT = Gauge("ut_requests_inflight", "Richieste in elaborazione")
DBWAIT = Histogram("ut_db_pool_wait_seconds", "Attesa per una connessione DB",
                   buckets=(.0001, .001, .005, .01, .05, .1, .5, 1, 5, 10))
DBBUSY = Gauge("ut_db_pool_busy", "Connessioni DB in uso")
DBEXHAUSTED = Counter("ut_db_pool_exhausted_total",
                      "Tentativi falliti di ottenere una connessione")
POOLCFG = Gauge("ut_pool_config", "Parametri di configurazione", ["param"])

# ------------------------------------------------------------- pool di DB --

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
            password=os.environ.get("PGPASSWORD", "undertow"),
        )
    return _pool


@contextmanager
def db():
    """Connessione dal pool, con misura del tempo di attesa.

    Il tempo di attesa e' la metrica chiave: cresce da zero a valori
    macroscopici nel momento in cui il pool si esaurisce, ed e' il
    secondo anello della catena di saturazione.
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

@app.before_request
def _start():
    request._t0 = time.perf_counter()
    INFLIGHT.inc()


@app.after_request
def _end(resp):
    INFLIGHT.dec()
    ep = request.endpoint or "unknown"
    cacheable = resp.headers.get("X-UT-Cacheable", "0")
    LAT.labels(ep, cacheable).observe(time.perf_counter() - request._t0)
    REQ.labels(ep, str(resp.status_code), cacheable).inc()
    return resp


def cacheable(resp, ttl=None):
    resp.headers["Cache-Control"] = f"public, max-age={ttl or CACHE_TTL}"
    resp.headers["X-UT-Cacheable"] = "1"
    return resp


def uncacheable(resp):
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-UT-Cacheable"] = "0"
    return resp


# ------------------------------------------------------------- endpoint  --

@app.get("/health")
def health():
    """Endpoint banale: nessun accesso al DB.

    Serve al test nullo, che deve verificare che il generatore di carico
    regga un multiplo del ritmo di prova senza che il bersaglio sia il
    limite. Se anche /health degrada, il problema e' altrove.
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
    """Capitolo: cacheable, ma nella coda lunga.

    E' l'endpoint che il traffico agentico colpisce e quello umano quasi
    mai: la cache si riempie di contenuti richiesti una volta sola,
    sfrattando quelli caldi.
    """
    row = query(
        "SELECT book_id, n, title, body FROM chapters"
        " WHERE book_id = %s AND n = %s", (book_id, n), one=True)
    if not row:
        return uncacheable(jsonify(error="not found")), 404
    return cacheable(jsonify(row))


@app.get("/search")
def search():
    """Ricerca full-text: NON cacheable, costosa.

    Nessuna cache puo' assorbirla. E' il caso assente dal lavoro
    esistente e quello dove la saturazione arriva prima.
    """
    q = (request.args.get("q") or "").strip()
    if not q:
        return uncacheable(jsonify(error="q required")), 400
    rows = query(
        # ts_headline va applicato DOPO il LIMIT, non prima. Calcolato
        # sull'intero insieme di corrispondenze, il costo dipende da quanti
        # capitoli contengono il termine: 77 ms per "whale", 2075 ms per
        # "love". Il costo della query diventerebbe una variabile non
        # controllata del workload. Con la sottoquery, gli snippet si
        # generano su esattamente 25 righe qualunque sia il termine.
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
    """Link uscenti da un capitolo: alimenta l'attraversamento agentico."""
    rows = query(
        "SELECT dst_book, dst_n FROM links WHERE src_book = %s AND src_n = %s",
        (book_id, n))
    return cacheable(jsonify(rows))


# Le metriche NON devono passare dal pool di thread dell'applicazione:
# quando il pool satura, lo scrape si accoderebbe e la strumentazione si
# spegnerebbe proprio nell'istante che si vuole misurare. start_http_server
# apre un socket e un thread propri, indipendenti da gunicorn.
from prometheus_client import start_http_server

def _init_metrics():
    POOLCFG.labels("threads").set(int(os.environ.get("THREADS", "32")))
    POOLCFG.labels("backlog").set(int(os.environ.get("BACKLOG", "256")))
    POOLCFG.labels("db_pool_max").set(DB_POOL_MAX)
    start_http_server(9000)

_init_metrics()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)