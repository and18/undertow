# Minimal Varnish exporter, built on the Varnish image because it must
# invoke varnishstat and see the same working directory as varnishd
# (mounted as a shared volume).

FROM varnish:7.5
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*
COPY exporter.py /usr/local/bin/exporter.py
ENTRYPOINT ["python3", "/usr/local/bin/exporter.py"]