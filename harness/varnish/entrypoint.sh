#!/bin/sh
set -e

# Default parameters
VARNISH_SIZE=${VARNISH_SIZE:-256m}
VARNISH_BACKEND=${VARNISH_BACKEND:-app:8000}

# Parse VARNISH_BACKEND in host:port format
VARNISH_BACKEND_HOST=${VARNISH_BACKEND%:*}
VARNISH_BACKEND_PORT=${VARNISH_BACKEND#*:}
VARNISH_BACKEND_PORT=${VARNISH_BACKEND_PORT:-8000}

# Generate default.vcl from the template using envsubst
export VARNISH_BACKEND_HOST VARNISH_BACKEND_PORT
envsubst < /tmp/default.vcl.tpl > /etc/varnish/default.vcl

# Start varnishd with the required parameters
exec varnishd -F -f /etc/varnish/default.vcl \
  -n /var/lib/varnish/ut \
  -a http=:80,HTTP \
  -s malloc,${VARNISH_SIZE} \
  -p thread_pool_min=50 -p thread_pool_max=1000
