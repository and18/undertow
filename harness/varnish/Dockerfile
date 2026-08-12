# L'exporter di Varnish non ha un'immagine pubblica: si costruisce.
# Deve stare sulla stessa immagine di Varnish perche' invoca varnishstat,
# e condividere la working directory con varnishd.

FROM golang:1.22-alpine AS build
RUN apk add --no-cache git
RUN go install github.com/jonnenauha/prometheus_varnish_exporter@v1.6.1

FROM varnish:7.5
USER root
COPY --from=build /go/bin/prometheus_varnish_exporter /usr/local/bin/
ENTRYPOINT ["/usr/local/bin/prometheus_varnish_exporter"]