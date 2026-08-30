# Instrada per classe di traffico. Template: __LOW_BACKEND__ viene
# risolto da split.sh in varnish-l (partizione) o varnish-h (riferimento
# condiviso), e il risultato scritto in router.active.conf.
#
# Cosi' il riferimento e' una cache davvero condivisa. Prima del 30
# agosto le due classi finivano sempre su istanze separate: il confronto
# era fra due partizioni, non fra partizione e condivisione.

map $http_user_agent $cache_upstream {
    default            "varnish-high";
    "~*lowloc"         "varnish-low";
}

upstream varnish-high { server varnish-h:80; keepalive 64; }
upstream varnish-low  { server __LOW_BACKEND__:80; keepalive 64; }

server {
    listen 80;
    location / {
        proxy_pass http://$cache_upstream;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header User-Agent $http_user_agent;
        proxy_pass_request_headers on;
    }
}