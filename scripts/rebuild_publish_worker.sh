#!/bin/bash
# 拉起 publish_worker：与 backend 一致，显式挂载镜像声明的全部 VOLUME 点
set -e
cd /srv/amazon-meli-publisher

TOKEN_KEY=$(grep -E '^TOKEN_ENCRYPTION_KEY=' .env | cut -d= -f2- | tr -d '"' | tr -d "'")
if [ -z "$TOKEN_KEY" ]; then
  TOKEN_KEY=$(docker inspect amazon-meli-publisher_backend_1 --format '{{range .Config.Env}}{{println .}}{{end}}' | grep '^TOKEN_ENCRYPTION_KEY=' | cut -d= -f2-)
fi
[ -z "$TOKEN_KEY" ] && { echo "ERROR: no TOKEN_ENCRYPTION_KEY"; exit 1; }
NETWORK=$(docker inspect amazon-meli-publisher_backend_1 --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{end}}')
MELI_ID=$(grep -E '^MELI_CLIENT_ID=' .env | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
MELI_SECRET=$(grep -E '^MELI_CLIENT_SECRET=' .env | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
LIVE=$(grep -E '^ALLOW_LIVE_PUBLISH=' .env | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
[ -z "$LIVE" ] && LIVE=false
echo "network=$NETWORK live=$LIVE"

docker rm -f amazon-meli-publisher_publish_worker_1 2>/dev/null || true

docker run -d --name amazon-meli-publisher_publish_worker_1 \
  --init --restart unless-stopped \
  --network "$NETWORK" \
  -e DATABASE_URL=postgresql+psycopg://meli:meli@postgres:5432/amazon_meli \
  -e "TOKEN_ENCRYPTION_KEY=$TOKEN_KEY" \
  -e "MELI_CLIENT_ID=$MELI_ID" \
  -e "MELI_CLIENT_SECRET=$MELI_SECRET" \
  -e "ALLOW_LIVE_PUBLISH=$LIVE" \
  -v /srv/amazon-meli-publisher/backend/app:/app/app:ro \
  -v /srv/amazon-meli-publisher/backend/alembic:/app/alembic:ro \
  -v /srv/amazon-meli-publisher/backend/alembic.ini:/app/alembic.ini:ro \
  -v /srv/amazon-meli-publisher/data/amazon-browser:/data/amazon-browser \
  mvp-skeleton-backend:latest \
  python -m app.worker --queue publish --loop --interval 30 --limit 10

sleep 10
docker ps --filter name=publish_worker --format '{{.Names}} {{.Status}}'
echo "=== worker 日志 ==="
docker logs amazon-meli-publisher_publish_worker_1 --tail 10 2>&1 | tail -10
