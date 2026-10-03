vcl 4.1;

# Deliberately minimal configuration.
#
# Every heuristic added here is a variable that would have to be justified
# in the methodology. The cache behaviour must depend ONLY on the
# Cache-Control headers emitted by the application, so that the distinction
# between cacheable and non-cacheable is a property of the workload and not
# of the configuration.

backend default {
    .host = "${VARNISH_BACKEND_HOST}";
    .port = "${VARNISH_BACKEND_PORT}";
    .connect_timeout = 5s;
    .first_byte_timeout = 120s;
    .between_bytes_timeout = 30s;
    # The connection pool towards the origin is itself a limited resource:
    # raising it too much masks saturation downstream.
    .max_connections = 200;
}

sub vcl_recv {
    # No normalisation of the cache key: a different URL is a different
    # object, which is precisely what makes agentic traffic destructive
    # for the cache.
    if (req.method != "GET" && req.method != "HEAD") {
        return (pass);
    }
    return (hash);
}

sub vcl_backend_response {
    # TTL and eviction derive from the application's Cache-Control.
    # No hidden defaults.
    if (beresp.http.Cache-Control ~ "no-store") {
        set beresp.uncacheable = true;
        set beresp.ttl = 0s;
        return (deliver);
    }
    # No grace, no keep: we want to measure the true miss, not a stale
    # response that would mask it.
    set beresp.grace = 0s;
    set beresp.keep = 0s;
    return (deliver);
}

sub vcl_deliver {
    # Diagnostic header: lets the load generator record hits and misses
    # per request, not only in aggregate from Varnish's statistics.
    if (obj.hits > 0) {
        set resp.http.X-Cache = "HIT";
    } else {
        set resp.http.X-Cache = "MISS";
    }
    set resp.http.X-Cache-Hits = obj.hits;
    return (deliver);
}
