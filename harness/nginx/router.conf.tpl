# Routes by traffic class. Template: split.sh resolves __LOW_BACKEND__ to
# varnish-l (partition) or varnish-h (shared reference), and writes the
# result to router.active.conf.
#
# This way the reference is a truly shared cache. Before 30 August the
# two classes always ended up on separate instances: the comparison was
# between two partitions, not between partition and sharing.

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