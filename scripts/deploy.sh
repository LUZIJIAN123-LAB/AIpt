#!/usr/bin/env bash
# =====================================================================
# AIpt — one-shot production deploy
# Target: Debian 12 (bookworm) on Huawei Flexus 2C/2G
# Run as: sudo -u aipt bash scripts/deploy.sh [YOURDOMAIN.COM]
# =====================================================================
set -euo pipefail

DOMAIN="${1:-}"
if [[ -z "$DOMAIN" || "$DOMAIN" == "YOURDOMAIN.COM" ]]; then
    echo "Usage: sudo -u aipt bash scripts/deploy.sh your.real.domain"
    echo "Edit .env.prod first (POSTGRES_PASSWORD + APP_CORS_ORIGINS)."
    exit 1
fi

APP_USER="aipt"
APP_HOME="/home/${APP_USER}"
BACKEND_DIR="${APP_HOME}/backend"
FRONTEND_STATIC="/var/www/aipt"
VENV="${BACKEND_DIR}/.venv"
PG_PASSWORD="XSTRONG_POSTGRES_PASSWORDX"   # change me
NGINX_SITE="/etc/nginx/sites-available/aipt"

echo "=== [1/7] OS packages ==="
sudo apt-get update -yq
sudo apt-get install -yq python3 python3-venv python3-pip \
    postgresql postgresql-contrib \
    nginx certbot python3-certbot-nginx \
    git curl ca-certificates gnupg

echo "=== [2/7] PostgreSQL ==="
# Create aipt role + DB (run as postgres).
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='aipt'" | grep -q 1; then
    sudo -u postgres psql -c "CREATE ROLE aipt LOGIN PASSWORD '${PG_PASSWORD}';"
    sudo -u postgres psql -c "CREATE DATABASE aipt OWNER aipt;"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE aipt TO aipt;"
fi

# pg_hba.conf — scram-sha-256 (NOT trust, prod security).
PG_HBA="$(sudo -u postgres psql -tAc "SHOW hba_file")"
if grep -q "host.*all.*aipt.*trust" "$PG_HBA" 2>/dev/null; then
    sudo sed -i 's/host.*all.*aipt.*trust/host    all    aipt    127.0.0.1\/32    scram-sha-256/' "$PG_HBA"
    sudo pg_ctlcluster "$(ls -1 /etc/postgresql)" main reload 2>/dev/null || sudo systemctl reload postgresql
fi

echo "=== [3/7] App user + venv ==="
if ! id "$APP_USER" &>/dev/null; then
    sudo useradd -m -s /bin/bash "$APP_USER"
fi
mkdir -p "$BACKEND_DIR"

echo "=== [4/7] Copy backend + frontend dist ==="
# Assume this script runs from repo root; rsync to server.
sudo mkdir -p /var/www/aipt
sudo rsync -a --delete frontend/dist/ "$FRONTEND_STATIC/"
sudo rsync -a --delete --exclude '.site-packages' --exclude '__pycache__' \
    --exclude '.env' --exclude '.env.example' backend/ "$BACKEND_DIR/"

# Copy prod env (deployer must have edited it first).
cp backend/.env.prod "${BACKEND_DIR}/.env.prod"

sudo chown -R "${APP_USER}:${APP_USER}" "$BACKEND_DIR"

echo "=== [5/7] Python venv + deps ==="
sudo -u "$APP_USER" bash -c "
    cd $BACKEND_DIR
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip setuptools wheel
    .venv/bin/pip install -r requirements.txt
"

# Update .env.prod with the real PG password + domain.
sudo sed -i "s/XSTRONG_POSTGRES_PASSWORDX/${PG_PASSWORD}/" "${BACKEND_DIR}/.env.prod"
sudo sed -i "s/YOURDOMAIN.COM/${DOMAIN}/g" "${BACKEND_DIR}/.env.prod"

echo "=== [6/7] Alembic migrate ==="
sudo -u "$APP_USER" bash -c "
    cd $BACKEND_DIR
    APP_ENV=prod .venv/bin/alembic upgrade head
"

echo "=== [7/7] systemd + Nginx ==="
# systemd unit
sudo sed "s|YOURDOMAIN.COM|${DOMAIN}|g; s|XSTRONG_POSTGRES_PASSWORDX|${PG_PASSWORD}|g" \
    deploy/aipt.service | sudo tee /etc/systemd/system/aipt.service >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable aipt
sudo systemctl restart aipt
sleep 2
sudo systemctl --no-pager --full status aipt | head -15

# Nginx
sudo sed "s|YOURDOMAIN.COM|${DOMAIN}|g" deploy/nginx.conf | sudo tee "$NGINX_SITE" >/dev/null
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/aipt
sudo nginx -t && sudo systemctl reload nginx

# HTTPS via certbot (non-interactive).
sudo certbot --nginx -d "$DOMAIN" --email "admin@${DOMAIN}" --agree-tos --no-eff-email -q || true

echo ""
echo "=== DEPLOY DONE ==="
echo "Checks:"
echo "  curl http://127.0.0.1:8000/api/v1/health   # backend"
echo "  curl -I https://${DOMAIN}/                   # HTTPS + SPA"
echo "  journalctl -u aipt -f                        # logs"
