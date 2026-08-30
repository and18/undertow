vcl 4.1;

# Configurazione volutamente minima.
#
# Ogni euristica aggiunta qui e' una variabile che andrebbe giustificata
# nella metodologia. Il comportamento della cache deve dipendere SOLO
# dagli header Cache-Control emessi dall'applicazione, cosi' che la
# distinzione fra cacheable e non cacheable sia una proprieta' del
# workload e non della configurazione.

backend default {
    .host = "${VARNISH_BACKEND_HOST}";
    .port = "${VARNISH_BACKEND_PORT}";
    .connect_timeout = 5s;
    .first_byte_timeout = 120s;
    .between_bytes_timeout = 30s;
    # Il pool di connessioni verso l'origine e' esso stesso una risorsa
    # limitata: alzarlo troppo maschera la saturazione a valle.
    .max_connections = 200;
}

sub vcl_recv {
    # Nessuna normalizzazione della chiave di cache: un URL diverso e'
    # un oggetto diverso, che e' precisamente cio' che rende il traffico
    # agentico distruttivo per la cache.
    if (req.method != "GET" && req.method != "HEAD") {
        return (pass);
    }
    return (hash);
}

sub vcl_backend_response {
    # TTL e sfratto derivano da Cache-Control dell'applicazione.
    # Nessun default nascosto.
    if (beresp.http.Cache-Control ~ "no-store") {
        set beresp.uncacheable = true;
        set beresp.ttl = 0s;
        return (deliver);
    }
    # Nessun grace, nessun keep: si vuole misurare il miss vero, non
    # una risposta stantia che lo maschererebbe.
    set beresp.grace = 0s;
    set beresp.keep = 0s;
    return (deliver);
}

sub vcl_deliver {
    # Header diagnostico: permette al generatore di carico di
    # registrare hit e miss per singola richiesta, non solo in
    # aggregato dalle statistiche di Varnish.
    if (obj.hits > 0) {
        set resp.http.X-Cache = "HIT";
    } else {
        set resp.http.X-Cache = "MISS";
    }
    set resp.http.X-Cache-Hits = obj.hits;
    return (deliver);
}
