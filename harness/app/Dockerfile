FROM python:3.12-slim

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y gcc libpq-dev && apt-get autoremove -y

COPY app.py load_corpus.py ./

EXPOSE 8000

# Un solo processo, N thread: la risorsa limitata e' il pool di thread,
# analogo a un Work Manager WebLogic. THREADS e BACKLOG sono variabili
# di sweep passate dall'ambiente.
#
# --backlog e' la profondita' della coda del socket: le richieste che non
# trovano un thread libero si accodano qui. Superato il backlog, il kernel
# rifiuta la connessione — ed e' li' che la curva precipita.
CMD gunicorn \
      --bind 0.0.0.0:8000 \
      --worker-class gthread \
      --workers 1 \
      --threads ${THREADS:-32} \
      --backlog ${BACKLOG:-256} \
      --timeout 120 \
      --graceful-timeout 5 \
      --access-logfile - \
      --access-logformat '%(t)s %(s)s %(D)s %(U)s' \
      app:app