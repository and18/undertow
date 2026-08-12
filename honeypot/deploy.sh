#!/usr/bin/env bash
#
# deploy.sh - Installa configurazione e contenuto dell'honeypot.
#
# Idempotente: si puo' rilanciare quante volte si vuole.
#
# Uso:
#   ./honeypot/deploy.sh              installa contenuto e config
#   ./honeypot/deploy.sh --generate   rigenera prima il sito
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE_SRC="$REPO/site"
WEBROOT="/var/www/theslowshelf"
VENV="$HOME/.venv"

log() { printf '\033[1m==>\033[0m %s\n' "$*"; }

# --- generazione opzionale del contenuto --------------------------------
if [[ "${1:-}" == "--generate" ]]; then
    log "rigenero il sito"
    "$VENV/bin/python" "$REPO/honeypot/content/generate.py" --books 50
fi

if [[ ! -d "$SITE_SRC" ]]; then
    echo "Errore: $SITE_SRC non esiste. Lancia prima:  $0 --generate" >&2
    exit 1
fi

# --- contenuto -----------------------------------------------------------
log "installo il contenuto in $WEBROOT"
sudo mkdir -p "$WEBROOT"
sudo rsync -a --delete "$SITE_SRC/" "$WEBROOT/"

log "installo i file statici"
sudo cp "$REPO/honeypot/static/robots.txt" "$WEBROOT/robots.txt"
sudo cp "$REPO/honeypot/static/about.html" "$WEBROOT/about.html"
[[ -f "$REPO/honeypot/static/404.html" ]] && \
    sudo cp "$REPO/honeypot/static/404.html" "$WEBROOT/404.html"

sudo chown -R www-data:www-data "$WEBROOT"
sudo find "$WEBROOT" -type d -exec chmod 755 {} \;
sudo find "$WEBROOT" -type f -exec chmod 644 {} \;

# --- configurazione nginx ------------------------------------------------
log "installo la configurazione nginx"
sudo cp "$REPO/honeypot/nginx/00-agentic-log.conf" /etc/nginx/conf.d/
sudo cp "$REPO/honeypot/nginx/theslowshelf.conf" \
        /etc/nginx/sites-available/theslowshelf
sudo ln -sf /etc/nginx/sites-available/theslowshelf \
            /etc/nginx/sites-enabled/theslowshelf
sudo rm -f /etc/nginx/sites-enabled/default

# --- rotazione dei log ---------------------------------------------------
# Con 1 GB di RAM e mesi di traffico, il disco pieno e' il modo piu'
# realistico di rompere questa macchina.
log "configuro la rotazione dei log"
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

# --- verifica ------------------------------------------------------------
log "verifico la configurazione"
sudo nginx -t

log "ricarico nginx"
sudo systemctl reload nginx

sleep 1
log "controllo di sanita'"
for path in / /robots.txt /sitemap.xml /about.html /library.html; do
    code=$(curl -s -o /dev/null -w '%{http_code}' "https://theslowshelf.org$path")
    printf '  %-16s %s\n' "$path" "$code"
done

pages=$(find "$WEBROOT" -name '*.html' | wc -l)
log "fatto: $pages pagine servite da $WEBROOT"