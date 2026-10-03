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

# A single process, N threads: the limited resource is the thread pool,
# analogous to a WebLogic Work Manager. THREADS and BACKLOG are sweep
# variables passed from the environment.
#
# --backlog is the depth of the socket queue: requests that find no free
# thread queue up here. Once the backlog is exceeded, the kernel refuses
# the connection — and that is where the curve collapses.
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