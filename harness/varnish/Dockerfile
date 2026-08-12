# Exporter minimale per Varnish, costruito sull'immagine di Varnish
# perche' deve invocare varnishstat e vedere la stessa working directory
# di varnishd (montata come volume condiviso).

FROM varnish:7.5
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*
COPY exporter.py /usr/local/bin/exporter.py
ENTRYPOINT ["python3", "/usr/local/bin/exporter.py"]