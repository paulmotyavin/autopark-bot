#!/usr/bin/env bash
# Локальный дамп PostgreSQL перед миграциями. Хранит последние 10 файлов в ./backups.
# ВАЖНО: это страховка на момент деплоя, а не полноценный бэкап (лежит на том же сервере).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups

if ! docker compose ps --status running --services | grep -qx postgres; then
  echo "postgres не запущен — пропускаю дамп (вероятно, первый деплой)"
  exit 0
fi

out="backups/pre-deploy-$(date +%Y%m%d-%H%M%S).sql.gz"
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$out"
if [ ! -s "$out" ]; then
  echo "Дамп пустой, останавливаю деплой" >&2
  rm -f "$out"
  exit 1
fi
echo "Дамп: $out"
ls -1t backups/pre-deploy-*.sql.gz | tail -n +11 | xargs -r rm --
