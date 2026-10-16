#!/usr/bin/env bash
# =====================================================================
# AIpt — one-shot production deploy (HTTP + IP, no HTTPS)
# Target: Debian 12 (bookworm) on Huawei Flexus 2C/2G
# Usage (run on the server — see README "Deploy via console" for options):
#   bash scripts/deploy.sh
# =====================================================================
set -euo pipefail

SERVER_IP="${SERVER_IP:-139.159.132.123}"

APP_USER="aipt"
APP_HOME="/home/${APP_USER}"
BACKEND_DIR="${APP_HOME}/backend"
FRONTEND_STATIC="/var/www/aipt"
VENV="${BACKEND_DIR}/.venv"
PG_PASSWORD="${PG_PASSWORD:-aipt_strong_$(head -c6 /dev/urandom | base64 -w0)}"
NGINX_SITE="/etc/nginx/sites-available/aipt"

echo "=== [1/7] OS packages ==="
sudo apt-get update -yq
sudo apt-get install -yq python3 python3-venv python3-pip \
    postgresql postgresql-contrib nginx curl ca-certificates

echo "=== [2/7] PostgreSQL ==="
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='aipt'" | grep -q 1; then
    sudo -u postgres psql -c "CREATE ROLE aipt LOGIN PASSWORD '${PG_PASSWORD}';"
    sudo -u postgres psql -c "CREATE DATABASE aipt OWNER aipt;"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE aipt TO aipt;"
fi
# pg_hba.conf — scram-sha-256, NOT trust for prod.
PG_HBA="$(sudo -u postgres psql -tAc "SHOW hba_file")"
sudo sed -i 's/host.*all.*all.*md5   /host    all    all    127.0.0.1\/32    scram-sha-256/' "$PG_HBA" 2>/dev/null || true
sudo pg_ctlcluster "$(ls -1 /etc/postgresql | head -1)" main reload 2>/dev/null || sudo systemctl reload postgresql || true

echo "=== [3/7] App user + dirs ==="
if ! id "$APP_USER" &>/dev/null; then
    sudo useradd -m -s /bin/bash "$APP_USER"
fi
sudo mkdir -p "$BACKEND_DIR" "$FRONTEND_STATIC" data/uploads

echo "=== [4/7] Copy code (assumes repo is at /tmp/AIpt or current dir) ==="
REPO_SRC="${REPO_SRC:-$(pwd)}"
if [[ ! -d "$REPO_SRC/backend" ]]; then
    # Try /tmp/AIpt — if someone git clone'd it there.
    REPO_SRC="/tmp/AIpt"
fi
echo "  repo source: $REPO_SRC"
sudo rsync -a --delete "$REPO_SRC/frontend/dist/"   "$FRONTEND_STATIC/"
sudo rsync -a --delete --exclude '.site-packages' --exclude '__pycache__' \
    --exclude '.env' --exclude '.env.example' "$REPO_SRC/backend/" "$BACKEND_DIR/"
# deploy/ scripts/ 目录也带上，方便后续维护
sudo rsync -a        "$REPO_SRC/deploy/"           "$BACKEND_DIR/deploy/"
sudo rsync -a        "$REPO_SRC/scripts/"          "$BACKEND_DIR/scripts/"

# Write .env.prod (PG password + IP cors).
cat > "${BACKEND_DIR}/.env.prod" <<EOF
APP_NAME=AIpt RAG Platform
APP_ENV=prod
APP_HOST=127.0.0.1
APP_PORT=8000
APP_CORS_ORIGINS=http://${SERVER_IP}:5173,http://${SERVER_IP},http://${SERVER_IP}/
APP_STORAGE_DIR=${BACKEND_DIR}/data/uploads

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=aipt
POSTGRES_PASSWORD=${PG_PASSWORD}
POSTGRES_DB=aipt

AUTH_JWT_SECRET=tJxP1tTpscNQyVnTnF9tBYRSlKFKLr7PKInRioDF8777KkrHf0hf9yFc-Hpl4oTP
AUTH_JWT_ALGO=HS256
AUTH_JWT_EXPIRE_MINUTES=720

# 注意：这里的 LLM/Embedding key 需要手动从仓库 backend/.env.prod 复制过来！
# 占位如下 — 替换成真实值。
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-b9b0469b47af4b5d82950ae71b036b71
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_FALLBACK_PROVIDER=qwen
LLM_FALLBACK_API_KEY=
LLM_FALLBACK_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_FALLBACK_MODEL=qwen-plus

EMBEDDING_PROVIDER=qwen
EMBEDDING_API_KEY=sk-ws-H.DIDMDYM.uggF.MEUCIQDytefZpISoh-zE5yqOJbCk1xF_N7HIhQU44ZmCWmnJQQIgYiAJ2_P6L6qgwo7kINFIRXwT_XwTLVgYYwUWGROKvyI
EMBEDDING_BASE_URL=https://ws-apo1k6fyj2goy763.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_DIM=1024

RAG_CHUNK_SIZE=800
RAG_CHUNK_OVERLAP=100
RAG_VECTOR_TOP_K=10
RAG_BM25_TOP_K=10
RAG_FINAL_TOP_K=6
EOF

sudo chown -R "${APP_USER}:${APP_USER}" "$BACKEND_DIR" "$FRONTEND_STATIC"

echo "=== [5/7] Python venv + deps ==="
sudo -u "$APP_USER" bash -c "
    cd $BACKEND_DIR
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip setuptools wheel -q
    .venv/bin/pip install -r requirements.txt -q
"

echo "=== [6/7] Alembic migrate ==="
sudo -u "$APP_USER" bash -c "
    cd $BACKEND_DIR
    APP_ENV=prod .venv/bin/alembic upgrade head
"

echo "=== [7/7] systemd + Nginx ==="
sudo tee /etc/systemd/system/aipt.service >/dev/null <<EOF
[Unit]
Description=AIpt RAG Platform (uvicorn)
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${BACKEND_DIR}
Environment=APP_ENV=prod
Environment=APP_HOST=127.0.0.1
Environment=APP_PORT=8000
EnvironmentFile=${BACKEND_DIR}/.env.prod
ExecStart=${BACKEND_DIR}/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=on-failure
RestartSec=3
StandardOutput=journal
StandardError=journal
MemoryMax=1200M
CPUQuota=160%
NoNewPrivileges=true
ProtectSystem=full
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now aipt
sleep 2
sudo systemctl --no-pager --full status aipt | head -12

# Nginx — HTTP-only.
sudo cp "$BACKEND_DIR/deploy/nginx-http.conf" "$NGINX_SITE"
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf "$NGINX_SITE" /etc/nginx/sites-enabled/aipt
sudo nginx -t && sudo systemctl reload nginx

echo ""
echo "=== DEPLOY DONE ==="
echo "  curl http://127.0.0.1/api/v1/health      # backend"
echo "  curl -I http://127.0.0.1/                  # frontend via nginx"
echo "  curl http://${SERVER_IP}/                  # external"
echo "  journalctl -u aipt -f                      # realtime logs"
echo "  sudo systemctl restart aipt                # restart after .env change"
echo ""
echo "PG password (save this): ${PG_PASSWORD}"
