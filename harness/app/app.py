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
import threading
import time
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool as pgpool
from flask import Flask, Response, abort, jsonify, request
from prometheus_client import (
    CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest,
)

# OBJECT_TTL, se impostato, ha precedenza: e' la variabile
# dell'esperimento sulla scadenza. Il corpus Gutenberg non cambia mai,
# quindi con un TTL lungo un oggetto vive finche' non viene sfrattato e
# misuriamo il limite superiore del riuso. Su un sito reale la vita
# utile e' min(residenza, TTL), e la classe con l'intervallo di ritorno
# piu' lungo e' la prima a perdere il beneficio.
CACHE_TTL = int(os.environ.get("OBJECT_TTL") or os.environ.get("CACHE_TTL") or 3600)
DB_POOL_MIN = int(os.environ.get("DB_POOL_MIN", "2"))
DB_POOL_MAX = int(os.environ.get("DB_POOL_MAX", "16"))

# ------------------------------------------------------ budget per classe --

BUDGET_LOW = int(os.environ.get("BUDGET_LOW", "0"))
# Attesa zero, e la ragione e' strutturale.
#
# Il semaforo viene acquisito da before_request, che gira gia' su un
# thread di gunicorn. Una richiesta che ATTENDE uno slot tiene occupato
# quel thread mentre aspetta: con BUDGET_WAIT=0.5 la campagna del
# 2026-08-23 ha misurato un peggioramento monotono, fino a 6,4 volte il
# riferimento con budget=1. Il meccanismo aggiungeva latenza senza
# liberare nulla.
#
# Con attesa zero, la richiesta o ottiene subito uno slot o riceve subito
# 503 con Retry-After, e il thread torna libero in microsecondi. Solo
# cosi' la classe batch occupa al massimo BUDGET_LOW thread e alla classe
# interattiva ne restano garantiti THREADS meno BUDGET_LOW.
BUDGET_WAIT = float(os.environ.get("BUDGET_WAIT", "0"))

# Ammissione per identita': le classi elencate qui ricevono 403 PRIMA
# di qualunque lavoro — nessuna query, nessuno slot di pool, nessun
# oggetto inserito in cache. E' la politica che l'industria sta
# adottando (Cloudflare, default del 15 settembre 2026), portata
# all'origine invece che al bordo.
#
# Vuoto = nessun blocco, cioe' il comportamento preesistente. I nomi
# sono quelli che l'applicazione assegna a request._cls, non gli user
# agent: vanno letti da ut_requests_inflight_class prima di usarli.
#
# LIMITE DA DICHIARARE: il blocco e' all'origine, quindi una richiesta
# della classe bloccata che trova l'oggetto in cache viene comunque
# servita da Varnish. Sul carico all'origine l'effetto e' identico a
# un blocco al bordo (un hit non raggiunge l'origine in nessun caso);
# differisce solo su quante richieste il client vede soddisfatte.
BLOCK_CLASSES = {c.strip() for c in
                 os.environ.get("BLOCK_CLASSES", "").split(",")
                 if c.strip()}

_low_sem = (threading.BoundedSemaphore(BUDGET_LOW)
            if BUDGET_LOW > 0 else None)

# Insieme fisso di termini di ricerca. Il costo di una ricerca full-text
# dipende da quanti capitoli contengono il termine — 83 ms per "whale",
# 1330 ms per "night" — quindi un termine scelto liberamente renderebbe
# il costo della query una variabile non controllata del workload. Con un
# insieme fisso, campionato in modo identico dai due profili, il costo
# medio per richiesta e' una costante nota dell'esperimento.
# I termini vanno scelti misurandoli sul corpus: vedi tools/pick_terms.py.
SEARCH_TERMS = []  # popolato da profiles/search-terms.txt

app = Flask(__name__)

# --------------------------------------------------------------- metriche --

REQ = Counter("ut_requests_total", "Richieste servite",
              ["endpoint", "status", "cacheable"])
LAT = Histogram("ut_request_seconds", "Latenza lato applicazione",
                ["endpoint", "cacheable"],
                buckets=(.001, .005, .01, .025, .05, .1, .25, .5,
                         1, 2.5, 5, 10, 30, 60))
INFLIGHT = Gauge("ut_requests_inflight", "Richieste in elaborazione")
INFLIGHT_CLS = Gauge("ut_requests_inflight_class", "In volo per classe", ["cls"])
BUDGET_ADMITTED = Counter("ut_budget_admitted_total", "Amesse", ["cls"])
BUDGET_SHED = Counter("ut_budget_shed_total", "Rifiutate per budget", ["cls"])
BLOCKED = Counter("ut_blocked_total", "Richieste rifiutate per classe",
                  ["cls"])
BUDGET_WAITED = Histogram("ut_budget_wait_seconds", "Attesa per uno slot",
                          buckets=(.001, .01, .05, .1, .25, .5, 1, 2))
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
            password=os.environ["PGPASSWORD"],
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

def request_class():
    """Classifica la richiesta per il banco prova."""
    ua = request.headers.get("User-Agent", "")
    # Tre classi, non due. Il profilo agentico esiste in workload.js dal
    # 9 settembre, ma l'applicazione non lo distingueva: finiva in "high"
    # insieme al traffico umano, quindi non era ne' osservabile ne'
    # governabile separatamente. Serve per la politica che blocca
    # training e agent lasciando passare search, cioe' il default
    # Cloudflare dal 15 settembre 2026.
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

    # Prima del semaforo e prima di ogni query: una richiesta bloccata
    # non deve consumare lavoro all'origine.
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
    """Capitolo: cacheable, nella coda lunga.

    Fa quello che fa una pagina reale: contenuto, metadati del libro,
    indice per la navigazione, link uscenti. Una singola lookup su chiave
    primaria costerebbe ~5 ms, e a quel costo il pool di thread non si
    riempirebbe a nessuna composizione del traffico: l'esperimento non
    potrebbe produrre il fenomeno che deve misurare. Il costo qui non e'
    gonfiato artificialmente, e' quello di una pagina applicativa vera.
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
    # Estratti dei capitoli collegati. Una pagina cacheable e' costosa da
    # generare — e' per questo che la si mette in cache. Senza questo
    # lavoro il capitolo costa ~6 ms, e per la legge di Little il pool da
    # 16 thread saturerebbe solo oltre 2600 req/s all'origine: un ritmo
    # che il GIL non lascia raggiungere. L'esperimento non potrebbe
    # produrre il fenomeno che deve misurare.
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
    # TTL come variabile d'esperimento. Il corpus Gutenberg non cambia mai,
    # quindi senza questo un oggetto in cache vive finche' non viene
    # sfrattato: misuriamo il limite superiore del riuso. Su un sito reale
    # la vita utile e' min(residenza, TTL), e la classe con l'intervallo di
    # ritorno piu' lungo e' la prima a perdere il beneficio.
    ttl = int(os.environ.get("OBJECT_TTL", "0"))
    if ttl > 0:
        resp.headers["Cache-Control"] = f"public, max-age={ttl}"
    else:
        resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


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