#!/usr/bin/env bash
#
# deploy.sh - Installs the honeypot's configuration and content.
#
# Idempotent: it can be rerun as many times as needed.
#
# Usage:
#   ./honeypot/deploy.sh              install content and config
#   ./honeypot/deploy.sh --generate   regenerate the site first
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE_SRC="$REPO/site"
WEBROOT="/var/www/theslowshelf"
VENV="$HOME/.venv"

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }

# --- optional content generation ----------------------------------------
if [[ "${1:-}" == "--generate" ]]; then
    log "regenerating the site"
    "$VENV/bin/python" "$REPO/honeypot/content/generate.py" --books 500
fi

if [[ ! -d "$SITE_SRC" ]]; then
    echo "Error: $SITE_SRC does not exist. Run first:  $0 --generate" >&2
    exit 1
fi

# --- content -------------------------------------------------------------
log "installing the content in $WEBROOT"
sudo mkdir -p "$WEBROOT"
sudo rsync -a --delete "$SITE_SRC/" "$WEBROOT/"

log "installing the static files"
sudo cp "$REPO/honeypot/static/robots.txt" "$WEBROOT/robots.txt"
sudo cp "$REPO/honeypot/static/989bd4b93d864525a40b9b19bc590fed.txt" "$WEBROOT/989bd4b93d864525a40b9b19bc590fed.txt"
sudo cp "$REPO/honeypot/static/about.html" "$WEBROOT/about.html"
[[ -f "$REPO/honeypot/static/404.html" ]] && \
    sudo cp "$REPO/honeypot/static/404.html" "$WEBROOT/404.html"

sudo chown -R www-data:www-data "$WEBROOT"
sudo find "$WEBROOT" -type d -exec chmod 755 {} \;
sudo find "$WEBROOT" -type f -exec chmod 644 {} \;

# --- nginx configuration -------------------------------------------------
log "installing the nginx configuration"
sudo cp "$REPO/honeypot/nginx/00-agentic-log.conf" /etc/nginx/conf.d/
sudo cp "$REPO/honeypot/nginx/theslowshelf.conf" \
        /etc/nginx/sites-available/theslowshelf
sudo ln -sf /etc/nginx/sites-available/theslowshelf \
            /etc/nginx/sites-enabled/theslowshelf
sudo rm -f /etc/nginx/sites-enabled/default

# --- log rotation --------------------------------------------------------
# With 1 GB of RAM and months of traffic, a full disk is the most
# realistic way to break this machine.
log "configuring log rotation"
sudo tee /etc/logrotate.d/agentic >/dev/null <<'EOF'
/var/log/nginx/agentic.log {
    daily
    rotate 120
    compress
    delaycompress
    missingok
    notifempty
    create 0640 www-data adm
    sharedscripts
    postrotate
        [ -f /var/run/nginx.pid ] && kill -USR1 $(cat /var/run/nginx.pid)
    endscript
}
EOF

# --- verification --------------------------------------------------------
log "checking the configuration"
sudo nginx -t

log "reloading nginx"
sudo systemctl reload nginx

sleep 1
log "sanity check"
for path in / /robots.txt /sitemap.xml /about.html /library.html; do
    code=$(curl -s -o /dev/null -w '%{http_code}' "https://theslowshelf.org$path")
    printf '  %-16s %s\n' "$path" "$code"
done

pages=$(find "$WEBROOT" -name '*.html' | wc -l)
log "done: $pages pages served from $WEBROOT"