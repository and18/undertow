#!/bin/sh
set -e

# Parametri di default
VARNISH_SIZE=${VARNISH_SIZE:-256m}
VARNISH_BACKEND=${VARNISH_BACKEND:-app:8000}

# Parsing di VARNISH_BACKEND nel formato host:port
VARNISH_BACKEND_HOST=${VARNISH_BACKEND%:*}
VARNISH_BACKEND_PORT=${VARNISH_BACKEND#*:}
VARNISH_BACKEND_PORT=${VARNISH_BACKEND_PORT:-8000}

# Genera default.vcl dal template usando envsubst
export VARNISH_BACKEND_HOST VARNISH_BACKEND_PORT
envsubst < /tmp/default.vcl.tpl > /etc/varnish/default.vcl

# Avvia varnishd con i parametri richiesti
exec varnishd -F -f /etc/varnish/default.vcl \
  -n /var/lib/varnish/ut \
  -a http=:80,HTTP \
  -s malloc,${VARNISH_SIZE} \
  -p thread_pool_min=50 -p thread_pool_max=1000
